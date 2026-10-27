"""One entry point for the app and the eval: process an email, enforce the caps, log one record per email.

    result, record = process(email, "beach-resort", source="inbox", session_id=..., first=True)

Order: input check (no API call for empty, too long, greeting or off-topic text typed by a visitor) → session cap →
daily cap → agent → one request-log record. Every outcome is logged, including caps and errors.
"""

import uuid
from dataclasses import replace

from src import ops, triage
from src.agent import Email, holding_template, run_agent
from src.config import (
    LLM_MODEL,
    MAX_EMAIL_CHARS,
    MAX_EMAILS_PER_SESSION,
    PRICE_IN_PER_M,
    PRICE_OUT_PER_M,
)
from src.errors import record_error, safe_message
from src.models import AgentResult
from src.usage import estimate_cost, log_request

SCHEMA_VERSION = 1
SESSION_CAP_MESSAGE = (
    f"This demo session has reached its limit of {MAX_EMAILS_PER_SESSION} emails. Start a new session from the "
    "Outbox and tasks page, or come back later."
)
DAILY_CAP_MESSAGE = "The demo has reached today's limit across all visitors. Please come back tomorrow."
ERROR_MESSAGE = "The assistant is temporarily unavailable. Please try again in a minute."
RESULT_CHARS = 1500
NL = "\n"  # subject and body are checked as one text, then split back at the first newline


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def short_result(result) -> object:
    """Tool results in the log, trimmed so one record stays small. Policy passages keep their id and section."""
    import json

    text = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
    return result if len(text) <= RESULT_CHARS else text[:RESULT_CHARS] + "…"


def build_record(
    result: AgentResult,
    email: Email,
    prop: str,
    *,
    request_id: str,
    source: str,
    session_id: str | None,
    first: bool,
    email_id: str | None = None,
    error: str | None = None,
    error_message: str | None = None,
) -> dict:
    cost = (
        estimate_cost(result.tokens_in, result.tokens_out, PRICE_IN_PER_M, PRICE_OUT_PER_M) if result.api_calls else 0.0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "session_id": session_id,
        "first": first,
        "source": source,
        "email_id": email_id,
        "property": prop,
        "email": {"from": email.sender, "name": email.sender_name, "subject": email.subject, "body": email.body},
        "outcome": result.outcome,
        "escalate": result.escalate,
        "escalation_reasons": result.escalation_reasons,
        "fallback_reason": result.fallback_reason,
        "message": result.message or None,
        "steps": [
            {
                "n": s.n,
                "kind": s.kind,
                "tool": s.name,
                "summary": s.summary,
                "ok": s.ok,
                "args": s.args,
                "result": short_result(s.result) if s.result is not None else None,
                "ms": s.ms,
            }
            for s in result.steps
        ],
        "requests": [r.model_dump() for r in result.requests],
        "draft": result.reply or None,
        "raw_draft": result.raw_reply or None,
        "language": result.language,
        "citations": [{k: c.get(k) for k in ("id", "title", "source", "section")} for c in result.citations],
        "bookings": [b.get("booking_id") for b in result.bookings],
        "tasks": [t.model_dump() for t in result.tasks],
        "actions": [a.model_dump() for a in result.actions],
        "checks": result.flags,
        "model": result.model if result.api_calls else None,
        "api_calls": result.api_calls,
        "latency_s": result.latency_s,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": cost,
        "error": error,
        "error_message": error_message,
    }


def log_reused(
    result: AgentResult,
    email: Email,
    prop: str,
    *,
    original_id: str,
    session_id: str | None,
    first: bool,
    email_id: str | None,
    log: bool = True,
) -> tuple[AgentResult, dict]:
    """A sample email's earlier result shown to another visitor: its own request record (so staff decisions link to
    it), marked as reused, with no API call, tokens or cost counted again."""
    reused = result.model_copy(update={"api_calls": 0, "tokens_in": 0, "tokens_out": 0})
    record = build_record(
        reused, email, prop, request_id=new_id(), source="inbox", session_id=session_id, first=first, email_id=email_id
    )
    record["reused_from"] = original_id
    record["model"] = result.model
    return reused, (log_request(record) if log else record)


def quick_result(outcome: str, message: str) -> AgentResult:
    return AgentResult(outcome=outcome, message=message)


