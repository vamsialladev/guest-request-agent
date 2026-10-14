"""Owner-only Admin page. Registered only when ADMIN_PASSWORD is set; hidden from the menu until unlocked.

Copied from Project 1's Admin page: hmac password check, lockout, 30-minute auto sign-out, health and errors, usage
vs caps, cost today, secrets as set / missing, and the request log (list -> "Request details" dialog).
The gate is simple demo protection, not real authentication (SECURITY.md).
"""

import json
import time
from datetime import date

import streamlit as st

from src.admin import FAILURE_DELAY_SECONDS, GateState, attempt, sign_out, still_signed_in
from src.config import (
    ADMIN_IDLE_MINUTES,
    ALERT_DAILY_COST_USD,
    ALERT_ERROR_RATE,
    ALERT_MIN_EVENTS,
    LLM_EFFORT,
    LLM_MODEL,
    MAX_EMAILS_PER_DAY,
    MAX_EMAILS_PER_SESSION,
    PRICE_IN_PER_M,
    PRICE_OUT_PER_M,
    admin_password,
)
from src.display import diff_html, draft_html, esc, model_name, table_html
from src.errors import category, errors_file
from src.limits import today_utc
from src.monitoring import ERROR_COLUMNS, alerts, first_email_success, health, recent_errors, to_csv
from src.reports import latest, mean
from src.requestlog import (
    NOT_RECORDED,
    RESULTS,
    details,
    filter_requests,
    find,
    list_rows,
    log_since,
    request_json,
    selected_id,
    table_key,
    to_jsonl,
)
from src.secrets_check import REQUIRED, secret_status
from src.tools import ACTION_NAMES, DEPARTMENT_NAMES
from src.usage import decisions_file, read_jsonl, redact, requests_file
from views import components as ui

IDLE_SECONDS = ADMIN_IDLE_MINUTES * 60
gate = st.session_state.setdefault("admin_gate", GateState())
timed_out = gate.unlocked and not still_signed_in(gate, time.time(), IDLE_SECONDS)

if not gate.unlocked:
    ui.header("Owner sign-in", "This page is for the app owner only.", "Admin")
    if timed_out:
        st.info(f"Signed out after {ADMIN_IDLE_MINUTES} minutes of inactivity.", icon=":material/lock_clock:")
    with st.form("admin_login", clear_on_submit=True):
        given = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Unlock", icon=":material/lock_open:")
    if submitted:
        ok, message = attempt(gate, given, admin_password(), now=time.time())
        if ok:
            st.rerun()
        time.sleep(FAILURE_DELAY_SECONDS)  # slows down guessing
        st.error(message, icon=":material/lock:")
    st.stop()


@st.fragment(run_every="60s")
def idle_watch():
    """Locks the page even if it's just left open: checks once a minute without counting as activity."""
    if time.time() - gate.last_active > IDLE_SECONDS:
        sign_out(gate)
        st.rerun()


idle_watch()

ui.header("Admin", "Private health, usage, cost and the full request log. Never shown to visitors.", "Owner only")
if st.button("Sign out", icon=":material/logout:"):
    sign_out(gate)
    st.rerun()
st.caption(f"Signs out automatically after {ADMIN_IDLE_MINUTES} minutes without activity.")

records, decisions, errors = read_jsonl(requests_file()), read_jsonl(decisions_file()), read_jsonl(errors_file())
today = today_utc()
h = health(records, errors, today, time.time(), ui.app_started(), ui.daily_counter().used(), MAX_EMAILS_PER_DAY)
secrets = secret_status()  # "set" or "missing" only, never a value
warnings = [
    f"Required secret {name} is missing. Add it under Secrets on Streamlit Cloud (or .streamlit/secrets.toml "
    "locally), then reboot the app."
    for name in REQUIRED
    if secrets[name] == "missing"
] + alerts(h, ALERT_ERROR_RATE, ALERT_MIN_EVENTS, ALERT_DAILY_COST_USD)


def money(value, digits=4):
    return "not configured" if value is None else f"${value:,.{digits}f}"


# ---------- Health and errors ----------
st.subheader("Health and errors")
for w in warnings:
    st.warning(w, icon=":material/warning:")
