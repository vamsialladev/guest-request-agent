"""Shared guardrails, request tracing and the cross-app ops log (hotel-ai-platform), wired for this app.

    with ops.start(session_id) as trace:              one trace per email; the reference shows on errors
        v = ops.check_email(body)                     input guardrails: attacks flagged, card numbers redacted
        ...the agent runs; each model turn and tool call is a span (src/agent.py)...
        o = ops.check_draft(reply, sources, body)     output guardrails on the draft
        ops.finish(trace, record)                     one ops_request_log row + the spans, PII removed first

Guest emails are never *blocked*: staff still need to see a guest's email even when it carries an attack, so
attack patterns are flagged (and the agent's own planted-instruction quarantine removes them, decision 20) and
card or ID numbers are replaced before the model reads the email. The app's own request log (src/usage.py) keeps
its detailed record; the ops tables are the same in every hotel app.
"""

import os
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from hotelplatform import guardrails, jsonlog, oplog, pii, tracing, version

from src.config import ALERT_DAILY_COST_USD, APP_NAME, BUDGET_P95_S, LLM_MODEL, MAX_EMAIL_CHARS, RETENTION_DAYS

ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = "1.2.0"
MONTHLY_COST_CAP_USD = float(os.getenv("MONTHLY_COST_CAP_USD", "10.00"))

INPUT_POLICY = guardrails.InputPolicy(
    max_chars=MAX_EMAIL_CHARS + 300,  # subject + body; the page already limits the body
    languages=(),  # the agent detects the language and replies in it (decision 19)
    block=(),  # an email always reaches staff...
    flag=guardrails.ATTACKS,  # ...with every attack pattern noted on the trace
    sanitize=(),
    pii_block=frozenset(),
    # The model never needs a card, SSN, IBAN or IP address to draft a reply. Emails and phones stay: the guest
    # may ask staff to call them back, and the sender's address is a separate field the tools use.
    pii_redact=frozenset({"CREDIT_CARD", "US_SSN", "IBAN_CODE", "IP_ADDRESS"}),
)
# Promises and citations already have this app's own checks (src/guards.py, decisions 6 and 20); the shared check
# adds leaked contact details, prompt leaks and off-brand text.
OUTPUT_POLICY = guardrails.OutputPolicy(require_citation=False, numbers="off", promises="flag", pii_leak="redact")
CAPS = {"session_cap", "daily_cap"}
_TRACES: "OrderedDict[str, str]" = OrderedDict()  # request_id -> trace_id, for staff decisions (bounded)
_MAX_TRACES = 2000


@lru_cache(maxsize=1)
def store() -> oplog.OpsStore:
    """One per process. Nothing connects until the first row is written (Neon stays asleep for bots)."""
    url = os.getenv("DATABASE_URL", "").strip()
    return oplog.OpsStore(APP_NAME, url=url, log_dir=ROOT / "data" / "logs", retention_days=RETENTION_DAYS)


@lru_cache(maxsize=1)
def running_version() -> str:
    return version.version_string(APP_VERSION, ROOT)


def configure_logs() -> None:
    jsonlog.configure(APP_NAME, running_version())


def start(session_id: str | None):
    return tracing.new_trace(APP_NAME, session_id=session_id)


def check_email(text: str) -> guardrails.Verdict:
    return guardrails.check_input(text, INPUT_POLICY)


def check_draft(reply: str, sources: list[str], email_text: str) -> guardrails.Verdict:
    return guardrails.check_output(reply, OUTPUT_POLICY, sources=sources, input_text=email_text)


def safety_flags(trace) -> list[str]:
    flags = set()
    for span in trace.spans if trace is not None else []:
        if span.name.startswith("guardrails."):
            stage = span.name.split(".", 1)[1]
            flags.update(span.attributes.get("flags") or [])
            flags.update(f"{stage}:{r}" for r in span.attributes.get("reasons") or [])
    return sorted(flags)


def status_of(record: dict) -> str:
    """ok | refused | blocked | error | timeout | capped, from this app's request record."""
    error = record.get("error")
    if error in CAPS or record.get("outcome") == "cap":
        return "capped"
    if error == "timeout":
        return "timeout"
    if error or record.get("outcome") == "error":
        return "error"
    if record.get("outcome") in ("greeting", "off_topic"):
        return "refused"
    return "ok"


def remember(request_id: str, trace_id: str) -> None:
    _TRACES[request_id] = trace_id
    while len(_TRACES) > _MAX_TRACES:
        _TRACES.popitem(last=False)


def finish(trace, record: dict) -> bool:
    """Write the ops row for one email. Never raises, never blocks."""
    if trace is None:
        return False
    try:
        status = status_of(record)
        remember(record.get("request_id") or "", trace.trace_id)
        tools = [
            {"tool": s.get("tool"), "ok": s.get("ok")} for s in record.get("steps") or [] if s.get("kind") == "tool"
        ]
        row = oplog.request_row(
            trace,
            request_type="email",
            status=status,
            latency_ms=round((record.get("latency_s") or 0) * 1000, 1) or trace.elapsed_ms(),
            error_type=record.get("error") or record.get("fallback_reason"),
            error_message=record.get("error_message"),
            tokens_in=record.get("tokens_in") or 0,
            tokens_out=record.get("tokens_out") or 0,
            cost_usd=record.get("cost_usd") or 0.0,
            model=record.get("model"),
            tool_calls=tools,
            sources=[c.get("id") or c.get("section") for c in record.get("citations") or [] if isinstance(c, dict)],
            safety_flags=safety_flags(trace),
            source="user" if record.get("source") in ("inbox", "write") else record.get("source") or "user",
            version=running_version(),
            data={
                "outcome": record.get("outcome"),
                "escalate": record.get("escalate"),
                "escalation_reasons": record.get("escalation_reasons"),
                "request_id": record.get("request_id"),
                "email": record.get("email"),
                "draft": record.get("draft"),
            },  # fmt: skip
        )
        latency = row["latency_ms"] or 0
        if status == "ok" and latency > BUDGET_P95_S * 1000:
            jsonlog.slow_request(latency, BUDGET_P95_S * 1000, trace_id=trace.trace_id)
        if status == "capped":
            jsonlog.cap_hit(record.get("error") or "cap", trace_id=trace.trace_id)
        return store().submit(trace, row)
    except Exception:
        return False


def decision_feedback(record: dict) -> None:
    """A staff decision is this app's feedback: approved = up, rejected = down (with the reason)."""
    try:
        trace_id = _TRACES.get(record.get("request_id") or "")
        decision = record.get("decision")
        if trace_id and decision in ("approved", "rejected"):
            reason = pii.scrub_text(record.get("reason") or "")
            store().feedback(trace_id, "up" if decision == "approved" else "down", reason)
    except Exception:
        pass


def dependencies() -> dict[str, str]:
    return {
        "anthropic": "configured" if os.getenv("ANTHROPIC_API_KEY") else "missing key",
        "database": store().health()["status"],
        "model": LLM_MODEL,
    }


def caps() -> dict[str, float]:
    return {"cost_cap_day": ALERT_DAILY_COST_USD, "cost_cap_month": MONTHLY_COST_CAP_USD}
