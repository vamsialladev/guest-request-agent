"""Project 4: Operations numbers and budgets, the kill switch, Demo mode / Staff sign-in and the Operations page."""

import time
from datetime import date

from fakes import FakeClient, draft
from streamlit.testing.v1 import AppTest

import codeguard
import src.errors as errors
from src import roles
from src.admin import GateState
from src.agent import Email, run_agent
from src.config import ROOT
from src.operations import budget_label, summary
from src.usage import append_jsonl, now_iso, requests_file

TODAY = date(2026, 10, 15)


def rec(outcome, latency=4.0, cost=0.0013, calls=2, day="2026-10-15", **kw):
    return {
        "time": f"{day}T10:00:00+00:00",
        "outcome": outcome,
        "latency_s": latency,
        "cost_usd": cost,
        "api_calls": calls,
        **kw,
    }


ROWS = [
    rec("drafted", 4.0),
    rec("escalated", 6.0, escalate=True),
    rec("fallback", 9.0),
    rec("off_topic", None, None, 0),
    rec("greeting", None, None, 0),
    rec("error", None, None, 0),
    rec("drafted", 30.0, day="2026-09-01"),
]


def test_summary_counts_latency_cost_escalations_and_fallbacks():
    s = summary(ROWS, [], days=7, p95_budget=12.0, cost_budget=2.0, today=TODAY)
    assert s["requests"] == 5 and s["errors"] == 1 and s["refusals"] == 1 and s["escalations"] == 1
    assert s["p50_s"] == 6.0 and s["p95_s"] == 9.0 and s["cost_per_1000"] == 1.3
    assert s["budgets"]["p95_s"]["ok"] and s["budgets"]["cost_per_1000"]["ok"]


def test_budgets_can_fail():
    s = summary(ROWS, [], days=7, p95_budget=8.0, cost_budget=1.0, today=TODAY)
    assert s["budgets"]["p95_s"]["ok"] is False and s["budgets"]["cost_per_1000"]["ok"] is False
    assert budget_label(s["budgets"]["cost_per_1000"], "${:.2f}") == "Over budget: $1.30 (budget $1.00)"


def test_kill_switch_gives_the_safe_holding_reply_without_a_model_call(store, monkeypatch):
    monkeypatch.setenv("KILL_SWITCH", "on")
    client = FakeClient([[draft("never used")]])
    email = Email("elena.marsh@example.com", "Dog", "Can we bring our dog?", "Elena Marsh")
    result = run_agent(email, "beach-resort", client=client, store=store)
    assert client.requests == [] and result.api_calls == 0
    assert result.outcome == "fallback" and result.fallback_reason == "paused"
    assert any(s.name == "kill_switch" for s in result.steps) and result.tasks


def test_staff_role_rules():
    gate = GateState()
    assert roles.role(gate, 0, 60) == roles.DEMO
    assert roles.staff_attempt(gate, "right", "right", 1) == (True, None)
    assert roles.role(gate, 30, 60) == roles.STAFF and roles.role(gate, 500, 60) == roles.DEMO


def app_test(monkeypatch, tmp_path, staff=True):
    monkeypatch.setenv("ADMIN_PASSWORD", "test-only-password")
    if staff:
        monkeypatch.setenv("STAFF_PASSWORD", "test-only-staff")
    else:
        monkeypatch.delenv("STAFF_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(codeguard.STAMP_KEY, codeguard.code_stamp(ROOT))
    monkeypatch.setattr(errors, "ERRORS_FILE", tmp_path / "errors.jsonl")
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)


def test_operations_page_is_owner_only_and_shows_budgets(monkeypatch, tmp_path):
    at = app_test(monkeypatch, tmp_path)
    at.run()
    at.switch_page("views/operations.py").run()
    assert not at.exception and not at.error and not at.dataframe
    append_jsonl(requests_file(), rec("drafted", 5.0) | {"time": now_iso()})
    at.session_state["admin_gate"] = GateState(unlocked=True, last_active=time.time())
    at.switch_page("views/operations.py").run()
    assert not at.exception and not at.error
    assert "Within budget: 5.00 s (budget 12.00 s)" in " ".join(m.value for m in at.markdown)


def test_demo_mode_and_staff_sign_in(monkeypatch, tmp_path):
    at = app_test(monkeypatch, tmp_path)
    at.run()
    assert "Demo mode" in " ".join(c.value for c in at.sidebar.caption)
    at.sidebar.text_input[0].input("test-only-staff")
    next(b for b in at.button if b.label == "Sign in").click().run()
    assert not at.exception and "Signed in as staff" in " ".join(c.value for c in at.sidebar.caption)


def test_no_staff_password_means_demo_mode_only(monkeypatch, tmp_path):
    at = app_test(monkeypatch, tmp_path, staff=False)
    at.run()
    assert not [t for t in at.sidebar.text_input if t.label == "Staff password"]
