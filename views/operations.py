"""Owner-only Operations page (Project 4): requests, errors, latency, cost per day, refusals and escalations, budget
status, log storage, the kill switch and staff reports. Behind the same sign-in as the Admin page; no secret values,
no connection details and no question text beyond the staff reports (already redacted before storage)."""

import time

import streamlit as st

from src import store
from src.admin import still_signed_in
from src.config import (
    ADMIN_IDLE_MINUTES,
    BUDGET_COST_PER_1000,
    BUDGET_P95_S,
    LOG_DIR,
    model_calls_enabled,
    staff_password,
)
from src.errors import errors_file
from src.operations import budget_label, summary
from src.usage import read_jsonl, requests_file
from views import components as ui

gate = st.session_state.get("admin_gate")
if not gate or not still_signed_in(gate, time.time(), ADMIN_IDLE_MINUTES * 60):
    ui.header("Operations", "Sign in on the Admin page first.", "Owner only")
    st.page_link("views/admin.py", label="Go to Admin sign-in", icon=":material/lock_open:")
    st.stop()

ui.header("Operations", "Is the agent up, fast, affordable and safe? From the stored request log.", "Owner only")

usage, errors = read_jsonl(requests_file()), read_jsonl(errors_file())
reports = read_jsonl(LOG_DIR / "reports.jsonl")
days = st.segmented_control("Window", [1, 7, 30], default=7, format_func=lambda d: f"{d} day{'s' if d > 1 else ''}")
s = summary(usage, errors, days or 7, BUDGET_P95_S, BUDGET_COST_PER_1000)

p95_ok, cost_ok = s["budgets"]["p95_s"]["ok"], s["budgets"]["cost_per_1000"]["ok"]
if not model_calls_enabled():
    st.error(
        "Kill switch is ON: model calls are paused. Emails get the safe holding reply and a staff task.",
        icon=":material/block:",
    )
if p95_ok is False or cost_ok is False:
    st.warning(
        "Over budget: see Budgets below and the runbook for a cost spike or slow drafts.", icon=":material/warning:"
    )

ui.tiles(
    [
        (f"{s['requests']}", "Requests", "emails processed, greetings excluded"),
        (
            f"{s['errors']}",
            "Errors",
            ui.fmt_pct(s["error_rate"]) + " of requests" if s["error_rate"] is not None else "no requests",
        ),
        (
            f"{ui.fmt_seconds(s['p50_s'])} / {ui.fmt_seconds(s['p95_s'])}",
            "p50 / p95",
            "whole agent run, API calls only",
        ),
        (
            f"${s['cost_usd']:.4f}",
            "Cost",
            f"${s['cost_per_1000']:.2f} per 1,000" if s["cost_per_1000"] is not None else "no API calls",
        ),
        (f"{s['refusals']}", "Fallbacks", "holding reply + staff task"),
        (f"{s['escalations']}", "Escalations", "flagged for a manager"),
    ]
)

st.subheader("Budgets")
st.markdown(
    f"- **p95 latency:** {budget_label(s['budgets']['p95_s'], '{:.2f} s')}\n"
    f"- **Cost per 1,000 requests:** {budget_label(s['budgets']['cost_per_1000'], '${:.2f}')}\n"
)
st.caption("Budgets are set with BUDGET_P95_S and BUDGET_COST_PER_1000; CI checks the same budgets on every eval run.")

st.subheader("Per day")
if s["per_day"]:
    st.dataframe(s["per_day"], hide_index=True, width="stretch")
else:
    ui.empty_state("No requests in this window", "Numbers appear after the first question.")

st.subheader("Staff reports")
open_reports = [r for r in reports if r.get("status", "open") == "open"]
if open_reports:
    st.dataframe(
        [{k: r.get(k) for k in ("time", "reason", "question", "note", "request_id")} for r in reversed(open_reports)],
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("No reports. Staff can report a draft for review from the sidebar after signing in.")

st.subheader("System")
st_status = store.status()
storage = {
    "files": "Not configured: temporary files (reset when the app restarts)",
    "sqlite": "SQLite database",
    "postgres": "Postgres database",
    "invalid": "DATABASE_URL is not a postgres:// or sqlite:/// URL",
}[st_status["backend"]]
rows = [
    ("Log storage", storage + ("" if st_status["ok"] else f" · not reachable ({st_status['error']})")),
    ("Stored records", ", ".join(f"{k} {v}" for k, v in sorted(st_status["counts"].items())) or "none"),
    (
        "Retention",
        f"{st_status.get('retention_days', 30)} days, purged daily" if st_status["configured"] else "until restart",
    ),
    ("Kill switch", "ON (model calls paused)" if not model_calls_enabled() else "off"),
    ("Staff sign-in", "configured" if staff_password() else "not configured (Demo mode only)"),
]
st.dataframe([{"Item": a, "Status": b} for a, b in rows], hide_index=True, width="stretch")
