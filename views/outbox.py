"""Outbox and tasks: what this session 'sent' (simulated), the task board and the manager queue."""

import streamlit as st

from src.display import esc
from src.tools import ACTION_NAMES, DEPARTMENT_NAMES
from views import components as ui

ui.header(
    "Outbox and tasks",
    "Only approved drafts appear here. Nothing is ever emailed: this outbox lives in your browser session.",
    "This session",
)
d = ui.desk()
counts = d.counts()
ui.tiles(
    [
        (str(counts["sent"]), "Replies sent (simulated)", "Approved by you"),
        (str(counts["tasks"]), "Open tasks", "Created on approval"),
        (str(counts["manager"]), "Waiting for a manager", "Refunds, upgrades, changes"),
    ]
)
if st.button("New session", icon=":material/restart_alt:", help="Clears the outbox, tasks and drafts"):
    ui.new_session()
    st.rerun()

st.subheader("Outbox")
if not d.outbox:
    ui.empty_state("No replies yet", "Approve a draft on the Inbox or Write your own email page and it appears here.")
for item in reversed(d.outbox):
    title = f"To {item['to']} · {item['subject']}" + (" · edited" if item["edited"] else "")
    with st.expander(title):
        st.caption(f"{item['time'].replace('T', ' ')[:16]} UTC · simulated, not sent")
        st.text(item["body"])

st.subheader("Task board")
if not d.board:
    ui.empty_state("No tasks yet", "Tasks the agent proposes are created only when you approve the reply.")
by_team: dict[str, list] = {}
for t in d.board:
    by_team.setdefault(t["department"], []).append(t)
for team, tasks in sorted(by_team.items()):
    st.markdown(f"**{DEPARTMENT_NAMES.get(team, team)}** ({len(tasks)})")
    st.html(
        "".join(
            f'<div class="gra-item"><b>{esc(t["title"])}</b>'
            + (f" · {esc(t['booking_id'])}" if t.get("booking_id") else "")
            + (f"<small>{esc(t['details'])}</small>" if t.get("details") else "")
            + "</div>"
            for t in tasks
        )
    )

st.subheader("Manager queue")
if not d.manager_queue:
    ui.empty_state(
        "Nothing waiting",
        "Refunds, comps, upgrades, cancellations and rate or date changes the agent "
        "proposes wait here for a manager. The agent never approves them.",
    )
queue_html = "".join(
    f'<div class="gra-item gra-approval"><b>{esc(ACTION_NAMES.get(a["action_type"], a["action_type"]))}</b> · '
    f"needs manager approval{' · ' + esc(a['booking_id']) if a.get('booking_id') else ''}"
    f"<small>{esc(a['reason'])}</small></div>"
    for a in d.manager_queue
)
if queue_html:
    st.html(queue_html)
ui.footer()
