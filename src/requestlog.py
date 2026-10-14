"""The owner's request log: list and detail views for the Admin page, over the request and decision logs.

Pure functions, unit-tested without Streamlit. One record per processed email (src/service.py builds it); staff
decisions are separate records linked by request_id. Anything a record lacks shows "not recorded", never a blank.
"""

import hashlib
import json
from datetime import date

from src.display import changed

NOT_RECORDED = "not recorded"
PREVIEW = 60

RESULTS = {
    "drafted": "🟢 Drafted",
    "escalated": "🟠 Escalated",
    "fallback": "🟡 Fallback",
    "greeting": "🔵 Greeting",
    "off_topic": "🔵 Off-topic",
    "error": "🔴 Error",
    "cap": "🟣 Cap",
}
DECISIONS = {"approved": "✅ Approved", "rejected": "✖ Rejected", None: "⏳ Pending"}


def outcome_of(record: dict) -> str:
    outcome = record.get("outcome")
    return outcome if outcome in RESULTS else "error"


def request_id(record: dict) -> str:
    rid = record.get("request_id")
    if rid:
        return str(rid)
    seed = f"{record.get('time')}|{record.get('property')}|{(record.get('email') or {}).get('body')}"
    return "old-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]


def decision_index(decisions: list) -> dict:
    """request_id -> the latest decision for it."""
    return {str(d["request_id"]): d for d in decisions if d.get("request_id")}


def short_time(value) -> str:
    return str(value or "")[:19].replace("T", " ") or NOT_RECORDED


def preview(text, limit: int = PREVIEW) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        return NOT_RECORDED
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def fmt_seconds(record: dict) -> str:
    v = record.get("latency_s")
    if v is None:
        return NOT_RECORDED
    return "–" if not record.get("api_calls") else f"{v:.1f} s"


def fmt_cost(record: dict) -> str:
    v = record.get("cost_usd")
    return NOT_RECORDED if v is None else f"${v:.5f}"


def email_of(record: dict) -> dict:
    return record.get("email") or {}


def list_rows(records: list, decisions: list) -> list[dict]:
    """One row per email for the Admin table, newest first."""
    dec = decision_index(decisions)
    rows = []
    for r in reversed(records):
        rid = request_id(r)
        e = email_of(r)
        d = dec.get(rid)
        subject = e.get("subject") or e.get("body") or ""
        rows.append(
            {
                "id": rid,
                "time": short_time(r.get("time")),
                "property": r.get("property") or NOT_RECORDED,
                "source": r.get("source") or NOT_RECORDED,
                "result": RESULTS[outcome_of(r)],
                "outcome": outcome_of(r),
                "escalated": bool(r.get("escalate")),
                "decision": DECISIONS.get(d.get("decision") if d else None, DECISIONS[None]),
                "subject": preview(subject),
                "search_text": " ".join([e.get("from") or "", e.get("subject") or "", e.get("body") or ""]).lower(),
                "steps": len(r.get("steps") or []),
                "total": fmt_seconds(r),
                "cost": fmt_cost(r),
            }
        )
    return rows


def day_of(row: dict) -> date | None:
    try:
        return date.fromisoformat(row["time"][:10])
    except (KeyError, TypeError, ValueError):
        return None


def filter_requests(
    rows: list,
    start: date | None = None,
    end: date | None = None,
    prop: str | None = None,
    outcomes: list | None = None,
    escalated_only: bool = False,
    text: str = "",
) -> list:
    out = []
    needle = " ".join(text.split()).lower()
    for r in rows:
        day = day_of(r)
        if (start or end) and day is None:
            continue
        if start and day < start or end and day > end:
            continue
        if prop and r["property"] != prop:
            continue
        if outcomes and r["outcome"] not in outcomes:
            continue
        if escalated_only and not r["escalated"]:
            continue
        if needle and needle not in r["search_text"]:
            continue
        out.append(r)
    return out


def selected_id(shown: list, selection) -> str | None:
    try:
        rows = selection["selection"]["rows"]
    except (KeyError, TypeError):
        return None
    if not rows or not isinstance(rows[0], int) or not 0 <= rows[0] < len(shown):
        return None
    return shown[rows[0]]["id"]


def table_key(filters: tuple, limit: int) -> str:
    return "requests_" + hashlib.sha1(repr((filters, limit)).encode("utf-8")).hexdigest()[:10]


def find(records: list, rid: str) -> dict | None:
    for r in reversed(records):
        if request_id(r) == rid:
            return r
    return None


def details(record: dict, decisions: list) -> dict:
    """Everything the Request details dialog shows; "not recorded" for anything missing."""
    rid = request_id(record)
    d = decision_index(decisions).get(rid)
    final = d.get("final_text") if d else None
    draft = record.get("draft")
    return {
        "id": rid,
        "schema_version": record.get("schema_version", NOT_RECORDED),
        "time": short_time(record.get("time")),
        "property": record.get("property") or NOT_RECORDED,
        "session_id": record.get("session_id") or NOT_RECORDED,
        "source": record.get("source") or NOT_RECORDED,
        "email": email_of(record),
        "outcome": outcome_of(record),
        "result": RESULTS[outcome_of(record)],
        "escalate": bool(record.get("escalate")),
        "escalation_reasons": record.get("escalation_reasons"),
        "message": record.get("message"),
        "steps": record.get("steps"),
        "requests": record.get("requests"),
        "draft": draft,
        "raw_draft": record.get("raw_draft"),
        "citations": record.get("citations"),
        "decision": d,
        "final_text": final,
        "edited": bool(d and d.get("final_text") and draft and changed(draft, final)),
        "tasks": record.get("tasks"),
        "actions": record.get("actions"),
        "checks": record.get("checks"),
        "model": record.get("model") or ("none (no API call)" if not record.get("api_calls") else NOT_RECORDED),
        "api_calls": record.get("api_calls"),
        "latency_s": record.get("latency_s"),
        "tokens_in": record.get("tokens_in"),
        "tokens_out": record.get("tokens_out"),
        "cost_usd": record.get("cost_usd"),
        "fallback_reason": record.get("fallback_reason"),
        "error": record.get("error"),
        "error_message": record.get("error_message"),
        "raw": record,
    }


def to_jsonl(rows: list) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def request_json(record: dict, decisions: list) -> str:
    d = decision_index(decisions).get(request_id(record))
    return json.dumps({"request": record, "decision": d}, ensure_ascii=False, indent=2)


def log_since(records: list) -> str | None:
    times = [str(r.get("time")) for r in records if r.get("time")]
    return short_time(min(times)) if times else None