ui.tiles(
    [
        ("Needs attention" if warnings else "Running normally", "App status", f"Up for {h['uptime']} since restart"),
        (model_name(LLM_MODEL), "Model", f"Effort {LLM_EFFORT or 'default'} · policy search keyword-only"),
        (
            f"{h['daily_used']}/{h['daily_cap']}",
            "Agent runs today vs daily cap",
            f"Per session: {MAX_EMAILS_PER_SESSION} (UTC day)",
        ),
        (money(h["cost_today"], 4), "Estimated cost today", f"Warns at ${ALERT_DAILY_COST_USD:.2f}"),
    ]
)
fe = first_email_success(records)
visitor = latest("visitor")
ui.tiles(
    [
        (
            ui.fmt_pct(fe["rate"]),
            "First-email success (live)",
            f"{fe['ok']} of {fe['sessions']} sessions got a usable result for their first email",
        ),
        (
            ui.fmt_pct(mean(visitor, "first_email_success") if visitor else None),
            "First-email success (eval)",
            f"Visitor set, {visitor['meta']['date']}" if visitor else "No visitor eval report yet",
        ),
    ]
)
st.html(
    '<p class="gra-secrets"><b>Secrets</b> '
    + " ".join(
        f'<span class="gra-status gra-status-{"ok" if state == "set" else "error"}">{name}: {state}</span>'
        for name, state in secrets.items()
    )
    + "</p>"
)
st.markdown(f"**Most recent errors** ({h['errors_today']} today, {len(errors)} in the log)")
recent = recent_errors(errors, 20)
if recent:
    st.html(
        table_html(
            ["Time (UTC)", "Page", "Likely cause", "Message"],
            [
                [
                    r.get("time", "")[:19].replace("T", " "),
                    r.get("page", ""),
                    r.get("category") or category(r.get("type", "")),
                    r.get("message", ""),
                ]
                for r in recent
            ],
        )
    )
else:
    st.caption("No errors recorded since the last restart.")
st.caption(
    f"Cost is an estimate from PRICE_IN_PER_M={PRICE_IN_PER_M} and PRICE_OUT_PER_M={PRICE_OUT_PER_M} (USD per "
    "million tokens); the Anthropic Console is the source of truth for billing."
)

# ---------- Usage ----------
st.subheader("Usage")
since = log_since(records)
st.caption(
    f"Log since {since + ' UTC' if since else 'no entries yet'} · Logs reset when the app restarts. Download a "
    "copy to keep it."
)
api_records = [r for r in records if r.get("api_calls")]
costs = [r["cost_usd"] for r in records if r.get("cost_usd")]
ui.tiles(
    [
        (str(len(records)), "Emails in the log", f"{len(records) - len(api_records)} without an API call"),
        (str(sum(1 for r in records if r.get("escalate"))), "Escalated", "Rules or the agent"),
        (str(sum(1 for r in records if r.get("fallback_reason"))), "Fallback drafts", "API failure or step limit"),
        (
            money(sum(costs) if costs else None),
            "Estimated cost, whole log",
            f"{sum(r.get('api_calls', 0) for r in records)} API calls",
        ),
    ]
)
k1, k2 = st.columns(2)
k1.download_button(
    "Download request log (JSONL)",
    to_jsonl(records),
    f"requests-{today}.jsonl",
    "application/jsonl",
    icon=":material/download:",
    on_click="ignore",
)
k2.download_button(
    "Download decisions (JSONL)",
    to_jsonl(decisions),
    f"decisions-{today}.jsonl",
    "application/jsonl",
    icon=":material/download:",
    on_click="ignore",
)


# ---------- Requests: list, filters, details ----------
def nr(value, fmt=None) -> str:
    return NOT_RECORDED if value is None else (fmt(value) if fmt else str(value))


def fields_table(pairs: list) -> str:
    return table_html(["Field", "Value"], [[k, v] for k, v in pairs])


