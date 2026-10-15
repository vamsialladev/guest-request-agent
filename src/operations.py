"""Numbers for the owner's Operations page (Project 4): volume, errors, latency, cost per day, refusals and
escalations, and budget status. Pure functions over log records (from the database when one is configured), so they
are unit-tested without Streamlit.

Project 2 records: outcome (drafted | escalated | fallback | greeting | off_topic | error | cap), latency_s,
api_calls, cost_usd, escalate. Greetings are free and never counted as requests. "Refusals" here are fallbacks
(the agent couldn't finish, so staff got a holding reply and a task).
"""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from src.requestlog import outcome_of


def percentile(values: list, p: float) -> float | None:
    """Nearest-rank percentile (same rule as Project 1's Admin page); p as a fraction."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[min(len(values) - 1, int(round(p * (len(values) - 1))))]


COUNTED = {"drafted", "escalated", "fallback", "off_topic", "error", "cap"}


def day(record: dict) -> str:
    return str(record.get("time", ""))[:10]


def latency(record: dict) -> float | None:
    if not record.get("api_calls") or outcome_of(record) == "error":
        return None
    value = record.get("latency_s")
    return float(value) if isinstance(value, int | float) else None


def escalated(record: dict) -> bool:
    return bool(record.get("escalate"))


def window(rows: list, days: int, today: date | None = None) -> list:
    today = today or datetime.now(UTC).date()
    first = (today - timedelta(days=days - 1)).isoformat()
    return [r for r in rows if day(r) >= first]


def budget(value: float | None, limit: float) -> dict:
    return {"value": value, "budget": limit, "ok": None if value is None else value <= limit}


def summary(rows: list, errors: list, days: int, p95_budget: float, cost_budget: float, today=None) -> dict:
    rows = [r for r in window(rows, days, today) if outcome_of(r) in COUNTED]
    errors = window(errors, days, today)
    timed = [x for x in (latency(r) for r in rows) if x is not None]
    called = [r for r in rows if r.get("api_calls") and outcome_of(r) != "error"]
    costs = [r["cost_usd"] for r in called if isinstance(r.get("cost_usd"), int | float)]
    cost_per_1000 = round(sum(costs) / len(costs) * 1000, 4) if costs else None
    p95 = percentile(timed, 0.95)
    failed = sum(1 for r in rows if outcome_of(r) == "error")
    per_day = defaultdict(lambda: {"requests": 0, "errors": 0, "cost_usd": 0.0, "latencies": []})
    for r in rows:
        d = per_day[day(r)]
        d["requests"] += 1
        d["errors"] += outcome_of(r) == "error"
        d["cost_usd"] += r.get("cost_usd") or 0.0
        if (x := latency(r)) is not None:
            d["latencies"].append(x)
    table = [
        {
            "day": k,
            "requests": v["requests"],
            "errors": v["errors"],
            "cost_usd": round(v["cost_usd"], 4),
            "p95_s": percentile(v["latencies"], 0.95),
        }
        for k, v in sorted(per_day.items(), reverse=True)
    ]
    return {
        "days": days,
        "requests": len(rows),
        "errors": failed,
        "error_rate": failed / len(rows) if rows else None,
        "app_errors": len(errors),
        "p50_s": percentile(timed, 0.5),
        "p95_s": p95,
        "cost_usd": round(sum(costs), 4),
        "cost_per_1000": cost_per_1000,
        "refusals": sum(1 for r in rows if outcome_of(r) == "fallback"),
        "escalations": sum(1 for r in rows if escalated(r)),
        "per_day": table,
        "budgets": {"p95_s": budget(p95, p95_budget), "cost_per_1000": budget(cost_per_1000, cost_budget)},
    }


def budget_label(b: dict, unit: str) -> str:
    if b["value"] is None:
        return f"No data yet (budget {unit.format(b['budget'])})"
    state = "Within budget" if b["ok"] else "Over budget"
    return f"{state}: {unit.format(b['value'])} (budget {unit.format(b['budget'])})"
