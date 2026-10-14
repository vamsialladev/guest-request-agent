# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-14

First release. A simulated client engagement for a fictional hotel group, with synthetic data.

### Added
- Guest Request Agent: a manual Claude tool-use loop (Claude Haiku 5.5, effort low) with at most 6 model turns, a
  30 s timeout and one retry per call, parallel tool calls, a structured final answer (`draft_reply`) and a
  deterministic fallback (holding reply + front-desk task).
- Six typed tools: `find_booking` (sender-scoped), `check_availability`, `search_policy` (Project 1's retrieval at
  commit 1e7ae1e), `propose_task`, `propose_action` (always "needs manager approval"), `draft_reply`.
- Triage rules for escalation and prompt injection; guards for forbidden promises, fact grounding and citations.
- Staff approval: approve, edit or reject with a reason; simulated outbox, task board and manager queue.
- Streamlit app with Project 1's look: Inbox (30 sample emails), Write your own email, Outbox and tasks, How it
  works, Disclaimer and privacy, and the owner-only Admin page with the full request log and details dialog.
- Seeded synthetic bookings (80 reservations, edge cases) built on first start.
- Evals: 40 labelled emails, 10 visitor-style emails, 8 held-out emails; deterministic metrics, each unit-tested
  with a failing case; recorded runs re-scored in CI with gates on escalation, injection and forbidden promises.
- Docs: architecture, 17 decisions, business case with scenarios, demo script, validation checklist; CI, Docker,
  Dependabot, pre-commit.

### Measured (2026-10-14, 40 emails × 3 runs)
- Escalation recall, injection resistance and no forbidden promises: 100%. Request coverage and fact grounding:
  100%. Task routing 98%, citation accuracy 94%. Full draft p50 4.6 s, p95 8.4 s. $1.30 per 1,000 emails.
- Held-out set (8 emails, run once): 100% on every metric. Visitor set (10): first-email success 100%.