@st.dialog("Request details", width="large")
def request_dialog(record: dict, decision_rows: list):
    d = details(record, decision_rows)
    tabs = st.tabs(
        ["Summary", "Email", "Agent steps", "Draft vs final", "Tasks & actions", "Performance", "Checks", "Raw JSON"]
    )
    with tabs[0]:
        dec = d["decision"]
        st.html(
            fields_table(
                [
                    ("Result", d["result"]),
                    ("Escalated", ("Yes: " + "; ".join(d["escalation_reasons"] or [])) if d["escalate"] else "No"),
                    (
                        "Staff decision",
                        (dec.get("decision") + (f" ({dec.get('reason')})" if dec.get("reason") else ""))
                        if dec
                        else "pending",
                    ),
                    ("Property", d["property"]),
                    (
                        "Source",
                        d["source"] + (f" (reused from {record['reused_from']})" if record.get("reused_from") else ""),
                    ),
                    ("Time (UTC)", d["time"]),
                    ("Session", d["session_id"]),
                    ("Log schema", f"v{d['schema_version']}"),
                ]
            )
        )
        if d["message"]:
            st.caption(f"Reply shown: {d['message']}")
        st.caption("Request ID (copy icon on the right)")
        st.code(d["id"], language=None)
    with tabs[1]:
        e = d["email"]
        st.html(
            fields_table(
                [
                    ("From", f"{e.get('name') or ''} <{e.get('from') or NOT_RECORDED}>"),
                    ("Subject", e.get("subject") or "(none)"),
                ]
            )
        )
        st.text(e.get("body") or NOT_RECORDED)
    with tabs[2]:
        steps = d["steps"]
        if not steps:
            st.caption("No agent steps (answered without the agent)." if steps == [] else NOT_RECORDED)
        for s in steps or []:
            with st.expander(f"{s['n']}. {'✓' if s['ok'] else '⚠'} {s['tool']} · {s['summary']}"):
                st.caption(f"{s['kind']} · {nr(s.get('ms'), lambda v: f'{v} ms')}")
                if s.get("args"):
                    st.json(s["args"])
                if s.get("result") is not None:
                    st.json(s["result"], expanded=False)
    with tabs[3]:
        titles = {c["id"]: c.get("title") or c["id"] for c in d["citations"] or []}
        if d["draft"] is None:
            st.caption("No draft (answered without the agent).")
        else:
            st.markdown("**Agent draft** (after the guards)")
            st.html(draft_html(d["draft"], titles))
            if d["raw_draft"] and d["raw_draft"] != d["draft"]:
                with st.expander("Model's original draft (before the guards)"):
                    st.text(d["raw_draft"])
            if d["final_text"]:
                st.markdown("**Sent (simulated)** · " + ("edited by staff" if d["edited"] else "unchanged"))
                st.html(
                    diff_html(d["draft"], d["final_text"])
                    if d["edited"]
                    else f'<div class="gra-draft">{esc(d["final_text"])}</div>'
                )
            else:
                st.caption("Not sent: " + ((d["decision"] or {}).get("decision") or "no decision yet"))
    with tabs[4]:
        tasks, actions = d["tasks"] or [], d["actions"] or []
        st.html(
            table_html(
                ["Team", "Task", "Details"],
                [
                    [DEPARTMENT_NAMES.get(t["department"], t["department"]), t["title"], t.get("details") or ""]
                    for t in tasks
                ],
            )
            if tasks
            else "<p>No tasks proposed.</p>"
        )
        st.html(
            table_html(
                ["Needs manager approval", "Reason", "Booking"],
                [
                    [ACTION_NAMES.get(a["action_type"], a["action_type"]), a["reason"], a.get("booking_id") or ""]
                    for a in actions
                ],
            )
            if actions
            else "<p>No manager approvals proposed.</p>"
        )
    with tabs[5]:
        st.html(
            fields_table(
                [
                    ("Model", d["model"]),
                    ("API calls (model turns)", nr(d["api_calls"])),
                    ("Total time", nr(d["latency_s"], lambda v: f"{v:.2f} s")),
                    ("Tokens in / out", f"{nr(d['tokens_in'])} / {nr(d['tokens_out'])}"),
                    ("Estimated cost", nr(d["cost_usd"], lambda v: f"${v:.6f}")),
                ]
            )
        )
    with tabs[6]:
        c = d["checks"] or {}
        st.html(
            fields_table(
                [
                    ("Injection markers", ", ".join(c.get("injection_markers") or []) or "None"),
                    ("Promises removed by the guard", " | ".join(c.get("forbidden_promises_removed") or []) or "None"),
                    ("Facts not in any tool result", ", ".join(c.get("ungrounded_facts") or []) or "None"),
                    ("Unknown citations", ", ".join(c.get("unknown_citations") or []) or "None"),
                    ("Escalation override", c.get("escalation_override") or "None"),
                    ("Fallback", d["fallback_reason"] or "None"),
                    ("Error", d["error"] or "None"),
                    ("Error message", d["error_message"] or "None"),
                ]
            )
        )
    with tabs[7]:
        st.code(json.dumps(redact(d["raw"]), ensure_ascii=False, indent=2), language="json", wrap_lines=True)
    b1, b2 = st.columns(2)
    b1.download_button(
        "Download this request (JSON)",
        redact(request_json(record, decision_rows)),
        f"request-{d['id']}.json",
        "application/json",
        icon=":material/download:",
        on_click="ignore",
        width="stretch",
    )
    if b2.button("Close", icon=":material/close:", width="stretch"):
        st.rerun()


