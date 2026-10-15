"""Shared Streamlit building blocks: cached resources, header, banner, footer, the email and the agent result panel.

Only static markup or `esc()`-escaped values go into HTML here.
"""

import functools
import logging
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

from src.approval import ApprovalError, Desk, Review, approve, reject
from src.branding import DEMO_LABEL, load_branding
from src.config import LOG_DIR, MAX_EMAILS_PER_DAY, ROOT
from src.display import badge_html, draft_html, esc
from src.errors import PAGE_ERROR, is_control_flow, record_error
from src.limits import DailyCounter
from src.models import AgentResult
from src.secrets_check import log_missing, missing_required
from src.tools import ACTION_NAMES, DEPARTMENT_NAMES, PROPERTY_NAMES
from src.usage import log_decision

HERE = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def brand():
    """Re-read when branding.toml changes: a push updates the file in place on Streamlit Cloud."""
    from src.branding import BRANDING_FILE

    return _brand(BRANDING_FILE.stat().st_mtime_ns if BRANDING_FILE.exists() else 0)


@st.cache_resource(show_spinner=False)
def _brand(mtime_ns: int):
    return load_branding()


@st.cache_resource(show_spinner=False)
def daily_counter():
    return DailyCounter(LOG_DIR / "daily_count.json", MAX_EMAILS_PER_DAY)


@st.cache_resource(show_spinner=False)
def app_started() -> float:
    return time.time()


@st.cache_resource(show_spinner=False)
def startup_checks() -> list[str]:
    """Once per server start: log each missing required secret by name (never a value)."""
    return log_missing()


@st.cache_resource(show_spinner="Starting up: building the policy index and the synthetic bookings…")
def warm_up() -> bool:
    from src import policy_search
    from src.bookings import ensure_db

    ensure_db()
    policy_search.retriever()
    return True


@st.cache_resource(show_spinner=False)
def shared_results() -> dict:
    """Results for the sample inbox emails, shared by every visitor in this server process (keeps the demo free)."""
    return {}


@contextmanager
def error_boundary(page: str):
    """No page ever shows Streamlit's crash screen or a traceback: a friendly message, and a record for the owner."""
    try:
        yield
    except BaseException as exc:
        if is_control_flow(exc):
            raise
        logging.getLogger("guest_agent.app").exception("page error on %s", page)
        record_error(page, exc)
        st.error(PAGE_ERROR, icon=":material/error:")


