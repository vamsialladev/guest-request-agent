# Contributing

## Workflow
1. Create a branch from `main`: `feature/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
2. Make the change, with tests (and eval cases where behaviour changes).
3. Run the checks below locally.
4. Open a pull request. CI must pass before merging.

## Checks before every pull request
```bash
ruff check . && ruff format --check .
python -m pytest -q --cov
pip-audit -r requirements.txt
python scripts/sync_policy.py --check
python -m eval.run_eval --replay eval/recorded/main-final.jsonl --gate --no-report
```
For prompt, tool, guard or model changes, also run a real eval (`make eval`, about $0.05) and read the drafts for
the injection and escalation cases by hand. A metric is code: when a result looks too good or too bad, check the
grader before the model (docs/DECISIONS.md, "What the eval taught me").

Keep logic in `src/` with unit tests; pages in `views/` only wire it to the UI. Escape every dynamic value with
`src/display.py` before it goes into HTML.

## How to extend
- **A new tool:** a Pydantic input model in `src/models.py`, a function in `src/tools.py` returning
  `(result, summary)`, an entry in `TOOLS` and `tool_definitions()`, unit tests in `tests/test_tools.py`.
  Tools only read or *propose*; anything that changes a booking or sends something stays behind staff approval.
- **A new escalation rule:** a pattern in `src/triage.py`, a positive and a negative test in
  `tests/test_triage.py`, and an eval case.
- **A new eval case:** a line in `eval/cases.jsonl` (labels are documented in `eval/metrics.py`). Never edit
  `eval/heldout.jsonl` to make a result pass.
- **Updated hotel policies:** change them in Project 1, then `python scripts/sync_policy.py --ref <commit>`.
- **Another property:** add it to the generator (`scripts/make_data.py`), `branding.toml` and Project 1's documents.

## Commit messages
Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for | Example |
|---|---|---|
| `feat:` | New behavior | `feat(tools): add a spa availability tool` |
| `fix:` | Bug fix | `fix(guards): don't flag negated offers as promises` |
| `test:` | Tests or eval cases | `test(eval): add a Spanish injection case` |
| `docs:` | Documentation | `docs: record the language-label finding` |
| `chore:` | Tooling, CI, dependencies | `chore(ci): add the held-out gate` |
| `refactor:` | No behavior change | `refactor(agent): split the guard step` |

Versions follow [Semantic Versioning](https://semver.org/); record changes in `CHANGELOG.md`.
