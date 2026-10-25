# Video script: Guest Request Agent (about 85 seconds)

I record this myself, in my own voice, over a screen recording of the live app. Until I do, the AI-narrated version is in `docs/video/demo-ai-voice.mp4` (narration at the end of this file). Setup and tips:
`RECORDING_GUIDE.md` in my portfolio folder. Read it twice, then talk from the bullets. `/` marks a natural pause.
Aim for 140–160 words a minute.

Before recording: open https://guest-request-agent.streamlit.app two minutes early so it's awake, browser zoom 125%.
The sample emails' results are reused, so the runs below cost nothing and look the same every time.

This app has no chat box, so the "back-and-forth" shot is the real loop staff use: the agent drafts, I edit, I
approve.

## Shot list

| Time | On screen | What I say |
|---|---|---|
| 0–10 s | Inbox with email E01 open | Hotels get emails with three questions in one. / Staff answer them by hand, and under pressure they promise things only a manager can approve. / This is a simulated hotel, with made-up guests. |
| 10–30 s | Click **Run the agent on this email**. The step timeline fills in | So the agent reads it, / finds all three requests, / looks up the booking, / checks each policy with the search from my first project, / and proposes tasks for the right team. / You can open every step. |
| 30–45 s | The draft; point at a citation badge, open the policy step | The draft quotes the hotel's own policy. / That badge is the source. / And every price and date in it is checked against what the tools returned. |
| 45–60 s | Click **Edit**, add one sentence, **Done editing**, **Approve & send (simulated)**; outbox and task board | Now I'm the staff member. / I add a line, I approve it. / Nothing's actually sent, it goes to a pretend outbox, / and only now are the tasks created. |
| 60–75 s | Open `?email=E14` (the injection), then **How it works** | This one tries to take over the agent. / It's treated as data, no refund, no other guest's booking. / On forty test emails, three runs, it caught every escalation and resisted every injection. |
| 75–85 s | New tab: type the URL, the app loads | It's live, no sign-in. / guest-request-agent dot streamlit dot app. |

## Exact inputs

| # | Where | Do exactly |
|---|---|---|
| 1 | https://guest-request-agent.streamlit.app/?email=E01 | Click **Run the agent on this email** |
| 2 | The draft | **Edit**, add `We look forward to meeting Biscuit!`, **Done editing**, **Approve & send (simulated)** |
| 3 | https://guest-request-agent.streamlit.app/?email=E14 | Click **Run the agent on this email** |

Checked 2026-10-24: the live app reports "up" on the health check. E01 and E14 are sample emails with saved results
from the v1.1.0 release; check both once on the live app before recording.

Proof point from the v1.1.0 release run (40 emails × 3 runs): escalation recall 100%, injection resistance 100%,
no forbidden promises 100%, $1.24 per 1,000 emails.

## LinkedIn caption (one sentence)

I built an agent that reads hotel guest emails, checks the booking and policy, drafts a cited reply, and never
sends or promises anything until a person approves it.

## AI narration (used in docs/video/demo-ai-voice.mp4)

Until I record my own voice, the demo video (1:12) is narrated by an AI voice (Kokoro `af_heart`, local) and labelled "AI-narrated" on screen and here. It was recorded from the live app with Playwright; the captions are the narration, timed to the voice. `/` marks a pause.

| Step | Narration |
|---|---|
| problem | Hotels get emails with three questions in one. / Staff answer them by hand, / and under pressure they promise things only a manager can approve. / This is a simulated hotel, with made-up guests. |
| tools | So the agent reads it, / finds the requests, / and looks up the booking with a tool. / Here's that step, and the booking record it got back. |
| cite | Then it checks each policy with the search from my first project. / The draft quotes the hotel's own policy, / and every price and date is checked against what the tools returned. |
| approve | Now I'm the staff member. / I add a line, and I approve it. / Nothing's really sent, it goes to a pretend outbox, / and only now are the tasks created. |
| proof | This email tries to take over the agent. / It's treated as data. No refund, and no other guest's booking. / On forty test emails, three runs each, it caught every escalation and resisted every injection. |
| live | It's live, with no sign-in. / The link and the code are below. |
