# Validation Checklist

What is already measured with the real API, and what still needs a person.

## Done (measured with Claude Haiku 5.5, saved in `eval/`)
- [x] 40 labelled emails, 2 dev runs and a final run with `--runs 3`: every metric, latency and cost per 1,000 emails
      (`eval/reports/main-*-final.md`, raw results in `eval/recorded/main-final.jsonl`).
- [x] 10 visitor-style emails typed the way a first-time visitor writes (`eval/reports/visitor-*.md`).
- [x] 8 held-out emails written after all tuning, run once (`eval/reports/heldout-*.md`).
- [x] Injection and escalation drafts read by hand in every run (see DECISIONS.md, "What the eval taught me").
- [x] The app run locally end to end: Inbox → agent steps → draft → approve → outbox and task board.

## 1. Owner checks on the live app (about 10 minutes)
The assistant can't sign in to your live Admin page for you (it never types your password into a website).
1. Open `https://guest-request-agent.streamlit.app/admin` and sign in with your admin password.
2. Check: health tiles, secrets show **set** (never a value), the request list shows the smoke-test emails.
3. Select a row: the "Request details" dialog shows the agent steps, the draft vs final diff and the checks.
4. Download one request as JSON and confirm it contains no key or password.
5. Wait 30 minutes or click Sign out: the page locks.

## 2. Spending limit (2 minutes)
Anthropic Console → Settings → Limits: set a monthly limit (for example $10). The app's own caps are 10 emails per
session and 150 per day, but the Console limit is the real stop.

## 3. Manual baseline for the business case (about 20 minutes)
The most uncertain assumption is **minutes saved per email**.
1. Pick 5 emails from the Inbox (one multi-request, one availability, one policy, one task, one escalation).
2. **Without the app:** write each reply yourself, looking up the booking and the policy documents
   (`data/policy/raw/`). Time each one.
3. **With the app:** time how long it takes to review, edit and approve the agent's draft.
4. Run the calculator with your number:
   ```bash
   python scripts/business_case.py --minutes-saved <your measured number> --scenarios
   ```
Record it in BUSINESS_CASE.md under Assumptions ("Measured on 5 emails: manual X min, with the agent Y min"), and
say it was a small, self-run test.

## 4. Held-out emails from someone else (about 30 minutes)
I wrote the labelled emails, the visitor emails and the held-out emails. Ask someone who has worked in a hotel to
write 10 guest emails without looking at the code, add them to a new `eval/external.jsonl` with labels, and run them
once. Report the result separately, whatever it is.

## 5. Screenshots and video
- [x] Screenshots in `docs/images/` captured from the real app (`scripts/capture_screenshots.py`).
- [x] Narrated demo video recorded from the live app (`scripts/record_demo.py`); every frame checked for secrets.
