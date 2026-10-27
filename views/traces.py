"""Owner-only Traces page: the shared ops view (hotel-ai-platform) for this app. Every email's trace as a
step-by-step waterfall (guardrails, triage, booking lookup, each model turn and tool call), error rate, p50/p95, cost
against the caps, guardrail blocks, feedback and system health. Behind the same sign-in as the Admin page."""

import time

import streamlit as st
from hotelplatform import admin_ui

from src import ops
from src.admin import still_signed_in
from src.config import ADMIN_IDLE_MINUTES
from views import components as ui

gate = st.session_state.get("admin_gate")
if not gate or not still_signed_in(gate, time.time(), ADMIN_IDLE_MINUTES * 60):
    ui.header("Traces", "Sign in on the Admin page first.", "Owner only")
    st.page_link("views/admin.py", label="Go to Admin sign-in", icon=":material/lock_open:")
    st.stop()

st.caption('Paste a guest\'s "Reference: ..." into Trace reference to find the email it came from.')
admin_ui.render(
    ops.store(),
    app_title="Guest Request Agent",
    version=ops.running_version(),
    dependencies=ops.dependencies,
    require_gate=False,
    title="Traces",
    **ops.caps(),
)
