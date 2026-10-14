import csv
import io

from src.errors import error_record, is_control_flow, record_error
from src.monitoring import alerts, csv_safe, format_uptime, health, recent_errors, to_csv
from src.usage import read_jsonl

TODAY = "2026-10-10"
USAGE = [
    {"time": "2026-10-09T10:00:00+00:00", "turn_id": "a", "property": "beach-resort", "cost_usd": 0.5},
    {
        "time": "2026-10-10T10:00:00+00:00",
        "turn_id": "b",
        "property": "beach-resort",
        "cost_usd": 0.0002,
        "tokens_in": 900,
        "refused": False,
    },
    {"time": "2026-10-10T11:00:00+00:00", "turn_id": "c", "property": "mountain-lodge", "cost_usd": 0.0003},
    {
        "time": "2026-10-10T12:00:00+00:00",
        "turn_id": "d",
        "property": "mountain-lodge",
        "outcome": "error",
        "error": "rate_limit",
    },
]
ERRORS = [
    {"time": "2026-10-09T09:00:00+00:00", "page": "Insights", "type": "unexpected", "message": "old"},
    {"time": "2026-10-10T12:00:00+00:00", "page": "Assistant", "type": "rate_limit", "message": "429"},
]


def test_uptime_is_readable():
    assert format_uptime(59) == "0 min" and format_uptime(3 * 3600 + 120) == "3 h 2 min"
    assert format_uptime(2 * 86400 + 3600) == "2 d 1 h" and format_uptime(-5) == "0 min"


def test_health_counts_only_today():
    h = health(USAGE, ERRORS, TODAY, now=7200, started=0, daily_used=2, daily_cap=200)
    assert h["emails_today"] == 2 and h["errors_today"] == 1 and h["events_today"] == 3
    assert round(h["cost_today"], 4) == 0.0005 and h["uptime"] == "2 h 0 min"
    assert round(h["error_rate_today"], 2) == 0.33


def test_no_alert_below_the_minimum_number_of_events():
    h = health(USAGE, ERRORS, TODAY, now=0, started=0, daily_used=2, daily_cap=200)
    assert alerts(h, error_rate=0.2, min_events=5, daily_cost=1.0) == []


def test_error_rate_cost_and_cap_alerts():
    h = health(USAGE, ERRORS, TODAY, now=0, started=0, daily_used=190, daily_cap=200)
    warnings = alerts(h, error_rate=0.2, min_events=3, daily_cost=0.0001)
    assert len(warnings) == 3
    assert "Error rate today is 33%" in warnings[0] and "Estimated cost today" in warnings[1]
    assert "190/200" in warnings[2]


def test_recent_errors_newest_first():
    assert [e["message"] for e in recent_errors(ERRORS)] == ["429", "old"]


def test_csv_export_blocks_formula_injection():
    text = to_csv([{"question": '=HYPERLINK("http://x")', "cost": 0.1, "none": None}], ["question", "cost", "none"])
    header, row = list(csv.reader(io.StringIO(text)))
    assert header == ["question", "cost", "none"] and row == ['\'=HYPERLINK("http://x")', "0.1", ""]
    assert csv_safe("+1") == "'+1" and csv_safe("@x") == "'@x" and csv_safe("ok") == "ok"


def test_csv_of_all_columns_when_none_given():
    assert to_csv([{"b": 1, "a": 2}]).splitlines()[0] == "a,b"


def test_error_record_is_short_masked_and_has_no_traceback():
    exc = RuntimeError("key sk-ant-not-a-real-key failed\n  at line 3 " + "x" * 400)
    rec = error_record("Assistant", exc)
    assert rec["page"] == "Assistant" and rec["error"] == "RuntimeError" and rec["type"] == "unexpected"
    assert "sk-ant-***" in rec["message"] and "not-a-real-key" not in rec["message"]
    assert len(rec["message"]) <= 160 and "\n" not in rec["message"]


def test_record_error_appends_to_the_log(tmp_path):
    path = tmp_path / "errors.jsonl"
    record_error("Insights", ValueError("bad"), path=path)
    record_error("Admin", KeyError("x"), path=path)
    assert [r["page"] for r in read_jsonl(path)] == ["Insights", "Admin"]


def test_control_flow_exceptions_pass_through_the_boundary():
    from streamlit.runtime.scriptrunner_utils.exceptions import RerunException, StopException

    assert is_control_flow(StopException()) and is_control_flow(RerunException(None))
    assert is_control_flow(KeyboardInterrupt()) and not is_control_flow(RuntimeError("x"))


def test_first_email_success_counts_each_session_once():
    from src.monitoring import first_email_success

    rows = [
        {"session_id": "s1", "first": True, "outcome": "drafted"},
        {"session_id": "s1", "first": False, "outcome": "error"},
        {"session_id": "s2", "first": True, "outcome": "greeting"},
        {"session_id": "s3", "first": True, "outcome": "fallback"},
        {"session_id": "s4", "first": True, "outcome": "drafted", "checks": {"ungrounded_facts": ["$99"]}},
        {"first": True, "outcome": "drafted"},  # no session id: ignored
    ]
    assert first_email_success(rows) == {"sessions": 4, "ok": 2, "rate": 0.5}
    assert first_email_success([])["rate"] is None