PAGE_SIZE = 50
st.subheader("Requests")
st.caption("One record per email: drafted, escalated, fallback, greeting, off-topic, error or cap. Select a row.")
all_rows = list_rows(records, decisions)
props = sorted({r["property"] for r in all_rows if r["property"] != NOT_RECORDED})
f1, f2, f3 = st.columns(3)
picked = f1.date_input("Date range (UTC)", value=(), max_value=date.today())
pick_prop = f2.selectbox("Property", ["All properties", *props])
pick_results = f3.multiselect("Result", list(RESULTS), format_func=RESULTS.get, placeholder="All results")
g1, g2 = st.columns([1, 3], vertical_alignment="bottom")
escalated_only = g1.checkbox("Escalated only")
search = g2.text_input("Search emails", placeholder="Words in the sender, subject or body")
dates = list(picked) if isinstance(picked, list | tuple) else [picked]
start = dates[0] if dates else None
end = dates[1] if len(dates) > 1 else start
filters = (start, end, pick_prop, tuple(pick_results), escalated_only, search.strip().lower())
matching = filter_requests(
    all_rows,
    start=start,
    end=end,
    prop=None if pick_prop == "All properties" else pick_prop,
    outcomes=pick_results,
    escalated_only=escalated_only,
    text=search,
)
if st.session_state.get("requests_filters") != filters:
    st.session_state.requests_filters, st.session_state.requests_limit = filters, PAGE_SIZE
limit = st.session_state.setdefault("requests_limit", PAGE_SIZE)
shown = matching[:limit]
st.caption(f"Showing {len(shown)} of {len(matching)} emails ({len(all_rows)} in the log), newest first.")
event = st.dataframe(
    shown,
    column_order=("time", "property", "source", "result", "decision", "subject", "steps", "total", "cost"),
    column_config={
        "time": "Time (UTC)",
        "property": "Property",
        "source": "Source",
        "result": "Result",
        "decision": "Staff",
        "subject": st.column_config.TextColumn("Email", width="large"),
        "steps": "Steps",
        "total": "Total time",
        "cost": "Cost",
    },
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    key=table_key(filters, limit),
)
if len(matching) > limit and st.button(
    f"Load {min(PAGE_SIZE, len(matching) - limit)} more", icon=":material/expand_more:"
):
    st.session_state.requests_limit = limit + PAGE_SIZE
    st.rerun()

rid = selected_id(shown, event)
if rid is None:
    st.session_state.pop("requests_open", None)
elif st.session_state.get("requests_open") != rid:
    st.session_state.requests_open = rid
    record = find(records, rid)
    if record is not None:
        request_dialog(record, decisions)

d1, d2 = st.columns(2)
d1.download_button(
    "Download requests CSV",
    to_csv([{k: v for k, v in r.items() if k != "search_text"} for r in all_rows]),
    f"requests-{today}.csv",
    "text/csv",
    icon=":material/download:",
    on_click="ignore",
)
d2.download_button(
    "Download errors CSV",
    to_csv(errors, ERROR_COLUMNS),
    f"errors-{today}.csv",
    "text/csv",
    icon=":material/download:",
    on_click="ignore",
)
st.caption("The logs include guest emails and drafts as typed and shown. Keep downloads private.")
