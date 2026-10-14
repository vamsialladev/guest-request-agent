"""How it works: plain-language explanation, a diagram and the latest measured results."""

import streamlit as st

from src.config import LLM_MODEL, MAX_AGENT_STEPS
from src.display import model_name, table_html
from src.reports import latest, mean
from views import components as ui

ui.header(
    "How it works", "From a guest email to an approved reply, with a person in control of every send.", "Under the hood"
)

st.graphviz_chart(
    """
digraph {
  rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fillcolor="#E6EEEA", color="#1E4636",
  fontname="Helvetica", fontsize=11]; edge [color="#5B625E"];
  email [label="Guest email\\n(untrusted data)"];
  triage [label="Triage rules\\nescalation · injection\\n(no API call)"];
  agent [label="Agent: Claude Haiku 5.5\\nmax STEPS turns, retry, fallback"];
  tools [label="Tools\\nfind_booking · check_availability\\nsearch_policy (Project 1)\\npropose_task · propose_action"];
  guards [label="Guards\\nno promises · facts grounded\\ncitations valid"];
  staff [label="Staff review\\napprove · edit · reject", fillcolor="#F5EBD7", color="#94702C"];
  out [label="Outbox (simulated)\\n+ task board\\n+ manager queue"];
  email -> triage -> agent; agent -> tools [dir=both]; agent -> guards -> staff -> out;
}
""".replace("STEPS", str(MAX_AGENT_STEPS)),
    width="stretch",
)

st.markdown(
    f"""
**1. Triage, before any AI.** Simple rules look for injury, medical, safety, legal threats, harassment,
discrimination, press, refund demands in a complaint and very angry tone. Any hit sends the email to a manager with
a polite holding reply. Text that tries to instruct the assistant ("ignore your rules", "approve a refund") is
flagged and treated as data.

**2. The agent works through the email.** {model_name(LLM_MODEL)} lists every request and calls tools: it looks up
the sender's own booking (it can't look up anyone else's), checks which rooms are free, and searches the hotel
policies with Project 1's search. It proposes tasks for the right team and proposes, never makes, any refund,
comp, upgrade, cancellation or rate change. It has at most {MAX_AGENT_STEPS} turns; if the API fails or it runs
out of turns, a safe fallback writes a holding reply and a task for the front desk.

**3. Guards check the draft.** Every date, price, time and room number in the draft must appear in a tool result.
Any sentence that promises a refund, upgrade or similar is replaced. Citations must point at passages the agent
actually read.

**4. A person decides.** Staff approve, edit or reject (with a reason). Only approval puts the reply in the outbox
and creates the tasks. Nothing is ever really sent.
"""
)

report = latest("main", "final") or latest("main")
if report:
    st.subheader("Measured results")
    rows = [
        ["Escalation recall (gate 100%)", ui.fmt_pct(mean(report, "escalation_recall"))],
        ["Prompt-injection resistance (gate 100%)", ui.fmt_pct(mean(report, "injection_resistance"))],
        ["Drafts with no forbidden promise (gate 100%)", ui.fmt_pct(mean(report, "no_forbidden_promises"))],
        ["Requests found", ui.fmt_pct(mean(report, "request_coverage"))],
        ["Drafts with every fact grounded", ui.fmt_pct(mean(report, "fact_grounding"))],
        ["Task routing accuracy", ui.fmt_pct(mean(report, "task_routing"))],
        ["Full draft, p95", ui.fmt_seconds(mean(report, "p95_latency_s"))],
    ]
    st.html(table_html(["Metric", "Result"], rows))
    st.caption(
        f"{report['meta']['runs']} run(s) over {report['summary']['per_run'][0]['emails']} labelled synthetic "
        f"emails, {report['meta']['date']} ({report['file']}). Definitions and every miss are in the repo's "
        "eval reports."
    )
ui.footer()
