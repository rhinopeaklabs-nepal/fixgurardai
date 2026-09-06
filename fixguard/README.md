# FixGuard AI

[![acceptance](https://github.com/rhinopeaklabs-nepal/fixgurardai/actions/workflows/acceptance.yml/badge.svg)](https://github.com/rhinopeaklabs-nepal/fixgurardai/actions/workflows/acceptance.yml)

**Live: https://fixguardai.online**

Pre-flight QA and prompt scoping for Hostinger AI Builder sites.

Two things it does:

1. **Finds what is broken** — drives a real Chromium browser, submits your
   forms, follows your routes, and reports what actually happens rather than
   what the page claims.
2. **Stops AI Builder wandering** — turns "make the booking button blue" into
   a prompt scoped so tightly the builder cannot rewrite the rest of your site.

## Running the checks

The acceptance suite drives a real browser against a local testbed of
deliberately broken pages, because mocking Playwright would only prove the
mock works. It starts both servers itself:

```bash
cd fixguard/backend
python -m tests.run_acceptance
```

Eleven of the twelve SRS scenarios pass. T-04 is reported as *not
applicable* rather than failing: it asks FixGuard to verify a header on
mail the host sends directly to the site owner, which never reaches
FixGuard at all. Deployment is covered in
[`deploy/DEPLOYMENT.md`](deploy/DEPLOYMENT.md).

Requirement-by-requirement status against the SRS, including what is
deliberately cut and why, is in [`docs/SRS-TRACEABILITY.md`](docs/SRS-TRACEABILITY.md).

---

## The four modules

### 1 · Surgical Prompt Studio

You describe the change. FixGuard reads the live page, finds the element,
identifies the one property to change, and writes a prompt that names
everything AI Builder must not touch.

```
Change ONLY the CSS `background-color` of `#contact > button` to `#e02424`.
That element is the one labelled "Send message".
Its current `background-color` is `rgb(0, 85, 255)`.

DO NOT:
- change any property of `#contact > button` other than `background-color`
- change the parent container `#contact` or its layout (display: block, ...)
- change the site font family (`system-ui, sans-serif`)
- restructure the HTML, rename classes, or reorder elements
- modify any other page, component, or section

Return only the single changed CSS rule. Do not rewrite the file.
```

**Fix an audit's findings.** Feed the Prompt Studio an audit link and it turns
every finding into its own guarded prompt: the observed evidence, the fix, and
a fence around everything AI Builder must leave alone. That closes the loop
between finding a problem and fixing it without asking the builder to "fix my
site", which is the request that burns credits.

**This runs with no LLM API key.** The scoping engine is deterministic:
phrase-matched properties, a colour and length vocabulary, and element scoring
against the real DOM. Verified on 10 of 10 intent types with no key. Setting
`LLM_PROVIDER` and `LLM_API_KEY` adds a model on top that may only pick from
selectors that genuinely exist on the page.

### 2 · Form testing

| Check | What it catches |
|---|---|
| **Silent failure** | Success message shown, no request sent. The visitor thinks they contacted you. |
| **Endpoint error** | Data sent, server returned 4xx/5xx. Submissions dropped. |
| **JS crash** | JavaScript threw during submit. |
| **No confirmation** | Works, but the visitor sees nothing, so they submit twice. |

### 3 · Navigation, console, reachability, accessibility, speed and mobile

| Check | What it catches |
|---|---|
| **Redirect loop** | Repeated navigation to one URL — the React Router / `useEffect` loop. |
| **Infinite re-render** | Runaway DOM churn from an unguarded `useEffect`. Logs no error. |
| **Broken routes** | Internal links returning 4xx, including soft 404s behind an HTTP 200. |
| **Console errors** | With source, line, severity, and a plain-English explanation. |
| **Broken assets** | Images, CSS, fonts, scripts returning 4xx/5xx. |
| **DNS & TLS** | Resolution, certificate validity and expiry, redirect chain, block responses. |
| **Mobile layout** | Sideways scrolling, tap targets under 44px, text under 12px, blocked pinch-zoom. |
| **Accessibility** | Missing alt text and form labels, contrast below WCAG AA, heading order, duplicate ids, missing page language. |
| **Speed** | LCP, FCP, CLS and total blocking time against Google's Core Web Vitals thresholds. |

Any audit can follow internal links and score several pages in one run.

### 4 · Client handoff

0–100 health score on the SRS weights, a branded PDF certificate, a
token-based public report with client and developer modes, and an embeddable
verification badge that updates itself when you re-audit.

---

## Auditing behind a login

Most of what matters on a real site is signed in. FixGuard audits it without
ever handling a password: you sign in yourself and paste the resulting `Cookie`
header, which you can revoke at any time by logging out.

Being signed in also changes what crawling means, so an authenticated audit is
deliberately more careful than an anonymous one:

- **The session is verified first.** An expired cookie does not error - the site
  just returns the login page. Without a check, FixGuard would score *that* and
  report the site healthy. Give it a phrase that only appears when signed in.
- **Sign-out links are never followed.** One `/logout` turns the rest of the
  audit into a tour of the login screen.
- **Links that look destructive are refused** - `/delete`, `/cancel`,
  `/revoke`, `?action=remove` and similar. Plenty of applications still expose
  these as plain GET links.
- **Forms are not submitted by default.** Behind a login, a form is as likely to
  change a setting or close an account as it is to send a message. Opt in
  per audit.
- **Nothing secret is stored.** The audit record keeps the cookie *names* and
  nothing else. Values are used for the run and never written down.

## Safety rules built in

- The API refuses to start an audit unless the caller sets `i_own_this_site`.
- Any form containing a password, card, CVV, IBAN, SSN or API-key field is
  detected and **never submitted** — it is reported as deliberately skipped.
- All synthetic values carry the marker
  `FixGuard AI automated site test - please ignore`.
- Private and loopback addresses are rejected unless `ALLOW_PRIVATE_TARGETS=1`.

## Honest limits

- **Form checks confirm a submission leaves the browser and is accepted by the
  receiving server. They do not confirm the email reached your inbox**, because
  your site's mail never routes through FixGuard. Do not claim inbox delivery.
- **Reachability is measured from one host.** Cross-region geo-blocking needs
  probes in separate regions. Every surface reports `regions_measured: 1 of 3`.

---

## Run it locally

Three terminals.

**1. Testbed** — a deliberately broken site to audit:

```bash
python fixguard/testbed/server.py
```

**2. API:**

```bash
cd fixguard/backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
./.venv/Scripts/python.exe -m playwright install chromium
ALLOW_PRIVATE_TARGETS=1 ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

On Linux/macOS use `.venv/bin/python`.

**3. Dashboard:**

```bash
cd fixguard/dashboard
npm install
npm run dev
```

Open http://localhost:5173 and audit `http://127.0.0.1:8080/`.

### Testbed expectations

| URL | Expected |
|---|---|
| `/` | 49 / critical — silent failure, console errors, broken image, broken route |
| `/good.html` | 81 / minor_issues — form passes; the page links to a broken route |
| `/rerender.html` | 49 / critical — infinite re-render, score capped |
| `/loop.html` | 49 / critical — redirect loop, score capped |

The `good.html` control matters: a detector that flags everything is useless.
Its form must come back `pass`.

---

## Optional: add a model

Nothing requires one. It improves intent parsing on unusual phrasing.

```bash
# Anthropic
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-haiku-4-5-20251001

# or anything speaking the OpenAI chat-completions shape
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

`GET /api/v1/agents/status` reports which mode each agent is in.

> **Note:** AI Builder's integrated AI cannot be used here. It is an assistant
> inside the builder UI with no callable endpoint. AI Builder still does the
> real work — it applies the surgical prompt on your credits.

---

## Deploy to the VPS

```bash
cp .env.example .env      # then edit it
docker compose up -d --build
```

Build the dashboard and upload `dashboard/dist/` to Web Hosting:

```bash
cd dashboard
cp .env.example .env      # point VITE_API_BASE_URL at the VPS
npm run build
```

The dashboard is a single-page app, so Web Hosting needs a rewrite sending
unknown paths to `index.html`, otherwise `/r/<token>` links 404 on refresh.

---

## API

`X-API-Key` on everything except the public report, badge, and progress stream.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/audits/start` | Start an audit (`domain_url`, `modules`, `i_own_this_site`) |
| POST | `/api/v1/audits/{id}/retry` | Re-run a failed audit |
| GET | `/api/v1/audits` | Recent audits |
| GET | `/api/v1/audits/{id}/status` | Status, percent, modules complete/pending |
| GET | `/api/v1/audits/{id}/report` | Full report |
| GET | `/api/v1/audits/{id}/stream` | SSE progress |
| POST | `/api/v1/prompts/surgify` | Generate a surgical prompt |
| GET | `/api/v1/audits/{id}/compare` | Diff against the previous audit of the same site |
| POST | `/api/v1/prompts/from-audit` | Turn an audit's findings into fix prompts |
| GET | `/api/v1/prompts/history` | Prompt history and cumulative savings |
| GET | `/api/v1/agents/status` | Agent modes and call telemetry |
| GET | `/api/v1/reports/{id}/pdf` | PDF certificate |
| GET | `/api/v1/reports/{id}/badge` | Badge embed snippet |
| POST | `/api/v1/audits/{id}/share` | Create/return a share link |
| GET | `/api/v1/public/reports/{token}` | Public report (`?mode=client\|developer`) |
| GET | `/api/v1/public/badge/{token}.{js,svg,json}` | Public badge |
| GET | `/api/v1/health` | Health check |

Audit starts are rate limited to 10 per key per hour. Errors use the SRS
envelope: `{"error": {"code", "message", "audit_id", "retryable"}}`.

The progress stream is unauthenticated by design: browsers cannot attach
headers to `EventSource`, so the unguessable audit UUID is the capability for
that read-only channel.

---

## Architecture

```
Browser ──> NGINX :443 ──> FastAPI :8000 ──> Playwright (Chromium)
                                │                     │
                                ├──> SQLite           └──> target website
                                └──> LLM provider (optional)
```

No Redis, no separate worker container, no Puppeteer. On a 1 vCPU box the
queue is an `asyncio.Semaphore` and the PDF renderer is the browser already
running.

## Layout

```
backend/app/
  audit/probe.py       detectors, route crawl, verdict matrix
  audit/extract_js.py  in-page JS: form parsing, mutation observer, style context
  audit/runner.py      lifecycle, concurrency cap, SSE fan-out
  audit/payloads.py    type-aware test values, sensitive-field refusal
  audit/extract_quality.py  in-page JS: vitals, accessibility, mobile layout
  audit/quality.py     thresholds and scoring for those three
  audit/page_audit.py  per-page checks, reused by the multi-page scan
  compare.py           before/after diffing
  scope.py             Module 1 deterministic engine
  prompt_service.py    Module 1 orchestration
  agents.py            the three agents, each deterministic-first
  llm.py               provider-agnostic client, optional
  reachability.py      DNS, TLS, redirect chain
  scoring.py           weights, critical ceiling, grade bands
  report_render.py     PDF certificate and badge
  errors.py            SRS 8.3 envelope
  ratelimit.py         10 starts per key per hour
  routers/             HTTP surface
dashboard/src/         React SPA
testbed/               deliberately broken site (4 pages)
docs/                  traceability matrix, sample certificate
```