def safe_callback(page: str):
    def wrap(fn):
        @functools.wraps(fn)
        def guarded(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                logging.getLogger("guest_agent.app").exception("callback error on %s", page)
                record_error(page, exc)
                st.session_state.callback_error = True

        return guarded

    return wrap


def asset(path: str) -> str:
    return str(ROOT / path)


# ---------- Project 4: Demo mode / Staff sign-in, storage note ----------
def _staff_gate():
    from src.roles import GateState

    return st.session_state.setdefault("staff_gate", GateState())


def is_staff() -> bool:
    from src.config import STAFF_IDLE_MINUTES, staff_password
    from src.roles import STAFF, role

    if not staff_password():
        return False
    return role(_staff_gate(), time.time(), STAFF_IDLE_MINUTES * 60) == STAFF


def log_storage_note() -> str:
    """Honest wording for where the logs live (no connection details)."""
    from src import store

    s = store.status()
    if s["backend"] in ("postgres", "sqlite") and s["ok"]:
        return f"Stored in the database ({s['backend']}), kept for {s['retention_days']} days, personal data redacted."
    if s["configured"]:
        return "Database configured but not reachable: logging to a temporary file (resets when the app restarts)."
    return "Logs reset when the app restarts. Download a copy to keep it."


def staff_panel(recent_items):
    """Sidebar: the Demo mode label, and Staff sign-in when STAFF_PASSWORD is set. `recent_items()` returns this
    session's (drafts) as (request_id, text) pairs for the report form."""
    from src.config import STAFF_IDLE_MINUTES, staff_password
    from src.roles import DEMO_LABEL as MODE_LABEL
    from src.roles import REPORT_REASONS, report_record, sign_out, staff_attempt
    from src.usage import append_jsonl, now_iso

    with st.sidebar:
        if not is_staff():
            st.caption(MODE_LABEL)
            if not staff_password():
                return
            with st.expander("Staff sign-in", icon=":material/badge:"):
                with st.form("staff_login", clear_on_submit=True):
                    given = st.text_input("Staff password", type="password", autocomplete="current-password")
                    submitted = st.form_submit_button("Sign in", icon=":material/login:")
                if submitted:
                    ok, message = staff_attempt(_staff_gate(), given, staff_password(), now=time.time())
                    if ok:
                        st.rerun()
                    time.sleep(1.0)
                    st.error(message, icon=":material/lock:")
                st.caption("Staff can report a draft for review. Visitors use the open Demo mode.")
            return
        st.caption(f"Signed in as staff · signs out after {STAFF_IDLE_MINUTES} idle minutes")
        if st.button("Sign out of staff", icon=":material/logout:", key="staff_sign_out"):
            sign_out(_staff_gate())
            st.rerun()
        items = recent_items()
        with st.expander("Report a draft for review", icon=":material/flag:"):
            if not items:
                st.caption("Nothing to report yet in this session.")
                return
            with st.form("staff_report", clear_on_submit=True):
                labels = [f"{text[:60]}" for _, text in items]
                picked = st.selectbox("Which draft", range(len(items)), format_func=lambda i: labels[i])
                reason = st.selectbox("Reason", REPORT_REASONS)
                note = st.text_area("Note (optional)", max_chars=500)
                sent = st.form_submit_button("Send report", icon=":material/flag:")
            if sent:
                rid, text = items[picked]
                append_jsonl(LOG_DIR / "reports.jsonl", report_record(rid, text, reason, note, now_iso()))
                st.success("Reported. The owner sees it on the Operations page.", icon=":material/check:")


def privacy_storage_line(thing: str, max_entries: int) -> str:
    """Where the log lives, worded for visitors (Project 4): true for both storage modes."""
    from src import store
    from src.config import RETENTION_DAYS

    if store.enabled():
        return (
            f"{thing} are stored in a private database, readable only by the app owner. Emails, phone numbers, "
            "card-like numbers and names are removed, and booking numbers replaced with codes, before anything is "
            f"stored. Records are deleted after {RETENTION_DAYS} days."
        )
    return (
        f"{thing} are stored on the app server, readable only by the app owner, and kept only until the app "
        f"restarts (at most the most recent {max_entries:,} entries)."
    )


def inject_css():
    st.html(f"<style>{(HERE / 'style.css').read_text(encoding='utf-8')}</style>")


def banner():
    st.html(f'<div class="gra-banner" role="note">{esc(DEMO_LABEL)}</div>')


def header(title: str, subtitle: str = "", eyebrow: str = ""):
    banner()
    parts = [f'<p class="gra-eyebrow">{esc(eyebrow)}</p>' if eyebrow else ""]
    parts.append(f'<h1 class="gra-title">{esc(title)}</h1>')
    if subtitle:
        parts.append(f'<p class="gra-subtitle">{esc(subtitle)}</p>')
    st.html("".join(parts))


def tiles(items: list[tuple[str, str, str]]):
    cells = "".join(
        f'<div class="gra-tile"><div class="gra-tile-value">{esc(v)}</div>'
        f'<div class="gra-tile-label">{esc(label)}</div>'
        + (f'<div class="gra-tile-help">{esc(help_text)}</div>' if help_text else "")
        + "</div>"
        for v, label, help_text in items
    )
    st.html(f'<div class="gra-tiles">{cells}</div>')


def empty_state(title: str, body: str):
    st.html(f'<div class="gra-empty"><b>{esc(title)}</b>{esc(body)}</div>')


def link_row() -> str:
    links = brand().links
    items = [
        ("case_study", "Case study"),
        ("github", "GitHub"),
        ("project1", "Project 1: policy assistant"),
        ("linkedin", "LinkedIn"),
    ]
    return " · ".join(
        f'<a href="{esc(links[key])}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'
        for key, label in items
        if links.get(key)
    )


def footer():
    author = brand().links.get("author", "Vamsi Alla")
    st.html(
        '<footer class="gra-footer">'
        f"<p>Built by {esc(author)} · Simulated client engagement for a fictional hotel group, with synthetic data. "
        "Nothing is ever sent.</p>"
        f"<p>{link_row()}</p>"
        "</footer>"
    )
    st.page_link("views/about.py", label="Disclaimer and privacy", icon=":material/policy:")


def fmt_pct(value) -> str:
    return "–" if value is None else f"{value:.0%}"


def fmt_seconds(value) -> str:
    return "–" if value is None else f"{value:.1f}s"


# ---------- Session state ----------
def recent_drafts() -> list[tuple[str, str]]:
    """This session's drafts (request_id, subject), newest first, for the staff report form."""
    reviews = list(desk().reviews.values())
    return [(r.request_id, f"{r.subject} -> {r.to}") for r in reversed(reviews)][:10]


def session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex[:12]
    return st.session_state.session_id


def desk() -> Desk:
    if "desk" not in st.session_state:
        st.session_state.desk = Desk()
    return st.session_state.desk


def results() -> dict:
    """email key -> (AgentResult, request_id) for this browser session."""
    return st.session_state.setdefault("results", {})


def emails_sent_to_agent() -> int:
    return st.session_state.get("agent_count", 0)


def count_email():
    st.session_state.agent_count = emails_sent_to_agent() + 1


def is_first() -> bool:
    first = not st.session_state.get("had_first", False)
    st.session_state.had_first = True
    return first


def new_session():
    for key in ("desk", "results", "agent_count", "had_first", "session_id", "drafts"):
        st.session_state.pop(key, None)


def secrets_missing() -> bool:
    """Friendly message instead of a crash when the app is deployed without its API key."""
    if "ANTHROPIC_API_KEY" in missing_required():
        st.warning(
            "The assistant isn't configured on this server yet, so it can't process emails right now. "
            "The sample emails and the rest of the app still work. (Owner: add ANTHROPIC_API_KEY to the app's "
            "secrets and reboot.)",
            icon=":material/key_off:",
        )
        return True
    return False


# ---------- Email and result panel ----------
def email_card(sender: str, name: str, subject: str, body: str, prop: str, received: str = ""):
    head = (
        f"<span><b>From</b> {esc(name or sender)} &lt;{esc(sender)}&gt;</span>"
        f"<span><b>To</b> Guest Services, {esc(PROPERTY_NAMES.get(prop, prop))}</span>"
        + (f"<span>{esc(received.replace('T', ' '))}</span>" if received else "")
    )
    st.html(
        f'<div class="gra-email"><div class="gra-email-head">{head}</div>'
        + (f'<p class="gra-email-subject">{esc(subject)}</p>' if subject else "")
        + f'<p class="gra-email-body">{esc(body)}</p></div>'
    )


STEP_ICONS = {"triage": "🛡️", "tool": "🔧", "guard": "✅", "fallback": "🛟"}
TOOL_ICONS = {
    "find_booking": "📇",
    "check_availability": "🛏️",
    "search_policy": "📄",
    "propose_task": "🧹",
    "propose_action": "🔒",
}
STATUS_LABELS = {
    "answered": ("Answered", "ok"),
    "task_proposed": ("Task proposed", "info"),
    "needs_manager_approval": ("Needs manager approval", "warn"),
    "cannot_do": ("Can't be done", "muted"),
    "needs_info": ("Asked for details", "muted"),
    "escalated": ("Escalated", "error"),
}


def step_label(step, cited_ids: set[str]) -> str:
    icon = TOOL_ICONS.get(step.name, STEP_ICONS.get(step.kind, "•"))
    if not step.ok:
        icon = "⚠️" if step.kind in ("guard", "triage", "fallback") else "❌"
    text = step.summary
    if step.name == "search_policy" and isinstance(step.result, dict):
        ids = [r["id"] for r in step.result.get("results", [])]
        used = [i for i in ids if i in cited_ids]
        text += f" · cited {', '.join(used)} ✓" if used else " · not cited"
    return f"{icon} {text}"


def timeline(result: AgentResult):
    cited = {c["id"] for c in result.citations}
    for step in result.steps:
        if step.kind == "model":
            continue  # model turns are internal; the tool calls show what happened
        with st.expander(step_label(step, cited)):
            if step.args:
                st.caption("Input")
                st.json(step.args, expanded=True)
            if step.result is not None:
                st.caption("Result")
                st.json(step.result, expanded=False)
            if not step.args and step.result is None:
                st.caption("No details.")


def requests_list(result: AgentResult) -> str:
    items = "".join(
        f"<li>{badge_html(*STATUS_LABELS.get(r.status, (r.status, 'muted')))}<span>{esc(r.summary)}</span></li>"
        for r in result.requests
    )
    return f'<ul class="gra-requests">{items}</ul>' if items else ""


def items_html(result: AgentResult) -> tuple[str, str]:
    tasks = "".join(
        f'<div class="gra-item"><b>{esc(DEPARTMENT_NAMES.get(t.department, t.department))}</b> · {esc(t.title)}'
        + (f"<small>{esc(t.details)}</small>" if t.details else "")
        + "</div>"
        for t in result.tasks
    )
    actions = "".join(
        f'<div class="gra-item gra-approval"><b>{esc(ACTION_NAMES.get(a.action_type, a.action_type))}</b> · '
        f"needs manager approval<small>{esc(a.reason)}</small></div>"
        for a in result.actions
    )
    return tasks, actions


def result_panel(result: AgentResult, request_id: str, email: dict, key: str, page: str):
    """Steps, requests, the editable draft with citation badges, proposed tasks and approval buttons."""
    if result.outcome in ("greeting", "off_topic", "cap", "error"):
        (st.info if result.outcome in ("greeting", "off_topic") else st.warning)(result.message, icon=":material/info:")
        return
    if result.escalate:
        reasons = "; ".join(r.removeprefix("model: ") for r in result.escalation_reasons)
        st.html(
            '<div class="gra-note"><b>Escalated to a manager</b>'
            f"{esc(reasons)}<small>The draft is a polite holding reply. A manager should contact the guest "
            "personally.</small></div>"
        )
    if result.fallback_reason:
        st.warning(
            "The assistant couldn't finish, so this is a safe holding reply and a task for the front desk. "
            "Please reply personally.",
            icon=":material/support:",
        )
    shown = sum(1 for s in result.steps if s.kind != "model")
    st.markdown(f"**What the agent did** · {shown} steps in {result.latency_s:.1f} s")
    timeline(result)
    req = requests_list(result)
    if req:
        st.markdown(f"**Requests found** ({len(result.requests)})")
        st.html(req)

    review = desk().reviews.get(request_id)
    if review is None:
        review = Review(
            request_id=request_id,
            to=email["from"],
            subject=email.get("subject", ""),
            draft=result.reply,
            tasks=list(result.tasks),
            actions=list(result.actions),
            property=email["property"],
            escalate=result.escalate,
        )
        desk().reviews[request_id] = review

    st.markdown("**Draft reply**")
    titles = {c["id"]: c["title"] for c in result.citations}
    editing = st.session_state.get(f"edit_{key}", False) and review.status == "pending"
    if editing:
        st.text_area("Edit the reply before sending", value=review.draft, key=f"text_{key}", height=260, max_chars=4000)
    else:
        st.html(draft_html(review.final_text if review.status == "approved" else review.draft, titles))
    if result.citations:
        with st.expander(f"Sources cited ({len(result.citations)})"):
            for c in result.citations:
                st.markdown(
                    f"**[{c['id']}] {c['title']}**" + (f" · effective {c['effective']}" if c.get("effective") else "")
                )
                st.text(c.get("text") or "")
    tasks, actions = items_html(result)
    if tasks:
        st.markdown(f"**Proposed tasks** ({len(result.tasks)}) · created only if you approve")
        st.html(tasks)
    if actions:
        st.markdown(f"**Needs manager approval** ({len(result.actions)}) · never done or promised by the agent")
        st.html(actions)
    checks = result.flags.get("ungrounded_facts") or []
    if checks:
        st.warning(
            "Check before sending: " + ", ".join(checks) + " not found in the booking, availability or policy results.",
            icon=":material/fact_check:",
        )
    if result.flags.get("forbidden_promises_removed"):
        st.info("A sentence promising something only a manager can approve was replaced.", icon=":material/gavel:")
    approval_buttons(review, key, page)


def approval_buttons(review: Review, key: str, page: str):
    if review.status == "approved":
        st.success(
            "Sent (simulated): it's in the Outbox. Proposed tasks are on the task board.",
            icon=":material/outgoing_mail:",
        )
        st.page_link("views/outbox.py", label="Open Outbox and tasks", icon=":material/outbox:")
        return
    if review.status == "rejected":
        st.info(f"Rejected: {review.reason}. Nothing was sent and no task was created.", icon=":material/block:")
        return
    editing = st.session_state.get(f"edit_{key}", False)
    c1, c2, c3 = st.columns(3)
    send = c1.button(
        "Approve & send (simulated)", key=f"approve_{key}", type="primary", icon=":material/send:", width="stretch"
    )
    if c2.button("Done editing" if editing else "Edit", key=f"editbtn_{key}", icon=":material/edit:", width="stretch"):
        if editing:
            review.draft = st.session_state.get(f"text_{key}", review.draft)
        st.session_state[f"edit_{key}"] = not editing
        st.rerun()
    with c3.popover("Reject", icon=":material/block:", width="stretch"):
        reason = st.text_input("Reason (required)", key=f"reason_{key}", max_chars=200)
        if st.button("Reject draft", key=f"reject_{key}"):
            try:
                record = reject(desk(), review, reason)
                log_decision({**record, "session_id": session_id()})
                st.rerun()
            except ApprovalError as exc:
                st.error(str(exc))
    if send:
        text = st.session_state.get(f"text_{key}", review.draft) if editing else review.draft
        try:
            record = approve(desk(), review, text)
            log_decision({**record, "session_id": session_id()})
            st.session_state[f"edit_{key}"] = False
            st.rerun()
        except ApprovalError as exc:
            st.error(str(exc))
    st.caption("Demo: nothing is ever emailed. Approving puts the reply in this session's Outbox.")
