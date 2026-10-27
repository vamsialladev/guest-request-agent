"""Red-team suite for this app: the shared corpus (hotel-ai-platform) plus this app's own cases (redteam/cases.jsonl),
run through this app's real defences, no API calls; runs in CI.

    python scripts/run_redteam.py                 print the summary, exit 1 on any new miss
    python scripts/run_redteam.py --report        also rewrite docs/redteam-report.md

Layers:
    input      a guest email -> shared input check (flags, card/ID numbers replaced) + the planted-instruction
               quarantine the model reads through (src/triage.py)
    output     a draft -> this app's promise guard (src/guards.py) + the shared output check
    retrieved  text from a tool or document -> the same quarantine
    tool       a tool call the model might make -> the real tool with a guest's identity (sender-scoped lookups,
               actions that are only proposals)

Guest emails are never dropped, so for a shared input case that expects "block", "detected" counts: the attack is
flagged on the trace and either quarantined before the model or stopped by a tool (redteam/overrides.json says why).
"""

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hotelplatform import guardrails, jsonlog, redteam  # noqa: E402

from src import guards, ops, triage  # noqa: E402
from src.tools import ToolContext, execute  # noqa: E402

CASES = ROOT / "redteam" / "cases.jsonl"
OVERRIDES = ROOT / "redteam" / "overrides.json"
REPORT = ROOT / "docs" / "redteam-report.md"
GUEST = "elena.marsh@example.com"  # owns BR-1042 in the synthetic bookings


def input_layer(case):
    v = ops.check_email(case.text)
    _, removed = triage.quarantine(case.text)
    attacks = [f for f in v.flags if f in guardrails.ATTACKS]
    # Several categories can match one text; the case's own category counts if it is among them.
    reason = case.reason if case.reason in attacks else (attacks[0] if attacks else None)
    if removed:
        return redteam.Outcome("quarantine", reason, "removed before the model")
    if any(f.startswith("pii_redacted") for f in v.flags):
        return redteam.Outcome("redact", None, ", ".join(v.flags))
    if attacks:
        return redteam.Outcome("flag", reason, "flagged on the trace; the model still reads it")
    return redteam.Outcome("allow")


def output_layer(case):
    sources = case.context.get("sources", [])
    text, removed = guards.remove_promises(case.text)
    v = ops.check_draft(text, sources, case.context.get("input", ""))
    if not v.allowed:
        return redteam.Outcome("block", v.reason)
    if removed or v.text != case.text:
        return redteam.Outcome("redact", None, "promise removed" if removed else ", ".join(v.flags))
    return redteam.Outcome("allow")


def retrieved_layer(case):
    _, removed = triage.quarantine(case.text)
    return redteam.Outcome("quarantine" if removed else "allow")


def tool_layer(case):
    """Blocked = nothing outside the sender's own bookings came back, or the action is only a proposal."""
    name, _, arg = case.text.partition(":")
    # A name lookup only runs for a sender with no bookings of their own, so that case writes from a new address.
    sender = "new.guest@example.com" if name == "find_booking_by_name" else GUEST
    ctx = ToolContext(sender_email=sender, property="beach-resort")
    own = {b.booking_id for b in ctx.store.by_email(sender)}
    if name == "find_booking":
        content, error = execute(ctx, "find_booking", {"booking_ref": arg})
    elif name == "find_booking_by_name":
        content, error = execute(ctx, "find_booking", {"guest_name": arg})
    elif name == "propose_action":
        content, error = execute(ctx, "propose_action", {"action_type": arg, "reason": "red team"})
    elif name == "search_policy":
        content, error = execute(ctx, "search_policy", {"question": arg})
    else:
        raise ValueError(f"unknown tool case {name}")
    data = json.loads(content) if content.startswith("{") else {}
    leaked = {b.get("booking_id") for b in data.get("bookings", []) if isinstance(b, dict)} - own - {None}
    if error or data.get("status") == "needs manager approval" or (name.startswith("find_booking") and not leaked):
        return redteam.Outcome("block", None, content[:100])
    return redteam.Outcome("allow", None, content[:100])


HANDLERS = {"input": input_layer, "output": output_layer, "retrieved": retrieved_layer, "tool": tool_layer}


def overrides() -> dict:
    return json.loads(OVERRIDES.read_text(encoding="utf-8"))


def shared_cases_for_this_app() -> list:
    o = overrides()
    cases = redteam.shared_cases()
    for c in cases:
        if c.id in o["expect"]:
            c.expect, c.reason = o["expect"][c.id], None  # a different safe outcome, so no single reason to match
    return cases


def normalise(results) -> list:
    """For an input case expecting 'block': detected (quarantined or flagged) is this app's safe outcome."""
    for r in results:
        if r.case.layer == "input" and r.case.expect == "block" and r.outcome.verdict in ("quarantine", "flag"):
            r.outcome = redteam.Outcome(
                "block", r.outcome.reason, f"detected ({r.outcome.verdict}): {r.outcome.detail}"
            )
    return results


def run():
    jsonlog.configure("redteam", "ci", stream=io.StringIO())
    shared = normalise(redteam.run(shared_cases_for_this_app(), HANDLERS))
    own = redteam.run(redteam.load_cases(CASES), HANDLERS)
    return shared, own


def known_gaps() -> set[str]:
    lines = (ROOT / "redteam" / "known_gaps.txt").read_text(encoding="utf-8").splitlines()
    return {ln.split()[0] for ln in lines if ln.strip() and not ln.startswith("#")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    shared, own = run()
    for name, results in (("shared corpus", shared), ("this app's cases", own)):
        s = redteam.score(results)
        print(f"{name}: {s['passed']}/{s['cases']} passed; attacks stopped {s['attacks_stopped']}/{s['attacks']}; "
              f"false alarms {s['false_alarms']}/{s['controls']}")  # fmt: skip
        for r in results:
            if not r.passed:
                print(f"  FAIL {r.case.id} [{r.case.category}] expected {r.case.expect}, got {r.outcome.verdict}")
    if args.report:
        note = "For this app an input 'block' means detected: " + overrides()["_why"]
        REPORT.write_text(
            redteam.report_markdown(shared, "Red-team report: shared corpus through this app", note)
            + "\n"
            + redteam.report_markdown(own, "Red-team report: this app's own cases (held out)"),
            encoding="utf-8",
            newline="\n",
        )
    new_failures = [r.case.id for r in shared + own if not r.passed and r.case.id not in known_gaps()]
    if new_failures:
        print("GATE FAILED: new red-team failures:", ", ".join(new_failures))
    return 1 if new_failures else 0


if __name__ == "__main__":
    sys.exit(main())
