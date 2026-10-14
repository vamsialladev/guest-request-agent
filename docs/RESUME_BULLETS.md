# Resume bullets (Project 2)

Honest, with real numbers from `eval/reports/`. Value is labelled "projected". Use under the umbrella role
"Senior Software Engineer · Apr 2023 – Present" as a project sub-entry; don't change any resume PDF from here.

**Guest Request Agent** (independent project; simulated hotel client, synthetic data)

- Built and deployed an AI agent (Claude Haiku 5.5, manual tool-use loop, six Pydantic-typed tools) that reads hotel
  guest emails, checks bookings, availability and policy, and drafts cited replies with proposed staff tasks; staff
  approve every send, and refunds, upgrades and booking changes are only ever proposed to a manager.
- Gated quality in CI on recorded runs: 100% escalation recall, 100% prompt-injection resistance and zero forbidden
  promises over 40 labelled emails × 3 runs, 100% on a held-out set, $1.30 per 1,000 emails, 8.4 s p95; found and
  fixed eight bugs in my own checks before changing the model.
- Shipped with 237 tests (98% coverage), sender-scoped booking lookups, redacted request logs, an owner admin page,
  17 recorded decisions and a projected ~$37K/yr net value for two properties (range $10K–$82K, from stated assumptions).
