"""Caps, greetings and the request log: one record for every outcome, and no secret in any record."""

import json

import pytest
from fakes import FakeClient, api_error, draft, tool

import src.agent
from src.agent import Email
from src.limits import DailyCounter
from src.service import log_reused, process
from src.usage import decisions_file, log_decision, read_jsonl, requests_file

GUEST = Email("elena.marsh@example.com", "Dog", "Can we bring our dog?", "Elena Marsh")


class NoCalls:
    """Fails the test if the API is called."""

    class messages:  # noqa: N801
        @staticmethod
        def create(**_):
            raise AssertionError("the API must not be called")


@pytest.fixture
def db(store, monkeypatch):
    monkeypatch.setattr(src.agent, "ToolContext", _ctx_with(store))


def _ctx_with(store):
    from src.tools import ToolContext

    def make(**kw):
        return ToolContext(store=store, **kw)

    return make


@pytest.mark.parametrize(
    "body, outcome",
    [("hi", "greeting"), ("what's the capital of france", "off_topic"), ("", "off_topic"), ("x" * 5000, "off_topic")],
)
def test_visitor_text_that_isnt_an_email_never_calls_the_api(body, outcome):
    result, record = process(Email("visitor@example.com", "", body), "beach-resort", source="write", client=NoCalls())
    assert result.outcome == outcome and result.message and record["api_calls"] == 0
    assert read_jsonl(requests_file())[-1]["outcome"] == outcome


def test_session_and_daily_caps_stop_before_the_api(tmp_path):
    result, record = process(GUEST, "beach-resort", source="inbox", session_count=10, client=NoCalls())
    assert result.outcome == "cap" and record["error"] == "session_cap"
    counter = DailyCounter(tmp_path / "daily.json", limit=1)
    assert counter.try_consume()
    result, record = process(GUEST, "beach-resort", source="inbox", daily_counter=counter, client=NoCalls())
    assert result.outcome == "cap" and record["error"] == "daily_cap"


def test_a_full_record_is_logged_for_a_drafted_email(db):
    client = FakeClient(
        [
            [tool("find_booking", {}), tool("search_policy", {"question": "dog"})],
            [draft("The fee is $75 per stay [P1].")],
        ]
    )
    result, record = process(
        GUEST, "beach-resort", source="inbox", session_id="s1", first=True, email_id="E01", client=client
    )
    logged = read_jsonl(requests_file())[-1]
    assert logged["request_id"] == record["request_id"] and logged["time"]
    for key in (
        "schema_version",
        "session_id",
        "property",
        "email",
        "outcome",
        "steps",
        "draft",
        "raw_draft",
        "requests",
        "tasks",
        "actions",
        "checks",
        "model",
        "latency_s",
        "tokens_in",
        "tokens_out",
        "cost_usd",
    ):
        assert key in logged, key
    assert logged["email_id"] == "E01" and logged["first"] is True and logged["model"] == "claude-haiku-5-5"
    tools = [s for s in logged["steps"] if s["kind"] == "tool"]
    assert [s["tool"] for s in tools] == ["find_booking", "search_policy"] and tools[1]["args"] == {"question": "dog"}
    assert logged["cost_usd"] == pytest.approx((2000 * 0.10 + 200 * 0.50) / 1e6)
    assert logged["citations"][0]["id"] == "P1"


def test_api_failure_is_logged_with_a_fallback(db):
    result, record = process(GUEST, "beach-resort", source="inbox", client=FakeClient(error=api_error(500)))
    assert result.outcome == "fallback" and record["error"] == "server_error"
    assert "fallback" in record["error_message"] and read_jsonl(requests_file())[-1]["outcome"] == "fallback"


def test_unexpected_crash_is_logged_as_an_error(monkeypatch):
    import src.service

    monkeypatch.setattr(src.service, "run_agent", lambda *a, **k: 1 / 0)
    result, record = process(GUEST, "beach-resort", source="inbox")
    assert result.outcome == "error" and record["error"] == "unexpected"
    assert record["error_message"].startswith("ZeroDivisionError")


def test_no_secret_reaches_any_log_record(db, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse-battery-staple")
    leaky = Email(
        "x@example.com", "keys", "my key is sk-ant-api03-SECRET and the password correct-horse-battery-staple"
    )
    process(leaky, "beach-resort", source="write", client=FakeClient([[draft("Thanks for your email. sk-ant-xyz")]]))
    log_decision({"request_id": "r", "decision": "approved", "final_text": "correct-horse-battery-staple"})
    text = requests_file().read_text(encoding="utf-8") + decisions_file().read_text(encoding="utf-8")
    assert "sk-ant-api03-SECRET" not in text and "correct-horse-battery-staple" not in text
    assert "sk-ant-test-0000" not in text and "[redacted]" in text


def test_reused_result_gets_its_own_record_without_cost(db):
    client = FakeClient([[draft("The team will confirm.")]])
    result, record = process(GUEST, "beach-resort", source="inbox", client=client, log=False)
    reused, again = log_reused(
        result, GUEST, "beach-resort", original_id=record["request_id"], session_id="s2", first=True, email_id="E01"
    )
    assert again["request_id"] != record["request_id"] and again["reused_from"] == record["request_id"]
    assert again["api_calls"] == 0 and again["cost_usd"] == 0.0 and reused.reply == result.reply
    assert json.loads(requests_file().read_text(encoding="utf-8").splitlines()[-1])["reused_from"]
