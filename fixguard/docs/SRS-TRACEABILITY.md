# SRS Traceability Matrix

Every requirement in `FixGuard-AI-SRS.md` mapped to its implementation status
as of **6 September 2026** (Day 4 of 21).

| | Meaning |
|---|---|
| **Done** | Implemented and verified against the testbed |
| **Partial** | Implemented with a documented limitation |
| **Cut** | Will not be built; reason given |

All four modules are now implemented. The remaining gaps are listed honestly
below rather than glossed over.

---

## 4.1 Module 1 — Surgical Prompt Studio

| Req | Title | Status | Notes |
|---|---|---|---|
| FR-1.1 | Intent input & code context capture | **Done** | Three context modes: live `page_url`, pasted `code_context`, or `target_selector` alone. Intent capped at 500 characters. |
| FR-1.2 | AST/DOM scoping engine | **Done** | Playwright extracts up to 140 candidate elements with computed styles, global `:root` tokens, parent layout, and a count of how many elements share each class. Pasted HTML is parsed without a browser via `html.parser`. |
| FR-1.3 | Guardrail prompt generation | **Done** | Prompts scope to one selector and one property, then enumerate what must not change: parent layout, global tokens, site font, and shared classes. Output is typically 150–200 tokens, well inside the 300 the spec asks for. |
| FR-1.4 | Differential code preview | **Done** | Before/after diff of the single changed declaration, plus a count of frozen style groups. |
| FR-1.6 | Audit findings to fix prompts | **Added** | Not in the SRS. `POST /api/v1/prompts/from-audit` turns each finding into a guarded remediation prompt, joining Module 3 to Module 1. |
| FR-1.5 | Prompt history & credit estimator | **Done** | Every prompt persisted to `surgical_prompts` with a `tokens_saved_estimate`; the history page shows a cumulative total. |

### The engine runs without any LLM

This is the important design decision. **Hostinger AI Builder's integrated AI
is not callable from a backend** — it is an assistant inside the builder UI,
with no endpoint or key. So Module 1 was built deterministic-first:

- Property detection: 18 ordered phrase patterns → CSS property.
- Value extraction: 27 named colours, hex, `rgb()`, lengths with units, and
  relative sizes resolved against the element's real computed value.
- Element resolution: candidates scored on quoted text, element type,
  descriptive words matched against text, id, class, `name`, `placeholder`
  and associated `<label>`.

Verified on the testbed at **10 of 10 intent types** with no API key:

| Intent | Resolved |
|---|---|
| "Make the Send message button background red" | `#contact > button` · `background-color` = `#e02424` |
| "Make the main title bigger" | `h1` · `font-size` = `40px` (1.25× its real 32px) |
| "Change the heading to uppercase" | `h1` · `text-transform` = `uppercase` |
| "Round the send message button corners to 12px" | `#contact > button` · `border-radius` = `12px` |
| "Hide the phone field" | `#phone` · `display` = `none` |
| "Make the email field border red" | `#email` · `border` = `#e02424` |
| "Center the main title" | `h1` · `text-align` = `center` |
| "Make the paragraph font size 18px" | `.sub` · `font-size` = `18px` |
| "Set the form font family to 'Georgia'" | `#contact` · `font-family` = `Georgia` |
| "Make the send message button bold" | `#contact > button` · `font-weight` = `700` |

Setting `LLM_PROVIDER` and `LLM_API_KEY` adds Agent 2 on top. It may only
choose from selectors that actually exist on the page; a hallucinated selector
is rejected and the deterministic match is kept.

---

## 4.2 Module 2 — Synthetic Form & SMTP Testing

| Req | Title | Status | Notes |
|---|---|---|---|
| FR-2.1 | Target URL & form selector input | **Partial** | `form_selector` is accepted but not yet used to narrow selection; all visible forms are tested up to a cap of 3. |
| FR-2.2 | Autonomous DOM field parser | **Done** | text, email, textarea, select, radio, checkbox, tel, date, datetime-local, time, url, number. Captures `action`, `method`, and locates the submit control. |
| FR-2.3 | Headless form submission | **Done** | Fills, submits, intercepts every outbound request, captures JS errors and HTTP status. |
| FR-2.4 | Temporary SMTP inbox | **Cut** | See below. |
| FR-2.5 | Email header verification | **Cut** | Same reason. |
| FR-2.6 | Silent failure detection | **Partial** | Both frontend criteria fully implemented and verified. The "no email within 30s" criterion is not implementable. |

### Why SMTP capture was cut

A contact form on an AI Builder site sends mail from Hostinger's
infrastructure to the **site owner's** inbox. That traffic never touches
FixGuard, so a MailHog container here can never see it. Capturing it would
require the owner to repoint their form's recipient address before an audit
and change it back afterwards — worse than the problem it solves.

