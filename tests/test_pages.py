"""Every page runs for real (Streamlit AppTest, no browser, no API: a scripted fake model).

- each page renders; an exception on any page shows the friendly message, never a traceback
- Inbox: run the agent, see steps and the draft; nothing is sent or created until Approve
- Write your own email: greetings get an instant reply without the API
- Admin: locked by default with no log data; unlocked, it lists every request; downloads are admin-only
"""

import time

import pytest
from fakes import FakeClient, draft, tool
from streamlit.testing.v1 import AppTest

import codeguard
import src.agent
import src.errors as errors
from src.admin import GateState
from src.config import ROOT
from src.errors import PAGE_ERROR
from src.usage import read_jsonl, requests_file
from views import components

PAGES = {
    "views/inbox.py": "Inbox",
    "views/write.py": "Write your own email",
    "views/outbox.py": "Outbox and tasks",
    "views/how_it_works.py": "How it works",
    "views/about.py": "Disclaimer and privacy",
    "views/admin.py": "Admin",
}


def scripted():
    return FakeClient(
        [
            [
                tool("find_booking", {}),
                tool("search_policy", {"question": "dog pet fee"}),
                tool("propose_task", {"department": "concierge", "title": "Book MIA pickup"}),
            ],
            [
                draft(
                    "Dear Elena,\n\nDogs up to 40 lbs are welcome; the fee is $75 per stay [P1].\n\nGuest Services",
                    requests=[
                        {"summary": "Dog", "kind": "policy", "status": "answered"},
                        {"summary": "Pickup", "kind": "service", "status": "task_proposed"},
                    ],
                )
            ],
        ]
    )


@pytest.fixture
def app(monkeypatch, store, tmp_path):
    monkeypatch.setenv("ADMIN_PASSWORD", "test-only-password")
    monkeypatch.setenv(codeguard.STAMP_KEY, codeguard.code_stamp(ROOT))  # keep the patched modules
    monkeypatch.setattr(src.agent, "make_client", scripted)
    original = src.agent.ToolContext
    monkeypatch.setattr(src.agent, "ToolContext", lambda **kw: original(store=store, **kw))
    monkeypatch.setattr(components, "daily_counter", lambda: _Counter())
    monkeypatch.setattr(errors, "ERRORS_FILE", tmp_path / "errors.jsonl")
    components.shared_results.clear()  # results reused across visitors would leak between tests
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60), tmp_path


class _Counter:
    def try_consume(self):
        return True

    def used(self):
        return 0


def open_page(at, path):
    at.run()
    if path != "views/inbox.py":
        at.switch_page(path).run()
    return at


@pytest.mark.parametrize("path", PAGES)
def test_every_page_renders_without_errors(app, path):
    at, logs = app
    open_page(at, path)
    assert not at.exception and not [e for e in at.error if e.value == PAGE_ERROR]
    assert not (logs / "errors.jsonl").exists()


@pytest.mark.parametrize("path", PAGES)
def test_an_exception_on_any_page_shows_the_friendly_message(app, monkeypatch, path):
    at, logs = app

    def broken(*args, **kwargs):
        raise RuntimeError("simulated failure with key sk-ant-not-a-real-key")

    monkeypatch.setattr(components, "header", broken)
    open_page(at, path)
    assert not at.exception and [e.value for e in at.error] == [PAGE_ERROR]
    record = read_jsonl(logs / "errors.jsonl")[-1]
    assert "sk-ant-not-a-real-key" not in str(record)


def test_inbox_run_review_and_approve(app):
    at, _ = app
    at.session_state["inbox_open"] = "E01"
    at.run()
    assert any("Arriving Friday" in s.value for s in at.subheader)
    run_button = next(b for b in at.button if b.label == "Run the agent on this email")
    run_button.click().run()
    assert not at.exception
    labels = [e.label for e in at.expander]
    assert any("Found booking BR-1042" in label for label in labels)
    assert any("cited P1 ✓" in label for label in labels)
    desk = at.session_state["desk"]
    assert desk.counts() == {"sent": 0, "tasks": 0, "manager": 0}  # nothing happens before approval
    record = read_jsonl(requests_file())[-1]
    assert record["email_id"] == "E01" and record["source"] == "inbox" and record["outcome"] == "drafted"
    next(b for b in at.button if b.label == "Approve & send (simulated)").click().run()
    desk = at.session_state["desk"]
    assert desk.counts() == {"sent": 1, "tasks": 1, "manager": 0}
    assert "[P1]" not in desk.outbox[0]["body"]
    from src.usage import decisions_file

    assert read_jsonl(decisions_file())[-1]["decision"] == "approved"
    at.switch_page("views/outbox.py").run()
    assert not at.exception and any("Re: Arriving Friday" in e.label for e in at.expander)


def test_write_page_greeting_is_instant_and_free(app, monkeypatch):
    at, _ = app

    def no_api():
        raise AssertionError("the API must not be called")

    monkeypatch.setattr(src.agent, "make_client", no_api)
    open_page(at, "views/write.py")
    at.text_area(key="write_body").input("hello").run()
    next(b for b in at.button if b.label == "Run the agent").click().run()
    assert not at.exception and any("drafts replies to guest emails" in i.value for i in at.info)
    assert read_jsonl(requests_file())[-1]["outcome"] == "greeting"


def test_missing_api_key_shows_a_friendly_message(app, monkeypatch):
    at, _ = app
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at.run()
    assert not at.exception and any("isn't configured" in w.value for w in at.warning)


def test_locked_admin_shows_no_log_data_or_downloads(app):
    at, _ = app
    open_page(at, "views/admin.py")
    assert any("Owner sign-in" in h.value for h in at.get("html")) or at.text_input
    assert not at.get("download_button") and not at.dataframe


def test_wrong_password_is_rejected(app, monkeypatch):
    import src.admin

    monkeypatch.setattr(src.admin, "FAILURE_DELAY_SECONDS", 0)
    at, _ = app
    open_page(at, "views/admin.py")
    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert any("Incorrect password" in e.value for e in at.error)


def test_unlocked_admin_lists_requests_with_downloads(app):
    at, _ = app
    at.session_state["inbox_open"] = "E01"
    at.run()
    next(b for b in at.button if b.label == "Run the agent on this email").click().run()
    at.session_state["admin_gate"] = GateState(unlocked=True, last_active=time.time())
    at.switch_page("views/admin.py").run()
    assert not at.exception
    assert len(at.dataframe) == 1 and at.dataframe[0].value.shape[0] == 1
    assert len(at.get("download_button")) >= 4


@pytest.mark.parametrize("path", [p for p in PAGES if p != "views/admin.py"])
def test_no_downloads_on_visitor_pages(app, path):
    at, _ = app
    open_page(at, path)
    assert not at.get("download_button")


def test_inbox_link_opens_one_sample_email(app):
    at, _ = app
    at.query_params["email"] = "E14"
    at.run()
    assert not at.exception and any("Urgent: system update" in s.value for s in at.subheader)


def test_write_page_counts_the_run_it_just_made(app):
    at, _ = app
    open_page(at, "views/write.py")
    at.text_area(key="write_body").input("Can we bring our dog?").run()
    next(b for b in at.button if b.label == "Run the agent").click().run()
    assert not at.exception and any("9 of 10 emails left" in c.value for c in at.caption)
