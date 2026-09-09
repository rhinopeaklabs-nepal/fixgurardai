Development plan, Day 1–21. Marking what's already done so the remaining days are the real schedule.

**Week 1 — engine (Days 1–7)**

| Day | Date | Work | Status |
|---|---|---|---|
| 1 | Sep 3 | Project scaffold, FastAPI + SQLite, config, error envelope | done |
| 2 | Sep 4 | Playwright worker, console capture, navigation-loop detection | done |
| 3 | Sep 5 | Form parser, type-aware payloads, sensitive-field refusal | done |
| 4 | Sep 6 | Silent-failure verdict matrix, network interception | done |
| 5 | Sep 7 | Health scoring, grade bands, critical ceiling | done |
| 6 | Sep 8 | React dashboard, SSE progress, report view | done |
| 7 | Sep 9 | Share links, public report, client/developer modes | done |

**Week 2 — detectors and Module 1 (Days 8–14)**

| Day | Date | Work | Status |
|---|---|---|---|
| 8 | Sep 10 | Route crawling, soft-404 detection, re-render observer | done |
| 9 | Sep 11 | Reachability: DNS, TLS expiry, redirect chain | done |
| 10 | Sep 12 | Surgical Prompt Studio — scoping engine, guardrails | done |
| 11 | Sep 13 | Agents 1–3, deterministic-first with optional LLM | done |
| 12 | Sep 14 | PDF certificate, verification badge | done |
| 13 | Sep 15 | Accessibility, mobile viewport, Core Web Vitals | done |
| 14 | Sep 16 | Multi-page scans, before/after comparison, `/architecture` | done |

**Week 3 — deploy and prove (Days 15–21)**

Days 15–17 were pulled forward and finished on Sep 6, so the schedule below is
no longer the real one. What actually happened after that is in the commit
history and summarised in `fixguard/docs/SUBMISSION.md`.

| Day | Date | Work | Status |
|---|---|---|---|
| 15 | Sep 17 | VPS: upload, bootstrap, swap, TLS, `docker compose up` | done Sep 6 |
| 16 | Sep 18 | Dashboard to Web Hosting, `.htaccess`, CORS, end-to-end check | done Sep 6 — superseded: dashboard and API ship as one Coolify stack on the VPS, Web Hosting serves the marketing site instead |
| 17 | Sep 19 | AI Builder marketing page, badge in footer | done Sep 6 |
| 18 | Sep 20 | Audit 5 real sites, fix whatever breaks | to do |
| 19 | Sep 21 | Re-run acceptance suite against production, fix edge cases | partly — suite green, 36 unit checks; re-run before submitting |
| 20 | Sep 22 | Record and edit the 2-minute video | to do |
| 21 | Sep 23 | README, traceability, screenshots, submission package | draft in `fixguard/docs/SUBMISSION.md`; evidence still to capture |

**Unplanned work that took the freed time (Sep 6–9).** Accounts and per-owner
scoping, an admin console with persisted metrics, a privacy policy and terms,
security headers nginx was dropping, and five real bugs found by running the
thing in public — two routes returning 500 on every call, the marketing site
badge blocked by CORS, and three false positives in FixGuard's own checkers.

**Day 22 — Sep 24:** submit early in the day, then post the Discord close.

**Critical path.** Days 15–17 are the only ones that can't slip — nothing else matters if the four products aren't live. Days 18–19 are compressible if needed. Day 20 is not: the video is a graded deliverable and an unrehearsed take shows.

**Dependencies to watch.** Day 16 needs Day 15's API key and URL. Day 17 needs Day 16's dashboard URL for the buttons. Day 20 needs Days 15–17 live, because recording against localhost undercuts the whole submission.

**Where it actually stands (9 Sep).** The build is roughly ten days ahead of
this plan: everything through Day 17 is live. The remaining critical path is
Days 18 and 20 — audit five real sites, and record the video. Neither is
compressible, and the video is a graded deliverable that shows an unrehearsed
take.

The other thing to do now rather than later is capture evidence. Several items
in the submission package are hPanel conversations and panels that scroll
away; reconstructing them on Day 21 is not possible.