**What is claimed instead:** a submission left the browser and the receiving
server accepted it. Verifiable, valuable, honest. This wording appears in the
UI, the shared report and the PDF footer.

---

## 4.3 Module 3 — Router & Health Auditor

| Req | Title | Status | Notes |
|---|---|---|---|
| FR-3.1 | Client-side router inspection | **Done** | Route changes recorded, throttling warning matched, ≥5 navigations to one URL in 3s flagged, up to 5 same-origin links crawled, broken routes reported including soft 404s. |
| FR-3.2 | Infinite re-render detection | **Done** | MutationObserver on a 2s rolling window against a threshold of 50. Counters zero after first paint so building the DOM is not mistaken for churn. Verified: 1573 mutations on the re-render page, 0 on normal ones. |
| FR-3.3 | Console error & asset audit | **Done** | Source and line captured; categorised critical / warning / info with CORS mapped to info and deprecations to warning. |
| FR-3.4 | Multi-region geo-ping | **Partial** | Implemented for one region. See below. |

### Reachability: what one host can honestly measure

Three-region comparison needs three hosts and the grant is one VPS. Rather
than cut the category entirely or fake it, the module measures what a single
host genuinely can:

- DNS resolution and the addresses returned
- TLS certificate validity, issuer, and days to expiry
- the full redirect chain, and whether it terminates
- HTTP status and latency
- 403/451 block responses

Results are stored one row per region in `geo_ping_results`, so adding proxies
later needs no schema change. Every surface states `regions_measured: 1` of
`regions_requested: 3`, so coverage is never overstated.

**Not implemented:** identifying the specific React component causing a loop.
That needs a source-map walk or the DevTools hook, neither reliable on a
minified production build. FixGuard reports the looping URL and mutation count.

---

## 4.4 Module 4 — Client Handoff Report

| Req | Title | Status | Notes |
|---|---|---|---|
| FR-4.1 | Site health score | **Done** | Spec weights used exactly: Form 30, Router 30, Geo 20, Asset 20. Spec grade bands. One addition: any critical finding caps the composite at 49 so a site that silently drops enquiries cannot show a passing grade. A module the user deselects is excluded and remaining weights renormalised, rather than scored as a silent 100. |
| FR-4.2 | PDF audit certificate | **Done** | Branded A4 certificate: score dial, executive summary, weighted breakdown bars, full checks table, honest-limits footnote. Rendered with Playwright's `page.pdf()` rather than a second Puppeteer container, since Chromium is already running. |
| FR-4.3 | Shareable web audit view | **Done** | Token-based, no auth, 30-day expiry, client/developer toggle. Filtering is server-side, so the client view never ships technical payloads to the browser. |
| FR-4.4 | Verification badge widget | **Done** | One `<script src>` tag. Fetches the current score on load, so re-running an audit updates every embedded badge. Also available as `.svg` and `.json`. |

---

## 4.5 Cross-Module

| Req | Title | Status | Notes |
|---|---|---|---|
| FR-X.1 | Audit run orchestration | **Partial** | Module selection, SSE progress with percent, and `module_complete` events all work. Queueing is an `asyncio.Semaphore`, not Redis — a 1 vCPU box cannot run three Chromium instances anyway. |
| FR-X.2 | AI Agent integration | **Done** | All three agents implemented, each deterministic-first. Every call logged to `agent_calls` with input, output and latency. `GET /api/v1/agents/status` reports which mode each is in. |

### The three agents

| Agent | Deterministic engine | With a model |
|---|---|---|
| 1 · Log Parser | 12 error-pattern rules covering null property reads, undefined values, 404/5xx resources, CORS, throttling, stack overflow, syntax errors, mixed content, hydration mismatch, deprecations | Only the errors the rules did not recognise are sent |
| 2 · Prompt Generator | The full scoping engine above | Re-picks the element, but only from selectors that exist |
| 3 · Summary | Template built from the findings and score | Rewrites it more naturally |

---

## 5. Non-Functional Requirements

