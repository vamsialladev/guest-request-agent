"""Owner monitoring for the Admin page: health, threshold warnings, recent errors and CSV export.

Pure functions over the request and error logs, so they're unit-tested without Streamlit.
"""

import csv
import io

ERROR_COLUMNS = ("time", "page", "type", "category", "error", "message")


def on_day(rows: list, day: str) -> list:
    return [r for r in rows if str(r.get("time", "")).startswith(day)]


def format_uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def health(usage_rows, error_rows, today: str, now: float, started: float, daily_used: int, daily_cap: int) -> dict:
    """Today's numbers for the Health section."""
    usage_today = on_day(usage_rows, today)
    answered_today = [r for r in usage_today if r.get("outcome") not in ("error", "cap")]
    errors_today = on_day(error_rows, today)
    costs = [r["cost_usd"] for r in usage_today if r.get("cost_usd") is not None]
    events = len(answered_today) + len(errors_today)
    return {
        "uptime": format_uptime(now - started),
        "emails_today": len(answered_today),
        "daily_used": daily_used,
        "daily_cap": daily_cap,
        "cost_today": sum(costs) if costs else None,
        "errors_today": len(errors_today),
        "error_rate_today": len(errors_today) / events if events else 0.0,
        "events_today": events,
    }


def alerts(h: dict, error_rate: float, min_events: int, daily_cost: float) -> list[str]:
    """Plain-language warnings when a threshold is crossed. Empty list = all clear."""
    out = []
    if h["events_today"] >= min_events and h["error_rate_today"] >= error_rate:
        out.append(
            f"Error rate today is {h['error_rate_today']:.0%} ({h['errors_today']} errors), above the "
            f"{error_rate:.0%} threshold. Check the recent errors below and the API key and credit balance."
        )
    if h["cost_today"] is not None and h["cost_today"] >= daily_cost:
        out.append(
            f"Estimated cost today is ${h['cost_today']:.2f}, above the ${daily_cost:.2f} threshold. "
            "Check the Anthropic Console and consider lowering MAX_EMAILS_PER_DAY."
        )
    if h["daily_cap"] and h["daily_used"] >= 0.9 * h["daily_cap"]:
        out.append(
            f"The daily email cap is {h['daily_used']}/{h['daily_cap']} used; visitors will be turned away soon."
        )
    return out


def recent_errors(error_rows: list, n: int = 20) -> list:
    return list(reversed(error_rows[-n:]))


def csv_safe(value) -> str:
    """Stop spreadsheet formula injection: visitor-typed text like '=HYPERLINK(...)' is stored as text."""
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(rows: list, columns=None) -> str:
    columns = list(columns or sorted({k for r in rows for k in r}))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([csv_safe(r.get(c)) for c in columns])
    return buffer.getvalue()


def first_email_success(rows: list) -> dict:
    """Live first-email success: of the sessions in the log, how many got a usable result for their very first
    email (a draft that passed the checks, an escalation, or a greeting / off-topic reply)."""
    firsts = [r for r in rows if r.get("first") and r.get("session_id")]
    ok = sum(
        1
        for r in firsts
        if r.get("outcome") in ("drafted", "escalated", "greeting", "off_topic")
        and not (r.get("checks") or {}).get("ungrounded_facts")
    )
    return {"sessions": len(firsts), "ok": ok, "rate": ok / len(firsts) if firsts else None}
