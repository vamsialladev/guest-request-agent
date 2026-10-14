"""Inbox (main page): pick a sample guest email, run the agent, review the draft, approve, edit or reject."""

import streamlit as st

from src.config import MAX_EMAILS_PER_SESSION, SIM_TODAY
from src.inbox import load_inbox, rows, to_email
from src.service import log_reused, process
from src.tools import PROPERTY_NAMES, fmt_date
from views import components as ui

b = ui.brand()
ui.header(
    b.name,
    "Pick a guest email. The agent finds every request, checks the booking, availability and hotel policy, drafts a "
    "cited reply and proposes tasks. You approve, edit or reject.",
    f"{b.hotel_group} · Inbox · simulated today: {fmt_date(SIM_TODAY)}",
)
ui.warm_up()
no_key = ui.secrets_missing()

items = load_inbox()
by_id = {i["id"]: i for i in items}
results, desk = ui.results(), ui.desk()

f1, f2, f3 = st.columns([1.2, 1.2, 1], vertical_alignment="bottom")
prop = f1.selectbox(
    "Property", ["all", *PROPERTY_NAMES], format_func=lambda p: "All properties" if p == "all" else PROPERTY_NAMES[p]
)
status = f2.selectbox(
    "Status",
    ["all", "new", "drafted", "escalated", "approved", "rejected"],
    format_func=lambda s: {
        "all": "Any status",
        "new": "New",
        "drafted": "Draft ready",
        "escalated": "Escalated",
        "approved": "Sent",
        "rejected": "Rejected",
    }[s],
)
escalated_only = f3.toggle("Escalated only", help="Flagged by the escalation rules or by the agent")
shown = rows(
    items, results, desk.reviews, None if prop == "all" else prop, None if status == "all" else status, escalated_only
)
st.caption(f"{len(shown)} of {len(items)} emails · synthetic guests, fictional hotel group · select a row")
event = st.dataframe(
    shown,
    column_order=("id", "status", "escalated", "from", "subject", "property", "received"),
    column_config={
        "id": st.column_config.TextColumn("ID", width=45),
        "status": st.column_config.TextColumn("Status", width="small"),
        "escalated": st.column_config.TextColumn("⚑", width=30, help="Escalation"),
        "from": "From",
        "subject": st.column_config.TextColumn("Subject", width="large"),
        "property": st.column_config.TextColumn("Inbox", width="small"),
        "received": st.column_config.TextColumn("Received", width="small"),
    },
    hide_index=True,
    width="stretch",
    height=320,
    on_select="rerun",
    selection_mode="single-row",
    key=f"inbox_{prop}_{status}_{escalated_only}",
)
picked = event.selection.rows[0] if event and event.selection.rows else None
selected_id = shown[picked]["id"] if picked is not None and picked < len(shown) else st.session_state.get("inbox_open")
if selected_id not in by_id:
    ui.empty_state(
        "Select an email above",
        "Try E01 (three requests in one email), E05 (an angry refund demand) or E14 (a prompt-injection attempt).",
    )
    ui.footer()
    st.stop()
st.session_state.inbox_open = selected_id
item = by_id[selected_id]

st.subheader(item.get("subject") or "(no subject)")
ui.email_card(
    item["from"],
    item.get("name", ""),
    item.get("subject", ""),
    item["body"],
    item["property"],
    item.get("received", ""),
)


def run(item: dict, reuse: bool):
    shared = ui.shared_results()
    if reuse and item["id"] in shared:
        original, original_id = shared[item["id"]]
        result, record = log_reused(
            original,
            to_email(item),
            item["property"],
            original_id=original_id,
            session_id=ui.session_id(),
            first=ui.is_first(),
            email_id=item["id"],
        )
        results[item["id"]] = (result, record["request_id"], original_id)
        return
    with st.spinner("Reading the email, checking the booking and policy, drafting a reply…"):
        result, record = process(
            to_email(item),
            item["property"],
            source="inbox",
            session_id=ui.session_id(),
            first=ui.is_first(),
            email_id=item["id"],
            session_count=ui.emails_sent_to_agent(),
            daily_counter=ui.daily_counter(),
        )
    if result.api_calls:
        ui.count_email()
    results[item["id"]] = (result, record["request_id"], None)
    if result.outcome in ("drafted", "escalated") and not result.fallback_reason:
        shared[item["id"]] = (result, record["request_id"])


done = results.get(item["id"])
if done is None:
    reused = item["id"] in ui.shared_results()
    label = "Show the agent's result" if reused else "Run the agent on this email"
    if st.button(label, type="primary", icon=":material/smart_toy:", disabled=no_key and not reused):
        run(item, reuse=True)
        st.rerun()
    st.caption(
        f"Each session can run the agent on {MAX_EMAILS_PER_SESSION} emails. Results already produced for a "
        "sample email are reused, so most clicks are instant and free."
    )
else:
    result, request_id, reused_from = done
    if reused_from:
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.caption("This result was produced earlier for this sample email and is reused, so the demo stays free.")
        if c2.button("Run again", icon=":material/refresh:", disabled=no_key):
            desk.reviews.pop(request_id, None)
            results.pop(item["id"], None)
            ui.shared_results().pop(item["id"], None)
            run(item, reuse=False)
            st.rerun()
    ui.result_panel(result, request_id, item, key=f"{item['id']}_{request_id}", page="Inbox")
ui.footer()