| Req | Target | Status | Measured |
|---|---|---|---|
| 5.1 | Single-module audit < 30s | **Done** | 8.2s router-only |
| 5.1 | Full audit < 60s | **Done** | 14.5s typical, 20.9s worst |
| 5.1 | Prompt generation < 5s | **Done** | ~3s including page load |
| 5.1 | API response < 200ms | **Done** | Single SQLite reads |
| 5.1 | PDF < 10s | **Done** | ~2s |
| 5.1 | 3 parallel Playwright sessions | **Cut** | 1 vCPU. Capped at 1 via `MAX_CONCURRENT_AUDITS` |
| 5.2 | Horizontal worker scaling | **Cut** | Requires the Redis architecture |
| 5.3 | Graceful timeouts | **Done** | 90s ceiling, per-page and per-route limits |
| 5.3 | One-click retry | **Done** | `POST /audits/{id}/retry` plus a button |
| 5.3 | Report unreachable, do not crash | **Done** | `UNREACHABLE_TARGET` |
| 5.3 | Container auto-restart | **Done** | `restart: unless-stopped` |
| 5.4 | HTTPS/TLS | **Done** | NGINX config provided; certificate step manual |
| 5.4 | API key auth | **Done** | Constant-time comparison |
| 5.4 | Unguessable share tokens | **Done** | `secrets.token_urlsafe(24)` |
| 5.4 | Rate limit 10/hour/key | **Done** | Verified: 11th start returns `RATE_LIMIT_EXCEEDED` |
| 5.4 | No credential storage | **Done** | Plus: forms with password or payment fields are never submitted |
| 5.5 | Responsive dashboard | **Done** | |
| 5.5 | Progress indicators | **Done** | Percent bar, per-module chips, step log |
| 5.5 | Human-readable errors | **Done** | Agent 1 explains every console error |
| 5.6 | Modular structure, env config, `/api/v1` | **Done** | |
| 5.7 | Chromium engine | **Done** | |

---

## 7. Data Model

| SRS table | Status | Notes |
|---|---|---|
| `users` | **Done** | Built after the fact. SRS 3.2 puts authentication out of scope, and that was right until the history endpoint was found returning every audit anybody had run to whoever asked. Accounts exist so audits can be owned; the SRS should be read as superseded here. |
| `projects` | **Cut** | No grouping above the account yet. `project_id` is still accepted by the API and ignored, which is worse than rejecting it - see the open gaps below. |
| `audit_runs` | **Done** | Plus progress, modules, retry, reachability, summary, parsed errors |
| `surgical_prompts` | **Done** | Real table |
| `geo_ping_results` | **Done** | Real table, one row per region |
| `agent_calls` | **Added** | Not in the SRS; required by FR-X.2's logging clause |
| `share_links` | **Done** | Real table with expiry |
| `form_test_results` | **Merged** | JSON column `form_results` |
| `router_audit_results` | **Merged** | JSON column `router_result` |
| `console_error_logs` | **Merged** | JSON columns `console_errors` + `parsed_errors` |
| `health_scores` | **Merged** | JSON column `score_breakdown`, using the spec's field names |

**Why four are merged:** these rows are written once and always read with
their parent audit. Splitting them costs four joins on every report read and
buys nothing, because nothing queries them independently. They can be
normalised later without changing the API surface.

---

## 8. API Specification

| Endpoint | Status |
|---|---|
| `POST /api/v1/audits/start` | **Done** |
| `GET /api/v1/audits/:id/status` | **Done** |
| `GET /api/v1/audits/:id/stream` | **Done** |
| `GET /api/v1/audits/:id/report` | **Done** |
| `POST /api/v1/prompts/surgify` | **Done** |
| `POST /api/v1/prompts/from-audit` | **Added** |
| `GET /api/v1/prompts/history` | **Done** |
| `GET /api/v1/reports/:id/pdf` | **Done** |
| `GET /api/v1/public/reports/:token` | **Done** |
| `POST /api/v1/audits/:id/share` | **Done** |
| `GET /api/v1/health` | **Done** |
| `POST /api/v1/audits/:id/retry` | **Added** (NFR 5.3) |
| `GET /api/v1/reports/:id/badge` | **Added** (FR-4.4) |
| `GET /api/v1/public/badge/:token.{js,svg,json}` | **Added** (FR-4.4) |
| `GET /api/v1/agents/status` | **Added** (FR-X.2) |
| `POST /api/v1/forms/synthetic-test` | **Merged** into the audit's `form` module |

Error envelope per 8.3, with every spec code implemented plus
`CONSENT_REQUIRED`, `VALIDATION_ERROR`, `AUDIT_NOT_COMPLETE`,
`REPORT_NOT_FOUND`, `REPORT_EXPIRED`.

---

## 9. Four-Product Integration

| Product | SRS role | Status |
|---|---|---|
| AI Builder | Marketing site, lead capture, intake | **Not started.** Zero websites exist on the account; verified via the Hostinger API. |
| Web Hosting | Dashboard SPA, report pages | **Landing page instead.** `deploy/landing/index.html` is a standalone static page whose intake form hands a URL to the dashboard. The dashboard and reports stay on the VPS — see the divergence note. |
| VPS | Playwright, API, database | **Live** at https://fixguardai.online — engine, database, dashboard and TLS |
| AI Agents | Log parsing, prompt generation, summaries | **Built** — deterministic engines, optional model |

**Be precise about the removal test in a pitch.** Three products carry load
once the AI Builder page exists: the VPS runs everything, the agents produce
the explanations and prompts, and AI Builder is the front door that hands a
URL to the dashboard. Web Hosting carries the public landing page and the intake form that starts
the journey - static, so it stays up even while the engine is redeploying.

