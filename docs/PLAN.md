# Plan: Guest Request Agent (Project 2)

**Goal.** Staff paste or pick a guest email; an agent finds every request, looks up the booking, checks availability and
hotel policy (Project 1's retrieval, copied at a pinned version), drafts a cited reply and proposes staff tasks. A staff
member approves, edits or rejects. Nothing is ever really sent. Simulated client engagement, synthetic data.

**Shape.**
1. `scripts/make_data.py` builds a seeded SQLite bookings database (2 properties, ~80 reservations over 45 days, edge
   cases) and `data/inbox.jsonl` holds 30 hand-written sample emails.
2. `scripts/sync_policy.py` copies Project 1's keyword retrieval and documents into `src/policy/` (keyword-only, light).
3. `src/triage.py` runs first and never calls the API: greetings, off-topic, escalation rules, prompt-injection markers.
4. `src/agent.py` is a manual Claude tool-use loop (Claude Haiku 5.5): at most 6 model turns, a timeout and one retry
   per call, a deterministic fallback when the API or a tool fails, and a structured final answer (`draft_reply`).
5. Tools are small pure functions with Pydantic inputs: `find_booking` (the sender's address comes from the system, never
   from the email text), `check_availability`, `search_policy`, `propose_task`, `propose_action` (always "needs manager
   approval"), `draft_reply`.
6. `src/guards.py` checks every draft: forbidden promises (refunds, comps, upgrades, cancellations, rate changes) and fact
   grounding (every date, price, time and room number must appear in a tool result).
7. `src/approval.py`: approve / edit / reject with reason; only approval moves a reply to the simulated outbox and
   proposed tasks to the board.
8. Streamlit app with Project 1's look: Inbox, Write your own email, Outbox and tasks, How it works, Disclaimer and
   privacy, hidden Admin (Project 1's gate and request log, extended with agent steps and draft-vs-final diff).
9. Evals: 40 labelled cases + 10 visitor emails + 8 held-out emails; deterministic metrics, each unit-tested with a
   failing case; real runs recorded to JSONL so CI re-scores them without the API.

**Order.** Data and tools → triage and guards → agent loop (mocked) → app → tests and CI → push → real eval (dev, then
final `--runs 3`) → deploy → portfolio, video, posts.

**Budget.** Under $3 of real API spend: mocked model calls for development, real calls only for the eval runs and the
live smoke test.
