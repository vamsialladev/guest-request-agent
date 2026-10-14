## What changed

## Why

## How it was tested
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `python -m pytest -q --cov` passes (coverage ≥ 90%)
- [ ] `python -m eval.run_eval --replay eval/recorded/main-final.jsonl --gate` passes
- [ ] If the prompt, tools or guards changed: a new real eval run (`make eval`), result: ___ (before: ___)

## Screenshots (if the app's behavior changed)
