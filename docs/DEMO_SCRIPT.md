# Demo Script (about 2 minutes)

Recorded from the **live app** by `python scripts/record_demo.py` (Playwright, burned-in captions, no voice; see
decision 24). The "Narration" column is what the screen recording shows step by step; the video I record in my own
voice follows `docs/VIDEO_SCRIPT.md`.
Real agent runs, nothing staged. The Admin segment is recorded from a local run of the same code with a throwaway
test password and its own empty log (the live Admin password is never typed by a script), and is captioned so.

| Time | Screen | Narration |
|---|---|---|
| 0:00 | Title card | Guest Request Agent: a simulated client project, part two of five. |
| 0:04 | Inbox, email E01 opens | A guest writes with three requests: a dog, a late check-out and an airport pickup. |
| 0:12 | Step timeline | The agent finds every request. It looks up her booking, checks the hotel's policies with the search from project one, and proposes tasks for the right teams. |
| 0:26 | Draft with citation badges | The draft cites every policy it uses, and every price and date is checked against the tool results before staff see it. |
| 0:36 | Edit, then Approve | Staff stay in control. They can edit the reply, then approve it. Nothing is really sent: it goes to a simulated outbox. |
| 0:46 | Outbox and task board | Only now are the tasks created, for the concierge and the front desk. |
| 0:53 | Email E05, escalated | An angry refund demand goes straight to a manager, with the reason and a polite holding reply. The agent never promises a refund. |
| 1:06 | Email E14, injection | This email tries to take over the assistant. It's treated as data: no refund, and no other guest's booking. |
| 1:18 | How it works | It's measured on forty labelled emails, three runs each: every escalation caught, every injection resisted, no forbidden promises, at about a dollar thirty per thousand emails. |
| 1:33 | Admin, local run (captioned) | The owner sees every request: each agent step, the draft, and exactly what staff changed before sending. |
| 1:45 | End card with links | Try the live app, or read the code and the decisions. The links are on screen. |

## Captions (burned in, for muted viewers)
- Three requests in one email. The agent finds them all.
- Booking, policy (Project 1's search) and tasks, step by step.
- Cited draft. Every price and date checked against the tools.
- Edit, then approve. Nothing is really sent.
- Tasks are created only on approval.
- Angry refund demand → manager, with a holding reply.
- Prompt injection treated as data: no refund, no leak.
- 40 emails × 3 runs: 100% escalations, injections, no promises.
- Admin (local run of the same app): every step, draft vs sent.

## Manual run (if you record it yourself)
1. Open https://guest-request-agent.streamlit.app/?email=E01 and click "Run the agent on this email".
2. Expand "Found booking BR-1042" and a "Policy" step; point at the citation badges.
3. Edit: add "We look forward to meeting Biscuit!", Done editing, Approve & send (simulated).
4. Outbox and tasks: open the sent reply; show the two tasks.
5. Inbox `?email=E05`, then `?email=E14`.
6. How it works: the measured results table.
