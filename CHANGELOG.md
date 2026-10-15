# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-15
### Added
- **Booking lookup before the model** (E12): the sender's booking pins the hotel when the guest wrote to the other
  property's inbox; policy search defaults to the booking's property.
- **Reply language guard:** the email's language is detected up front; a draft in another language is sent back once
  for a rewrite, then flagged. Spanish holding, escalation and fallback replies.
- **Planted instructions quarantined** before the model reads the email (English and Spanish notes to an automated
  reader); staff still see the original.
- **Persistent request and decision log** (`DATABASE_URL`: Neon Postgres or SQLite; unset = files as before) with
  **personal data redacted before storage**, 30-day retention and `scripts/retention.py`.
- **Staff role** next to the open Demo mode (`STAFF_PASSWORD`): report a draft for review, no per-session cap.
- **Operations page**, **budgets** (p95 ≤ 12.0 s, ≤ $2.00 per 1,000), **kill switch** (`KILL_SWITCH`).
- `docker compose up --build` with its own Postgres; CI runs the store tests against Postgres too.

### Changed
- Policy search synced to Project 1 v1.6.0 (Spanish hotel vocabulary).
- The promise guard no longer flags cited policy statements about member benefits ("Breakfast is complimentary only
  for Platinum loyalty members [P4]"), which it had also been replacing in replies.
- Privacy page and Admin note say where logs are kept.

### Measured (eval harness, live, 3 runs, 2026-10-15)
- Dev (40 emails): hard gates 100%; correct tool use 96% → 100%; citation accuracy 94% → 100%; routing 98%;
  p50 4.2 s, p95 8.3 s; $1.30 → $1.24 per 1,000.
- Wrong-hotel cases (E12, b10): right hotel 0/6 → 6/6. Held-out (21 emails incl. 13 added): escalation 9/9,
  injection resistance 100% (H03 had failed 1/3 and 2/3 in two re-runs), key facts 80% (H03, see decision 20).
  Visitor emails 30/30.

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
