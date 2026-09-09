# Submission package

Draft answers for the seven fields the challenge asks for, plus the evidence
that has to be captured while it still exists.

Deadline **24 September 2026**. Everything below is accurate as of 9 September
and should be re-checked before submitting — figures and claims change as the
build does.

---

## 1. Live Project URL

**https://fixguardai.online**

| | |
|---|---|
| Marketing site | https://fixguardai.online — built with AI Builder, served from Web Hosting |
| The product | https://app.fixguardai.online — running on the VPS |
| A finished report, no account needed | https://app.fixguardai.online/r/IHKZMhbyD8dFIZvk4ZIOT7JTAUWZ7z0R |

Give the judge that third link somewhere obvious. It is the only way they see
real output without signing up, and a reviewer who hits a login wall and
leaves has reviewed nothing.

---

## 2. Business Description

FixGuard AI is pre-flight QA for websites built with AI.

An AI site builder produces something that looks finished in minutes. Looking
finished and working are different things, and the gap between them is
invisible from the page itself: a contact form can show a green success
message and send no request at all, an internal link can lead to a page that
returns 200 with nothing on it, a script can throw on load and take a button
with it. The person who built the site cannot see any of this, because the
page tells them it is fine.

FixGuard opens the site in a real Chromium browser, does what a visitor would
do — fills the forms in with clearly-labelled test data and presses submit,
follows every internal link, waits for the page to settle — and reports what
actually happened at the network level rather than what the interface claimed.
It produces a health score out of 100 with every point traced to a specific
request or element, a PDF certificate, and a share link a developer or client
can open without an account.

It installs nothing on the audited site. No snippet, no tag, no agent — just
an address.

---

## 3. Target Audience & Business Model

### Who it is for

**People who built a site with an AI builder and are about to send it to
customers.** They have no QA process, no staging environment, and no way to
tell a working form from a decorative one. This is the primary audience and
the one the product is shaped around.

**Freelancers and small agencies shipping AI-built sites to clients.** They
need something to hand over at the end of a job that says the thing works, and
something to point at when a client reports a problem three weeks later. The
PDF certificate and the share link exist for that handover.

**Whoever signed off on a build.** A non-technical owner who was told the site
is done and wants a second opinion in language they can read. The report has a
client mode that carries no technical payload at all.

### Business model

Freemium, with the free tier doing real work rather than being a teaser.

| Plan | Price | What it is for |
|---|---|---|
| Free | $0 | One audit. Full score, full evidence, no card. |
| Pro | $19/month | The site you actually ship: unlimited audits, PDF certificates, share links, before-and-after comparison. |
| Team | $49/month | Agencies running QA across client sites. |

**State honestly what is shipped.** Today the free tier and everything in Pro
except scheduled re-checks are built and running. Payments are not connected,
and the Team features — seats, white-label PDF, priority queue — are described
on the pricing page but not implemented. Say so in the submission rather than
letting a judge find it. A working free tier with a stated roadmap reads far
better than a pricing table that turns out to be fiction.

The reason the model works at all is cost shape: an audit is roughly thirty
seconds of one CPU on a machine that is already paid for monthly. There is no
per-request AI spend, because the scoring, scoping and detection engines are
deterministic rather than model-backed.

---

## 4. Short Project Pitch

> You built your site with AI in an afternoon. It looks finished. But does the
> contact form actually send anything?
>
> FixGuard AI opens your site in a real browser, fills your forms in, presses
> submit, and watches the network. It reports the three failures a green
> success message hides: a form that sends nothing, a form that sends
> something the server rejects, and a form that works but reaches nobody. It
> follows every link, catches redirect loops and soft 404s, and checks DNS,
> certificates, accessibility and mobile layout while it is there.
>
> You get a score out of 100 with every point traced to evidence, a PDF
> certificate for the client, and a share link for the developer. Nothing is
> installed on your site. It takes one URL and about thirty seconds.
>
> Find out before your customers do.

---

## 5. How all four Hostinger products were used

Be precise here. The challenge asks for a startup built **using** four
products, not for an application that calls four APIs at runtime — and one of
the four has no API to call.

### VPS — runs the product

The entire application: FastAPI, Playwright with a real Chromium, SQLite, and
the built React dashboard, as one Docker Compose stack behind Coolify's
Traefik with Let's Encrypt. `app.fixguardai.online` is this machine.

The VPS is not incidental — it is the only one of the four that can run this
product at all. Driving a real browser needs a real machine: shared hosting
cannot launch Chromium, and the whole premise depends on loading the site the
way a visitor does rather than fetching HTML.

Specifics worth naming: concurrency is capped at one browser by an asyncio
semaphore because that is what the box can honestly serve; `/dev/shm` is
raised to 1 GB because Docker's 64 MB default makes Chromium die partway
through a page load; nginx resolves the real client address from Traefik so
per-IP rate limiting works.

### Web Hosting — serves the marketing site

`fixguardai.online` is served from Web Hosting. The domain is connected here,
and it is the front door: the product sits on a subdomain pointed at the VPS.
Splitting them this way means the marketing site stays up and fast whether or
not the audit engine is busy driving a browser.

### AI Builder — built the marketing site

The whole of `fixguardai.online` — home, how it works, pricing, FAQ, limits —
was generated with AI Builder (Horizons) rather than hand-written. The prompts
are in the repository at `fixguard/deploy/AI-BUILDER-BRIEF.md`, including the
design-system pass and the iterations that came out of auditing the generated
page with FixGuard itself.