def process(email: Email, prop: str, *, source: str, session_id: str | None = None, **kwargs):
    """Process one email inside one trace (hotel-ai-platform): guardrails, the deterministic booking lookup, every
    model turn and tool call, and the output check are its spans. Returns (result, record) as before."""
    with ops.start(session_id) as trace:
        verdict = ops.check_email(email.subject + NL + email.body)  # attacks flagged; cards/IDs replaced
        subject, _, body = verdict.text.partition(NL)
        for_model = replace(email, subject=subject, body=body)
        result, record = _process(email, prop, source=source, session_id=session_id, for_model=for_model,
                                  trace=trace, **kwargs)  # fmt: skip
        ops.finish(trace, record)  # the shared ops row + spans; never blocks or raises
    return result, record


def check_draft(result: AgentResult, for_model: Email, trace) -> AgentResult:
    """The shared output check on the draft, after this app's own guard (promises, citations, grounding)."""
    if not result.reply:
        return result
    checked = ops.check_draft(result.reply, result.sources, for_model.subject + NL + for_model.body)
    if not checked.allowed:  # prompt leak or off-brand text: a holding reply and a manager, never the text
        reasons = [*result.escalation_reasons, f"guardrail: {checked.reason}"]
        return result.model_copy(update={"reply": holding_template(result.language, True), "escalate": True,
                                         "escalation_reasons": reasons, "outcome": "escalated"})  # fmt: skip
    if checked.text != result.reply:  # contact details the guest didn't give, replaced
        return result.model_copy(update={"reply": checked.text})
    return result


def _process(
    email: Email,
    prop: str,
    *,
    source: str,
    session_id: str | None = None,
    first: bool = False,
    email_id: str | None = None,
    session_count: int = 0,
    daily_counter=None,
    client=None,
    log: bool = True,
    keyword_matches=None,
    for_model: Email | None = None,
    trace=None,
) -> tuple[AgentResult, dict]:
    """Process one email. `session_count` is how many emails this session already sent to the agent. The agent
    reads `for_model` (card and ID numbers replaced); the record keeps the email as received (redacted on write)."""
    request_id = new_id()
    error = error_message = None
    if source == "write":
        kind = triage.classify_input(email.body, MAX_EMAIL_CHARS, keyword_matches)
        replies = {
            "empty": ("off_topic", triage.EMPTY_REPLY),
            "too_long": ("off_topic", f"Please keep the email under {MAX_EMAIL_CHARS:,} characters."),
            "greeting": ("greeting", triage.GREETING_REPLY),
            "off_topic": ("off_topic", triage.OFF_TOPIC_REPLY),
        }
        if kind in replies:
            result = quick_result(*replies[kind])
            record = build_record(
                result,
                email,
                prop,
                request_id=request_id,
                source=source,
                session_id=session_id,
                first=first,
                email_id=email_id,
            )
            if trace is not None:
                record["trace_id"] = trace.trace_id
                record["safety_flags"] = ops.safety_flags(trace)
            return result, (log_request(record) if log else record)
    if session_count >= MAX_EMAILS_PER_SESSION:
        result, error = quick_result("cap", SESSION_CAP_MESSAGE), "session_cap"
    elif daily_counter is not None and not daily_counter.try_consume():
        result, error = quick_result("cap", DAILY_CAP_MESSAGE), "daily_cap"
    else:
        try:
            result = run_agent(for_model or email, prop, client=client)
        except Exception as exc:  # run_agent has its own fallback; this is the last line of defence
            record_error("Agent", exc)
            result = quick_result("error", ERROR_MESSAGE)
            error, error_message = "unexpected", safe_message(exc)
        if result.fallback_reason and result.fallback_reason.startswith("api_"):
            error = result.fallback_reason[4:]
            error_message = f"API call failed ({error}); fallback draft used"
        result = check_draft(result, for_model or email, trace)
        if trace is not None and (error or result.outcome == "error"):
            result.flags["reference"] = trace.reference  # shown to staff; Admin -> Traces finds the request
            if result.outcome == "error":
                result = result.model_copy(update={"message": f"{result.message} Reference: {trace.reference}"})
    record = build_record(
        result,
        email,
        prop,
        request_id=request_id,
        source=source,
        session_id=session_id,
        first=first,
        email_id=email_id,
        error=error,
        error_message=error_message,
    )
    record["model"] = record["model"] or (LLM_MODEL if result.api_calls else None)
    if trace is not None:
        record["trace_id"] = trace.trace_id
        record["safety_flags"] = ops.safety_flags(trace)
    return result, (log_request(record) if log else record)
