# Business Case (a projection)

A simulated client engagement for a fictional hotel group with two properties and synthetic data. **Every value
below is a projection from stated assumptions, not a measured saving.** Only the AI cost per email is measured.
Recalculate with your own numbers: `python scripts/business_case.py --scenarios`.

## The problem in business terms
Guest emails arrive all day: "Can we bring our dog?", "Can we stay one more night?", "We need to cancel", "The AC
is broken", and now and then an injury or a legal threat. Each one means opening the reservation system, checking
availability, finding the right policy for the right hotel, writing a reply and remembering to tell housekeeping
or the concierge. It is slow, and under pressure staff promise things only a manager can approve (a refund, a free
upgrade) or miss the email that needed a manager today.

## What the agent changes
- Staff start from a draft that already lists every request, cites the policy, states the booking facts and proposes
  the tasks. They review, edit and approve instead of writing from scratch.
- Refunds, comps, upgrades, cancellations and rate changes are never promised: they go to a manager queue.
- Emails that need a manager are flagged with a reason and a holding reply, in 100% of the labelled and held-out
  cases (8 + 2), whether the rules or the model caught them.

## Assumptions (base case) and why

| Assumption | Base | Why this number |
|---|---|---|
| Guest emails per property per day | 30 | A 150–250 room property; pre-arrival questions, requests during the stay, post-stay follow-ups |
| Minutes saved per email | 4 | Writing from scratch with lookups: about 6–8 minutes; reviewing and editing a cited draft: about 2–4 |
| Loaded staff cost per hour | $22 | Front desk / reservations agent with benefits |
| Unapproved comps or refunds avoided per property per week | 0.5 | A promise made to calm a guest, later honoured to avoid a complaint |
| Average unapproved comp or refund | $100 | One night's partial credit or a waived fee |
| AI cost per email | $0.0013 | **Measured**: $1.30 per 1,000 emails (final eval, Claude Haiku 5.5, 3 runs × 40 emails) |
| Hosting per year | $240 | A small always-on container; Streamlit Community Cloud is free for the demo |

## Projected results

<img src="images/business-case.png" alt="Calculator output: pessimistic, base and optimistic scenarios for 2 properties with emails per day, minutes saved, comps avoided, value and net value per year" width="640">

| Projected net value per year | 2 properties | 100 properties |
|---|---|---|
| Pessimistic (15 emails/day, 2 min saved, 0.25 comps/week) | $10,376 | $530,548 |
| **Base** (30 emails/day, 4 min saved, 0.5 comps/week) | **$37,052** | **$1,864,336** |
| Optimistic (45 emails/day, 6 min saved, 1 comp/week) | $82,387 | $4,131,125 |

Base case for 2 properties: 1,460 staff hours a year ($32,120), $5,200 of unapproved comps avoided, $268 running cost.
The 100-property figures scale emails and comps linearly and keep hosting flat, which understates real hosting and
support costs at that size.

## Sensitivity
The result moves almost one-for-one with **minutes saved per email** (labour is about 86% of the base-case value).
The AI cost barely matters: at $1.30 per 1,000 emails, 2 properties cost about $28 a year in model calls. So the
pilot must measure minutes saved first (docs/VALIDATION_CHECKLIST.md, section 3).

## Value not in the numbers
- **Safety and legal exposure:** an injury, harassment or press email reaches a manager the same morning, with the
  reason stated. The labelled and held-out sets caught every one; the held-out ones were caught by the model, not the
  rules, which is why both run.
- **Consistency across hotels:** the same question gets each property's own rule (Project 1's property-aware search).
- **An audit trail:** every email, agent step, draft and staff decision is logged for the owner.
- **Faster replies to guests,** which this projection doesn't value at all.

## Pilot plan (4 weeks, one property)
1. **Week 1, shadow mode:** the agent drafts replies for real (de-identified) emails; staff answer as usual. Compare.
2. **Weeks 2–3, assisted mode:** staff start from the draft, edit and approve. Time each email.
3. **Week 4:** review the numbers below with the general manager and decide.

## KPIs with go / no-go criteria

| KPI | Go | No-go |
|---|---|---|
| Missed escalations (an email that needed a manager and wasn't flagged) | 0 | Any |
| Drafts that promise a refund, comp, upgrade or change | 0 after the guard | Any reaching a guest |
| Drafts approved with no or minor edits | ≥ 60% | < 40% |
| Median handling time per email (draft review vs manual) | ≥ 2 minutes saved | < 1 minute saved |
| Facts flagged as ungrounded that turned out wrong | ≤ 1 per 100 emails | > 3 per 100 |
| Staff who want to keep it after the pilot | ≥ 70% | < 50% |

## Risks

| Risk | Mitigation |
|---|---|
| Staff approve drafts without reading them | Escalation and ungrounded-fact flags are shown prominently; approval rate and edit rate are monitored |
| A wrong-property answer (measured: the E12 sample email in all 3 final runs) | Planned fix: look up the sender's booking before the model runs, so the property is always known |
| Real PMS and email integration take longer than the agent | Read-only PMS access first; sending stays behind approval |
| Guest personal data in prompts and logs | Redaction and a persistent, access-controlled audit store are Project 4 |
| Cost grows with volume | Measured at $1.30 per 1,000 emails; prompt caching of the fixed instructions is the next saving |
