# Screenshots

Every image here comes from the real app or real command output. Nothing is mocked up.

| File | How it's made |
|---|---|
| `inbox.png`, `agent-result.png`, `agent-result-dark.png`, `phone.png`, `escalation.png`, `injection.png`, `outbox.png`, `write-your-own.png`, `how-it-works.png`, `admin-list.png`, `admin-details.png`, `admin-diff.png` | `python scripts/capture_screenshots.py`: starts its own local app (port 8520) with an empty log folder and a one-time Admin password that is never printed or saved, runs the agent for real on E01, E05, E14 and one typed email, and captures each page |
| `demo.gif` | `python scripts/record_demo.py`: the "steps" part of the narrated demo recorded from the live app |
| `tests.png` | `python -m pytest -q --cov --cov-fail-under=90`, rendered with `scripts/render_terminal.py` |
| `eval.png` | `python -m eval.run_eval --replay eval/recorded/main-final.jsonl --gate`, rendered the same way |
| `business-case.png` | `python scripts/business_case.py --scenarios`, rendered the same way |

Re-capture after any UI change. Check every image for secrets before committing: the Admin page shows secrets only
as "set" or "missing".