The challenge asks entrants to *build using* the four products; the stricter
runtime-interdependence framing is SRS 9.2's own, written before the split was
weighed. Hostinger Agent was used throughout for provisioning, VPS diagnostics
and deployment debugging, which is what "build using" asks for.

Older note, kept because the reasoning still holds: The intelligence layer exists and runs, but on FixGuard's
own engines rather than a Hostinger inference endpoint, because none is
exposed to backends. Say that plainly; a technical judge will respect it more
than an overclaim.

---

## Additions not requested by the SRS

| Addition | Why |
|---|---|
| Consent gate (`i_own_this_site`) | The audit submits forms on a live site |
| Sensitive-field refusal | Password, card, CVV, IBAN, SSN and API-key fields are detected and never submitted |
| Self-identifying test payloads | Every value carries "FixGuard AI automated site test - please ignore" |
| Critical-finding score ceiling | Weighted averaging rated the redirect-loop page 84; a site nobody can load must not score a B |
| Soft-404 detection | Client-side routers return 200 for missing paths |
| Shared-class blast-radius warning | Editing `.btn` when 12 elements use it is exactly how AI Builder users lose their styling |
| Alternative-element suggestions | When the match is ambiguous, the next three candidates are offered |
| Testbed | Four pages with known failure modes, including a working control |
| Agent call telemetry | FR-X.2 requires logging; the table did not exist in the schema |
| Broad-request refusal | "Redesign the whole page" is a project, not a property change. Emitting a confident prompt for a guessed element is worse than saying so, and unscoped prompts are exactly what burns credits |
| Partial audits | UC4 requires partial results over total failure. A 403 still yields DNS/TLS findings; only a genuinely dead host fails |
| Acceptance suite | `backend/tests/test_acceptance.py` runs SRS 11.2 T-01..T-12 against a live API |
| Before/after comparison | A score alone never proves the tool helped. `GET /audits/{id}/compare` diffs two runs of the same site into resolved / introduced / remaining |
| Accessibility checks | Alt text, form labels, WCAG AA contrast, heading order, duplicate ids, page language |
| Mobile layout checks | Horizontal overflow, tap targets, small text, blocked pinch-zoom, at a 390px viewport |
| Core Web Vitals | LCP, FCP, CLS and TBT against Google's published thresholds |
| Multi-page scans | Follows internal links and scores each page, with one shared form budget so a large site cannot trigger dozens of real submissions |
| Site architecture map | The `/architecture` page maps the *audited* site: composition, detected libraries, every third-party host grouped by purpose, forms and where they send, content outline, link map |
| Authenticated auditing | Session handoff rather than credentials. Verifies the session before trusting results, refuses sign-out and destructive links, keeps form submission opt-in, and stores cookie names but never values |


---

## Open gaps as of 6 September

Listed because a traceability matrix that only records what was finished is a
marketing document.

| Gap | Where it bites |
|---|---|
| **AI Builder holds no website** | SRS 9.1 gives it marketing and intake. The brief and the `?url=` handoff are ready; the page is not built |
| **No pitch video** | SRS 3.3 success criterion |
| `form_selector` accepted and ignored | FR-2.1. A parameter that changes nothing is worse than one that is rejected |
| `project_id` accepted and ignored | Same shape, and `projects` was never built |
| No delete anywhere | SRS 10.2 says audits are retained "user can delete"; 10.4 promises deletion on request. No endpoint exists |
| One shared API key | SRS 10.1 asks for per-user keys, stored hashed, rotatable from the dashboard. Now that accounts exist this is buildable and was not before |
| Geo-ping measures one region | FR-3.4 asks for three. Documented at every surface rather than faked |
| No load testing | SRS 11.1 lists locust. Unit and end-to-end suites exist; load does not |

## Where the implementation deliberately diverges from the SRS

| SRS says | What was built | Why |
|---|---|---|
| 3.2: authentication out of scope | Accounts, sessions, per-user ownership | The alternative was one visitor seeing another's list of audited sites |
| 10.4: "public-facing pages only — no authenticated/login-gated site testing" | Session-handoff auditing behind a login | Requested, and built without ever handling a password. The SRS sentence predates the feature |
| 11.3: `/architecture` shows the 4-product diagram | It shows the *audited* site, with the 4-product diagram on a second tab | Mapping the audited site turned out to be one of the most useful outputs. The SRS item is met by the tab |
| 9.1: Web Hosting serves the dashboard and report pages | It serves the public landing page; the dashboard and reports stay on the VPS | Splitting the *dashboard* across two machines needed a shared-domain cookie, a second certificate and CORS, and bought nothing. Splitting the *landing page* costs none of that - it is static and calls no API - and gains something real: the public face stays up while the engine is redeployed |
