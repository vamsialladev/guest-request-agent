"""Capture the README and case-study screenshots from the real app (real agent runs, no mock-ups).

python scripts/capture_screenshots.py            # starts its own local app on port 8520, then captures

Starts a separate local instance with an empty log folder and a freshly generated Admin password that lives only in
this process (never printed or saved), so the Admin screenshots show only this script's own requests and no secret.
Runs the agent on 4 sample emails and 1 typed email (about $0.01). Dev-only: needs Playwright (requirements-dev.txt).
"""

import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "docs" / "images"
PORT = 8520
URL = f"http://localhost:{PORT}"
DESKTOP, PHONE = (1280, 900), (390, 844)
TALL = (1280, 3400)  # Streamlit scrolls inside its own container: a tall window shows a whole result at once


def start_app(password: str, log_dir: str) -> subprocess.Popen:
    env = {**os.environ, "ADMIN_PASSWORD": password, "LOG_DIR": log_dir}
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", str(PORT)]
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2)
            return proc
        except OSError:
            time.sleep(1)
    proc.kill()
    raise SystemExit("The app didn't start.")


def ready(page):
    page.wait_for_selector("h1.gra-title", timeout=120_000)
    page.wait_for_timeout(1500)


def run_email(page, email_id: str):
    page.goto(f"{URL}/?email={email_id}")
    ready(page)
    button = page.locator("button", has_text=re.compile("Run the agent on this email|Show the agent's result")).first
    button.wait_for(timeout=120_000)  # the first page load also builds the policy index
    button.click()
    page.get_by_text("Draft reply", exact=True).first.wait_for(timeout=120_000)
    page.wait_for_timeout(1200)


def top(page, path: Path, height: int = DESKTOP[1]):
    """What a visitor sees first: the top of the page at a laptop's window height."""
    page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": DESKTOP[0], "height": height})
    print("saved", path.relative_to(ROOT))


def visible(page, text: str):
    """The first visible element with this text (the data grid keeps a hidden copy of its cells)."""
    return page.get_by_text(text, exact=False).locator("visible=true").first


def region(page, start_text: str, end_text: str | None, path: Path, pad: int = 12):
    """Screenshot from the element containing start_text down to end_text (or the end of the main column)."""
    main = page.locator("[data-testid=stMainBlockContainer]").first.bounding_box()
    top_y = visible(page, start_text).bounding_box()["y"] - pad
    if end_text:
        end = visible(page, end_text).bounding_box()
        bottom = end["y"] + end["height"] + pad
    else:
        bottom = main["y"] + main["height"]
    top_y = max(0, top_y)
    page.screenshot(path=str(path), clip={"x": main["x"], "y": top_y, "width": main["width"], "height": bottom - top_y})
    print("saved", path.relative_to(ROOT))


def main():
    from playwright.sync_api import sync_playwright

    IMAGES.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)  # test-only, this process only
    with tempfile.TemporaryDirectory() as logs:
        proc = start_app(password, logs)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                ctx = browser.new_context(viewport={"width": TALL[0], "height": TALL[1]}, color_scheme="light")
                page = ctx.new_page()
                page.goto(URL)
                ready(page)
                top(page, IMAGES / "inbox.png")

                run_email(page, "E01")
                end = "Demo: nothing is ever emailed"
                region(page, "Arriving Friday - a few questions", end, IMAGES / "agent-result.png")
                page.get_by_role("button", name="Edit").first.click()
                page.wait_for_timeout(800)
                box = page.locator("textarea").first
                box.fill(
                    box.input_value().replace("Warm regards", "We look forward to meeting Biscuit!\n\nWarm regards")
                )
                page.get_by_role("button", name="Done editing").first.click()
                page.wait_for_timeout(800)
                page.get_by_role("button", name="Approve & send (simulated)").first.click()
                page.wait_for_timeout(1500)
                # In-app navigation: a full reload would start a new session with an empty outbox.
                page.locator("[data-testid=stSidebarNav] a", has_text="Outbox and tasks").first.click()
                page.wait_for_selector("h1.gra-title:has-text('Outbox and tasks')", timeout=60_000)
                page.wait_for_timeout(1000)
                page.locator("[data-testid=stExpander] summary").first.click()
                page.wait_for_timeout(600)
                region(page, "Demo · simulated data", "Manager queue", IMAGES / "outbox.png")

                run_email(page, "E05")
                region(page, "Escalated to a manager", "Demo: nothing is ever emailed", IMAGES / "escalation.png")
                run_email(page, "E14")
                region(page, "What the agent did", "Demo: nothing is ever emailed", IMAGES / "injection.png")

                page.goto(f"{URL}/write")
                ready(page)
                page.get_by_text("Example 1", exact=True).first.click()
                page.wait_for_timeout(800)
                page.get_by_role("button", name="Run the agent").first.click()
                page.get_by_text("Draft reply", exact=True).first.wait_for(timeout=120_000)
                page.wait_for_timeout(1000)
                region(page, "Demo · simulated data", "Draft reply", IMAGES / "write-your-own.png", pad=300)

                page.goto(f"{URL}/how-it-works")
                ready(page)
                region(page, "Demo · simulated data", "Definitions and every miss", IMAGES / "how-it-works.png")

                page.goto(f"{URL}/admin")
                ready(page)
                page.locator("input[type=password]").first.fill(password)
                page.get_by_role("button", name="Unlock").click()
                page.wait_for_selector("h1.gra-title:has-text('Admin')", timeout=60_000)
                page.wait_for_timeout(1500)
                region(page, "Health and errors", "Keep downloads private", IMAGES / "admin-list.png")
                page.get_by_placeholder("Words in the sender, subject or body").fill("Arriving Friday")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)  # the approved, edited E01 request
                grid = page.locator("[data-testid=stDataFrame]").first.bounding_box()
                page.mouse.click(grid["x"] + 15, grid["y"] + 52)  # select the first row (newest request)
                dialog = page.locator("[role=dialog]")
                dialog.wait_for(timeout=30_000)
                dialog.get_by_role("tab", name="Agent steps").click()
                page.wait_for_timeout(800)
                dialog.screenshot(path=str(IMAGES / "admin-details.png"))
                print("saved docs/images/admin-details.png")
                dialog.get_by_role("tab", name="Draft vs final").click()
                page.wait_for_timeout(800)
                dialog.screenshot(path=str(IMAGES / "admin-diff.png"))
                print("saved docs/images/admin-diff.png")

                dark = browser.new_context(viewport={"width": TALL[0], "height": TALL[1]}, color_scheme="dark")
                dpage = dark.new_page()
                run_email(dpage, "E01")
                region(dpage, "Arriving Friday - a few questions", "Requests found", IMAGES / "agent-result-dark.png")
                phone = browser.new_context(
                    viewport={"width": PHONE[0], "height": PHONE[1]},
                    device_scale_factor=2,
                    is_mobile=True,
                    has_touch=True,
                    color_scheme="light",
                )
                ppage = phone.new_page()
                run_email(ppage, "E01")
                ppage.get_by_text("Draft reply", exact=True).first.scroll_into_view_if_needed()
                ppage.screenshot(path=str(IMAGES / "phone.png"))
                print("saved docs/images/phone.png")
                browser.close()
        finally:
            proc.kill()


if __name__ == "__main__":
    main()
