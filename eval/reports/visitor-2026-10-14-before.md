# Eval report: visitor set, before

- Date: 2026-10-14 · Model: claude-haiku-5-5 · Effort: low · Runs: 1 · Emails per run: 10
- Source: `eval/recorded/visitor-before.jsonl` (re-score without the API: `python -m eval.run_eval --replay eval/recorded/visitor-before.jsonl`)
- Prices: $0.1 / $0.5 per million input / output tokens
- Synthetic data: fictional guests and a simulated hotel group. Nothing was sent.

## Summary

| Metric | Value (range over runs) |
|---|---|
| Emails per run | 10.0 |
| First-email success | 100% |
| Greetings and off-topic answered without the API | 100% |
| Real emails fully handled | 100% |

## Gates

All gates passed.

## Per case (run 1)

| Case | Expected | Outcome | Success | Why not |
|---|---|---|---|---|
| V01 | greeting | greeting | ✓ |  |
| V02 | off_topic | off_topic | ✓ |  |
| V03 | email | drafted | ✓ |  |
| V04 | email | drafted | ✓ |  |
| V05 | email | escalated | ✓ |  |
| V06 | email | drafted | ✓ |  |
| V07 | email | drafted | ✓ |  |
| V08 | email | drafted | ✓ |  |
| V09 | email | drafted | ✓ |  |
| V10 | email | drafted | ✓ |  |
