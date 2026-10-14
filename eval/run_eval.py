"""Run the eval on the real model, or re-score a recorded run without the API (what CI does).

    python -m eval.run_eval --set main --runs 3 --price-in 0.10 --price-out 0.50 --label final   # real API
    python -m eval.run_eval --replay eval/recorded/main-final.jsonl --gate                       # no API, free

Sets: main (eval/cases.jsonl, 40 labelled emails), visitor (eval/visitor.jsonl, 10 emails typed the way a first-time
visitor writes), heldout (eval/heldout.jsonl, 8 emails written last and never tuned on).

A live run saves every result to eval/recorded/<set>-<label>.jsonl (the same record the app logs) and a markdown + JSON
report to eval/reports/. Replay re-scores those records with the current metrics, so CI gates are deterministic.
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.metrics import aggregate, consistency, gate_failures, rate, score_case  # noqa: E402
from eval.visitor_metrics import score_visitor, summarize_visitor  # noqa: E402

SETS = {
    "main": ROOT / "eval" / "cases.jsonl",
    "visitor": ROOT / "eval" / "visitor.jsonl",
    "heldout": ROOT / "eval" / "heldout.jsonl",
}
RECORDED = ROOT / "eval" / "recorded"
REPORTS = ROOT / "eval" / "reports"
VISITOR_SENDER = "visitor@example.com"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_cases(name: str) -> list[dict]:
    inbox = {e["id"]: e for e in load_jsonl(ROOT / "data" / "inbox.jsonl")}
    cases = load_jsonl(SETS[name])
    for c in cases:
        if "inbox_id" in c:
            c["email"] = inbox[c["inbox_id"]]
    return cases


def email_of(case: dict):
    from src.agent import Email

    e = case["email"]
    return Email(
        sender=e.get("from") or VISITOR_SENDER,
        subject=e.get("subject", ""),
        body=e["body"],
        sender_name=e.get("name", ""),
    )


def run_live(cases: list[dict], set_name: str, runs: int, label: str, delay: float = 0.0) -> list[dict]:
    from src import policy_search
    from src.service import process

    RECORDED.mkdir(parents=True, exist_ok=True)
    out_path = RECORDED / f"{set_name}-{label}.jsonl"
    rows = []
    with out_path.open("w", encoding="utf-8") as f:
        for run in range(1, runs + 1):
            for case in cases:
                prop = case["email"]["property"]
                source = "write" if set_name == "visitor" else "eval"
                result, record = process(
                    email_of(case),
                    prop,
                    source=source,
                    session_id=f"eval-{label}-{run}",
                    log=False,
                    email_id=case["id"],
                    keyword_matches=lambda text, p=prop: policy_search.keyword_matches(text, p),
                )
                record = {**record, "sources": result.sources}  # lets later metric fixes re-score without the API
                row = {
                    "set": set_name,
                    "label": label,
                    "run": run,
                    "case_id": case["id"],
                    "record": record,
                    "time": datetime.now(UTC).isoformat(timespec="seconds"),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                rows.append(row)
                status = record["outcome"] + (" (escalated)" if record["escalate"] else "")
                print(
                    f"run {run} {case['id']}: {status}, {record['api_calls']} calls, {record['latency_s']:.1f}s",
                    flush=True,
                )
                if delay:
                    time.sleep(delay)
    print(f"Recorded {len(rows)} results to {out_path.relative_to(ROOT)}")
    return rows


def score_rows(rows: list[dict], cases: list[dict], set_name: str):
    by_id = {c["id"]: c for c in cases}
    runs: dict[int, list[dict]] = {}
    for row in rows:
        case = by_id.get(row["case_id"])
        if case is None:
            continue
        scorer = score_visitor if set_name == "visitor" else score_case
        runs.setdefault(row["run"], []).append(scorer(case, row["record"]))
    return [runs[r] for r in sorted(runs)]


def summarize(run_scores: list[list[dict]], set_name: str, price_in, price_out) -> dict:
    if set_name == "visitor":
        per_run = [summarize_visitor(scores) for scores in run_scores]
    else:
        per_run = [aggregate(scores, price_in, price_out) for scores in run_scores]
    keys = per_run[0].keys()
    combined = {}
    for k in keys:
        values = [r[k] for r in per_run if isinstance(r[k], int | float) and r[k] is not None]
        if not values:
            combined[k] = {"mean": None, "min": None, "max": None}
            continue
        combined[k] = {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}
    return {"per_run": per_run, "combined": combined, "consistency": consistency(run_scores)}


PCT = {
    "request_coverage",
    "fact_grounding",
    "correct_tool_use",
    "escalation_recall",
    "false_escalation_rate",
    "injection_resistance",
    "no_forbidden_promises",
    "task_routing",
    "citation_accuracy",
    "key_facts",
    "language",
    "first_email_success",
    "routing_correct",
    "emails_handled",
}
LABELS = {
    "request_coverage": "Request coverage",
    "fact_grounding": "Fact grounding (model draft)",
    "correct_tool_use": "Correct tool use",
    "escalation_recall": "Escalation recall (gate 100%)",
    "false_escalation_rate": "False-escalation rate",
    "injection_resistance": "Injection resistance (gate 100%)",
    "no_forbidden_promises": "No forbidden promises (gate 100%)",
    "task_routing": "Task routing accuracy",
    "citation_accuracy": "Citation accuracy (strict)",
    "key_facts": "Key facts stated",
    "language": "Reply in the guest's language",
    "p50_latency_s": "Latency p50",
    "p95_latency_s": "Latency p95",
    "avg_tool_steps": "Average tool steps",
    "avg_model_turns": "Average model turns",
    "fallbacks": "Fallback drafts",
    "cost_per_1000_emails": "Cost per 1,000 emails",
    "emails": "Emails per run",
    "first_email_success": "First-email success",
    "routing_correct": "Greetings and off-topic answered without the API",
    "emails_handled": "Real emails fully handled",
}


def fmt(key: str, v) -> str:
    if v is None:
        return "–"
    if key in PCT:
        return f"{v:.0%}"
    if key.endswith("_s"):
        return f"{v:.1f} s"
    if key.startswith("cost"):
        return f"${v:.2f}"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def fmt_range(key: str, stat: dict) -> str:
    if stat["mean"] is None:
        return "–"
    text = fmt(key, stat["mean"])
    if stat["min"] != stat["max"]:
        text += f" ({fmt(key, stat['min'])}–{fmt(key, stat['max'])})"
    return text


def write_report(set_name: str, label: str, summary: dict, run_scores, meta: dict) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    day = meta["date"]
    base = REPORTS / f"{set_name}-{day}-{label}"
    lines = [
        f"# Eval report: {set_name} set, {label}",
        "",
        f"- Date: {day} · Model: {meta['model']} · Effort: {meta['effort']} · Runs: {len(run_scores)} · "
        f"Emails per run: {len(run_scores[0])}",
        f"- Source: `{meta['source']}` (re-score without the API: `python -m eval.run_eval --replay {meta['source']}`)",
        f"- Prices: ${meta['price_in']} / ${meta['price_out']} per million input / output tokens",
        "- Synthetic data: fictional guests and a simulated hotel group. Nothing was sent.",
        "",
        "## Summary",
        "",
        "| Metric | Value (range over runs) |",
        "|---|---|",
    ]
    for key, stat in summary["combined"].items():
        if key in ("tokens_in", "tokens_out"):
            continue
        lines.append(f"| {LABELS.get(key, key)} | {fmt_range(key, stat)} |")
    if summary["consistency"] is not None:
        lines.append(f"| Same escalation decision and tools in every run | {summary['consistency']:.0%} |")
    failures = [f for r in summary["per_run"] for f in gate_failures(r)] if set_name != "visitor" else []
    lines += [
        "",
        "## Gates",
        "",
        "All gates passed." if not failures else "\n".join(f"- FAILED: {f}" for f in failures),
    ]
    lines += ["", "## Per case (run 1)", ""]
    if set_name == "visitor":
        lines += ["| Case | Expected | Outcome | Success | Why not |", "|---|---|---|---|---|"]
        for s in run_scores[0]:
            lines.append(
                f"| {s['id']} | {s['expect']} | {s['outcome']} | {'✓' if s['first_email_success'] else '✗'} | "
                f"{'; '.join(s['reasons']) or ''} |"
            )
    else:
        lines += [
            "| Case | Outcome | Coverage | Grounded | Tools | Escalation | Routing | Citations | Problems |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for s in run_scores[0]:

            def mark(v):
                return "–" if v is None else ("✓" if v else "✗")

            esc = "✓" if s["escalated"] == s["expect_escalate"] else ("missed" if s["expect_escalate"] else "extra")
            problems = s["violations"] + [f"ungrounded {f}" for f in s["ungrounded"]]
            if s["fallback"]:
                problems.append(f"fallback: {s['fallback']}")
            lines.append(
                f"| {s['id']} | {s['outcome']} | {fmt('request_coverage', s['request_coverage'])} | "
                f"{mark(s['fact_grounding'])} | {mark(s['correct_tool_use'])} | {esc} | {mark(s['task_routing'])} | "
                f"{mark(s['citation_accuracy'])} | {'; '.join(problems)} |"
            )
    if len(run_scores) > 1 and set_name != "visitor":
        lines += ["", "## Misses in any run", ""]
        for i, scores in enumerate(run_scores, 1):
            for s in scores:
                misses = [
                    k
                    for k in (
                        "fact_grounding",
                        "correct_tool_use",
                        "task_routing",
                        "citation_accuracy",
                        "key_facts",
                        "injection_resistance",
                    )
                    if s[k] is False
                ]
                if s["request_coverage"] is not None and s["request_coverage"] < 1:
                    misses.append(f"coverage {s['request_coverage']:.0%}")
                if s["escalated"] != s["expect_escalate"]:
                    misses.append("escalation")
                if misses:
                    lines.append(f"- run {i} {s['id']}: {', '.join(misses)}")
    base.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {"meta": meta, "summary": summary, "scores": run_scores}
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return base.with_suffix(".md")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", choices=list(SETS), default="main")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--label", default="dev", help="name for the recorded file and report")
    parser.add_argument("--replay", type=Path, help="re-score a recorded JSONL instead of calling the API")
    parser.add_argument("--price-in", type=float, default=None, help="USD per million input tokens")
    parser.add_argument("--price-out", type=float, default=None, help="USD per million output tokens")
    parser.add_argument("--gate", action="store_true", help="exit 1 if a gate fails")
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--only", help="comma-separated case ids (debugging)")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between emails (rate limits)")
    args = parser.parse_args(argv)

    from src.config import LLM_EFFORT, LLM_MODEL

    if args.replay:
        rows = load_jsonl(args.replay)
        set_name = rows[0]["set"] if rows else args.set
        label = rows[0]["label"] if rows else args.label
        source = args.replay.as_posix() if not args.replay.is_absolute() else args.replay.relative_to(ROOT).as_posix()
        day = rows[0]["time"][:10] if rows else datetime.now(UTC).date().isoformat()
    else:
        set_name, label = args.set, args.label
        cases = load_cases(set_name)
        if args.only:
            wanted = set(args.only.split(","))
            cases = [c for c in cases if c["id"] in wanted]
        rows = run_live(cases, set_name, args.runs, label, args.delay)
        source = f"eval/recorded/{set_name}-{label}.jsonl"
        day = datetime.now(UTC).date().isoformat()
    cases = load_cases(set_name)
    run_scores = score_rows(rows, cases, set_name)
    if not run_scores:
        print("Nothing to score.")
        return 1
    models = {r["record"].get("model") for r in rows if r["record"].get("model")}
    meta = {
        "set": set_name,
        "label": label,
        "date": day,
        "model": ", ".join(sorted(models)) or LLM_MODEL,
        "effort": LLM_EFFORT or "default",
        "price_in": args.price_in,
        "price_out": args.price_out,
        "source": source,
        "runs": len(run_scores),
    }
    summary = summarize(run_scores, set_name, args.price_in, args.price_out)
    for key, stat in summary["combined"].items():
        if key not in ("tokens_in", "tokens_out"):
            print(f"{LABELS.get(key, key):40s} {fmt_range(key, stat)}")
    if not args.no_report:
        path = write_report(set_name, label, summary, run_scores, meta)
        print(f"Report: {path.relative_to(ROOT)}")
    failures = [f for r in summary["per_run"] for f in gate_failures(r)] if set_name != "visitor" else []
    for f in failures:
        print("GATE FAILED:", f)
    if set_name == "visitor":
        print(f"First-email success: {rate(s['first_email_success'] for s in run_scores[0]):.0%}")
    return 1 if (args.gate and failures) else 0


if __name__ == "__main__":
    sys.exit(main())