That last part is the interesting bit and worth leading with: **the marketing
site was audited by the product it is marketing.** Real findings came back —
a contrast failure, a tap target four pixels short, a badge blocked by CORS —
and each was fixed by pasting a scoped prompt back into AI Builder. The
before-and-after is in the audit history.

### AI Agents — used throughout the build

The Hostinger Agent lives in hPanel and has no public API, which is worth
stating plainly rather than implying an integration that does not exist. It
was used as it is meant to be used: DNS and domain questions while connecting
`fixguardai.online`, hosting configuration, and copy and SEO review for the
marketing pages.

**Do not claim FixGuard calls a Hostinger AI API at runtime.** It does not,
there is no endpoint, and a technical judge will check.

---

## 6. Product Usage Evidence

Capture these now rather than on the last day — several are conversations and
panels that scroll away.

**AI Agents**
- [ ] hPanel Agent conversations: the DNS/domain one, the hosting one, the
      copy/SEO one. Full window, so the Agent panel is identifiable.

**AI Builder**
- [ ] The Horizons project, showing FixGuard AI as the site
- [ ] Prompt history, next to `fixguard/deploy/AI-BUILDER-BRIEF.md` in the repo
- [ ] Before/after of one page that a FixGuard finding changed

**Web Hosting**
- [ ] hPanel → Websites, showing `fixguardai.online`
- [ ] The domain connected, with its SSL active
- [ ] The live site

**VPS**
- [ ] hPanel → VPS, showing the machine
- [ ] Coolify with the FixGuard stack running, both services healthy
- [ ] `https://app.fixguardai.online` signed in, mid-audit, with the live
      progress stream
- [ ] The admin console at `/admin` — availability, latency, audit volume.
      This is the screenshot that shows the thing is operated, not just built.

**The product working**
- [ ] A finished report with real findings
- [ ] The PDF certificate (`fixguard/docs/sample-certificate.pdf`)
- [ ] The share link open in a private window, proving no account is needed
- [ ] The badge on the marketing site footer, live

---

## 7. Your 21-Day Journey

Days 1–14 came from the plan in `Development_log.md`; days 15 onward are the
commit history in this repository, which is the honest record.

**Days 1–7 · the engine.** FastAPI and SQLite scaffold with the error envelope
from the spec. Playwright driving a real Chromium, capturing console output
and detecting navigation loops. A form parser that generates type-aware test
payloads and refuses to submit anything carrying a password, card, CVV, IBAN
or national identity field. The verdict matrix that separates a form that
sends nothing from one that sends something rejected. Health scoring with
grade bands. The React dashboard with progress streamed over SSE. Share links
with a public report in client and developer modes.

**Days 8–14 · detectors and the prompt engine.** Route crawling with soft-404
detection and a mutation observer for infinite re-renders. Reachability: DNS,
TLS expiry, redirect chains. The Surgical Prompt Studio — turning a finding
into a scoped prompt that names one element, with guardrails that refuse to
guess. PDF certificates and the verification badge. Accessibility, mobile
viewport and Core Web Vitals. Multi-page scans and before/after comparison.

**Deployment and hardening.** The repository, the Coolify single-stack
deployment, and the domain live. Then the part that was not planned and
mattered most: putting the dashboard behind real accounts and scoping every
audit to its owner, which turned a demo into something that could hold a
stranger's data.

Then a run of things that were only found by running it in public:

- Two API routes that returned 500 on every call, left behind by a rename.
  Both parsed and imported cleanly, so nothing caught them until a real
  request arrived — including the documented one-click retry. Fixed, and a
  scope checker added that resolves names the way Python does, so the same
  class of bug fails a test instead of a user.
- Coolify publishing the API on its own hostname, bypassing nginx and with it
  the rate limiting and real-IP resolution.
- The marketing site's own verification badge, blocked by CORS in every
  visitor's browser — found by auditing the marketing site with the product.
- Three false positives in FixGuard's own checkers, each found by pointing it
  at our own pages: contrast measured mid-fade, a white background assumed
  behind white text, and a keyboard skip link reported as an unhittable tap
  target. A QA tool that cries wolf is worse than none, so each was fixed and
  pinned with a test.
- Security headers that nginx was silently dropping from the HTML document and
  the JavaScript bundle, because `add_header` does not inherit into a location
  that sets one of its own. The two responses where they mattered most had
  none.

**Where it stands.** An admin console with persisted request metrics,
availability and latency, and audits closed automatically when a deploy
interrupts them. A privacy policy and terms written from the code rather than
a template. 36 unit tests and an acceptance suite, green.

**What is honestly still missing.** Payments are not connected. Scheduled
re-checks, team seats and white-label PDFs are on the pricing page and not
built. Reachability is measured from one region, not three, because the grant
is one machine. And FixGuard confirms a form submission is accepted by the
receiving server — it cannot verify delivery to a mailbox, because the audited
site's mail never passes through it. That limit is stated in the product, on
the marketing site, and in every report.

---

## Before submitting

- [ ] The pricing page and home page still claim an audit needs no account.
      They do need one. Fix the copy or the claim is falsified by the first
      click a judge makes.
- [ ] Mark unbuilt plan features as planned on the pricing page.
- [ ] Link the privacy policy and terms from the marketing footer.
- [ ] Make `privacy@fixguardai.online` deliverable.
- [ ] Audit five real sites and keep the reports.
- [ ] Record the two-minute video.
- [ ] Re-read every figure in this document against what is live that day.
