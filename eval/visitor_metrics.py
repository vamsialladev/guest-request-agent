"""First-email success for the visitor set: did a first-time visitor typing into "Write your own email" get a useful
result on their first try? Same idea as Project 1's first-question success.

Success means:
- greeting or off-topic text: the friendly reply, with no API call;
- a real email: a draft (or an escalation, when one is expected) that covers every labelled request, states no fact
  missing from the tool results, makes no forbidden promise and didn't need the fallback.
"""

from eval.metrics import fact_grounding, no_forbidden_promises, request_coverage


def score_visitor(case: dict, record: dict) -> dict:
    expect = case.get("expect", "email")
    outcome = record.get("outcome")
    reasons = []
    if expect in ("greeting", "off_topic"):
        if outcome != expect:
            reasons.append(f"expected {expect}, got {outcome}")
        if record.get("api_calls"):
            reasons.append("called the API")
    else:
        if outcome not in ("drafted", "escalated"):
            reasons.append(f"no draft ({outcome})")
        if bool(record.get("escalate")) != bool(case.get("expect_escalate")):
            reasons.append("escalation " + ("missed" if case.get("expect_escalate") else "not expected"))
        coverage = request_coverage(case, record)
        if coverage is not None and coverage < 1:
            reasons.append(f"covered {coverage:.0%} of requests")
        if not fact_grounding(case, record):
            reasons.append("ungrounded: " + ", ".join((record.get("checks") or {}).get("raw_ungrounded_facts", [])))
        if not no_forbidden_promises(case, record):
            reasons.append("forbidden promise")
        if record.get("fallback_reason"):
            reasons.append(f"fallback ({record['fallback_reason']})")
    return {
        "id": case["id"],
        "expect": expect,
        "outcome": outcome,
        "first_email_success": not reasons,
        "reasons": reasons,
        "api_calls": record.get("api_calls", 0),
        "latency_s": record.get("latency_s"),
        "tokens_in": record.get("tokens_in", 0),
        "tokens_out": record.get("tokens_out", 0),
    }


def summarize_visitor(scores: list[dict]) -> dict:
    n = len(scores)
    emails = [s for s in scores if s["expect"] == "email"]
    other = [s for s in scores if s["expect"] != "email"]
    return {
        "emails": n,
        "first_email_success": sum(s["first_email_success"] for s in scores) / n if n else None,
        "routing_correct": sum(s["first_email_success"] for s in other) / len(other) if other else None,
        "emails_handled": sum(s["first_email_success"] for s in emails) / len(emails) if emails else None,
    }
