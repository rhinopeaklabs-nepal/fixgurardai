# AI Builder / Horizons — the marketing site

Everything to paste, in order. The site is already generated once; Step 1 is a
rebuild prompt that replaces what is there with a version matching the
dashboard's design system and pointing at the right URLs.

---

## Before anything: two rules

**Do not build a tool here.** The prompt box invites it. Horizons cannot drive
a browser, submit a form or read a console, so anything built here would be a
weaker copy of the product that already exists — and it would invite the
comparison. This site's job is the front door.

**Change one thing at a time after the first generation.** Every regeneration
spends a credit and risks the layout. Say explicitly what must not change.

---

## Step 1 — the rebuild prompt

Paste this whole block as a single message.

> Rebuild this site as a small marketing site for **FixGuard AI**, a
> pre-flight QA tool for websites. Replace the current pages entirely.
>
> ## Design system — follow exactly
>
> Colours:
> - Primary blue `#0055FF`, hover `#0044CC`
> - Ink / headings `#0D1117`, body text `#4B5563`, muted `#94A3B8`
> - Borders `#E2E8F0`, page wash `#F8FAFC`, cards white
> - Status colours, used only for status: pass `#059669`, warning `#D97706`,
>   critical `#DC2626`
>
> Type:
> - Headings: **Archivo**, weights 600 and 800, tight letter-spacing
> - Body: the system sans stack, generous line height
> - Any status code, URL, selector or log line: a monospace font, on a dark
>   `#0D1117` block with light text
>
> Style rules:
> - No emoji anywhere. No stock photos of people. No gradients on text.
> - Cards: white, 1px `#E2E8F0` border, 16px radius, no heavy shadows
> - Generous whitespace. Large readable type. Left-aligned, not centred,
>   except the final call to action.
> - Tone: direct and technical. Never salesy. Short sentences.
>
> ## Pages
>
> ### 1. Home
>
> **Hero.** Small pill label "Pre-flight QA for AI Builder sites". Headline:
> "Your form says Thanks! It sent nothing." — with "Thanks!" in the pass
> green `#059669`. Sub-headline: "That is the failure nobody reports to you.
> The visitor saw a success message and left. FixGuard opens your site in a
> real browser, fills your forms in, presses submit, and watches the network
> to see whether anything actually left the page."
>
> Under it, a text input labelled "Your website address" with placeholder
> "yourbakery.com" and a primary button "Run a free audit". Below in small
> muted text: "One URL. Around 30 seconds. No snippet to install, nothing to
> add to your site."
>
> To the right of the hero, a mock **audit report card**: a red score dial
> reading 49, the title "yourbakery.com", a red line "Critical · 1 blocking
> issue", then three findings stacked. Each finding has a coloured left bar,
> a small uppercase severity chip, a bold title, one line of explanation, and
> a dark monospace evidence block:
> - critical — "Contact form — submissions are being lost" / "The form showed
>   its success message, but no network request left the page." / evidence:
>   `form#contact  submit  ->  no request made`
> - warning — "2 links lead nowhere" / "Visitors clicking these reach a dead
>   page." / evidence: `GET /pricing   404`
> - info — "24 other companies receive a request" / "Nine are advertising or
>   analytics services."
>
> **Three problems**, as three cards, each with a small blue uppercase kicker,
> a heading, a paragraph and a dark monospace block:
> - FORMS — "The success message that means nothing" — a form can show a
>   confirmation and send no request at all, or send one that comes back 500.
>   FixGuard fills it in with clearly-labelled test data, submits it, and
>   reports which of those three actually happened.
> - ROUTES — "Links that lead nowhere" — every internal link is followed, not
>   just listed. Redirect loops, pages that return 200 while rendering "not
>   found", and routes that quietly 404 are named with the path a visitor
>   would have clicked.
> - THIRD PARTIES — "Everyone your visitors reach" — every host that receives
>   a request when someone opens your page, grouped by what it is for. Not the
>   scripts you added: the ones those scripts loaded too.
>
> **What you walk away with**, four tiles on a dark `#0D1117` band: a score
> you can argue with; a PDF certificate; a shareable client-safe link that
> expires; a before-and-after comparison of two runs.
>
> **Final call to action**, centred: "Find out before your customers do", one
> primary button "Open the dashboard", and small text "Your audits stay
> private to your account."
>
> ### 2. How it works
>
> Four numbered steps, numbers in monospace inside circles:
> 1. Paste your address. One URL. Choose whether to check just that page or
>    let FixGuard find your other routes from your sitemap and your own links.
> 2. It opens the site for real. A real Chromium browser loads the page,
>    watches the console and the network, submits your forms with test data,
>    and follows your links. Nothing is installed on your site.
> 3. You get evidence, not adjectives. A score out of 100, every finding with
>    the request or selector that produced it, and a PDF for whoever fixes it.
> 4. Each finding becomes a prompt. Scoped tightly enough that an AI builder
>    changes one thing instead of rewriting your layout.
>
> Then a compact list headed "What it checks": forms that silently fail,
> redirect loops, infinite re-renders, broken internal links, JavaScript
> errors, broken images, DNS records that disagree with each other, TLS
> certificate expiry, accessibility, mobile layout, Core Web Vitals.
>
> ### 3. What FixGuard will not do
>
> A definition list, plain, no cards. Introduce it with: "A tool that reports
> what actually happened has to be equally plain about what it did not look
> at. These are the limits, in the same words the reports use."
>
> - **It never asks for a password to your site.** To check pages behind a
>   login, you sign in yourself and hand FixGuard the resulting session. A
>   session is scoped, expiring and revocable. A password is none of those.
>   Forms containing a password, card or ID field are never submitted.
> - **It cannot tell you the email arrived.** FixGuard sees whether your
>   form's request left the page and what came back. The mail your host then
>   sends goes to you, not to FixGuard, so nothing here claims to have watched
>   it land in an inbox.
> - **It checks reachability from one region.** DNS, TLS and the response code
>   are measured from where FixGuard runs.
> - **It stores no cookie or token values.** If you hand it a session, the
>   names of the cookies are recorded and the values are not. Sign-out links
>   and anything that looks like it deletes data are never followed.
>
> ### Header and footer, on every page
>
> Header: "FixGuard AI" in blue on the left; links to Home, How it works,
> Limits; then "Sign in" as a quiet link and "Open the dashboard" as a primary
> button.
>
> Footer: "FixGuard AI — built for the Hostinger 21-Day Startup Challenge."
> Then in small muted text: "Form checks confirm that a submission leaves the
> browser and is accepted by the receiving server. Delivery to a specific
> mailbox is not verified. Reachability is measured from one region, not from
> everywhere."
>
> ## Links — use these exact URLs
>
> - Hero form and every "Run a free audit" button:
>   `https://app.fixguardai.online/?url=` with the value the visitor typed
>   appended, URL-encoded.
> - "Open the dashboard": `https://app.fixguardai.online/`
> - "Sign in": `https://app.fixguardai.online/signin`
> - Any "how it is built" link: `https://app.fixguardai.online/architecture`

---

## Step 2 — check the hero form by hand

The one thing worth verifying in the editor: typing `yourbakery.com` and
pressing the button must land on

```
https://app.fixguardai.online/?url=yourbakery.com
```

If Horizons will not build the string from the input, a plain link to
`https://app.fixguardai.online/` still works — the handoff is nicer, not
load-bearing. The dashboard reads `?url=`, shows the address back, and carries
it through sign-up to a pre-filled audit form.

---

## Step 3 — the badge

Paste into the footer. This snippet is tied to one shared report and expires
30 days after it was created, so regenerate it nearer the deadline from any
completed audit (**Badge**, then copy the script tag):

```html
<script src="https://app.fixguardai.online/api/v1/public/badge/IHKZMhbyD8dFIZvk4ZIOT7JTAUWZ7z0R.js" async></script>
```

If the badge renders broken, remove it rather than leaving it. A broken
verification badge on a QA tool's own site is the worst possible detail.

---

## Step 4 — connect the domain

Only after the links above are correct. Horizons → **Connect domain** →
`fixguardai.online`.

Until then the bare domain answers 503, which is expected: it was moved off
the VPS so the landing page could have it.

---

## Step 5 — changing anything later

One thing per prompt, and say what must not move:

> Change only the hero headline to "…". Leave every other section, all
> colours, all links and the layout exactly as they are.

That is the same discipline FixGuard sells. Using it on your own site is worth
a sentence in the pitch.

---

## Credit budget

| Spend | Credits |
|---|---|
| The rebuild above | 1 |
| Wording fixes, one at a time | 2–3 |
| **Keep in reserve** | **the rest** |

If the rebuild comes out wrong in a way that needs more than three corrections,
cut the third page. Home plus How it works is a complete marketing site; the
limits can live as a section at the bottom of Home.

---

## Step 6 — the modern pass

Run this **after** the site is correct. It changes treatment only, so the
content and links above survive. One credit.

> Keep every section, all copy, all links and all colours exactly as they are.
> Change only the visual treatment, as follows.
>
> **Set the page title** to "FixGuard AI — find what is broken before your
> customers do" and the meta description to "FixGuard opens your site in a real
> browser, submits your forms, and reports what actually happens rather than
> what the page claims." The title is currently empty.
>
> **Motion.** Every section fades up 16px as it scrolls into view, 400ms, ease
> out, once only — never on a loop. Each element in a group starts 60ms after
> the one before it. Everything must be fully visible in its final position
> before any scrolling happens: nothing starts at opacity 0 waiting for a
> scroll event. Respect prefers-reduced-motion by disabling all of it.
>
> **Animate the hero report card, once, on load.** The score dial counts up
> from 0 to 49 over 900ms while its arc draws. The three findings then appear
> one at a time, 120ms apart, each sliding up 12px. Each dark evidence block
> reveals its text left to right, like a terminal printing. Total under 2.5
> seconds, then it rests and stays rested. This is the product doing its job,
> so it must look like measurement, not decoration.
>
> **Depth.** Cards get a large soft shadow: 0 24px 48px -24px rgba(15,23,42,0.18),
> and lift 2px with a slightly stronger shadow on hover, 200ms. The hero report
> card sits higher than everything else. No glass, no blur, no gradients on
> anything except a single very faint radial wash behind the hero.
>
> **Type.** Push the hero headline larger — around 76px on desktop, tracking
> -0.03em, line height 1.02. Section headings around 44px. Keep body text at a
> comfortable reading size and no wider than 65 characters per line.
>
> **Rhythm.** Increase vertical padding between sections to roughly 128px on
> desktop and 72px on mobile. More air, fewer boxes.
>
> **One pinned moment only.** In "How it works", pin the four steps while the
> section scrolls, highlighting each step in turn as it becomes active. Just
> this one section; nothing else pins.
>
> **Buttons.** Primary button lifts 1px and darkens to #0044CC on hover over
> 150ms. Add a small right arrow that slides 3px right on hover.
>
> **Do not** add gradients on text, glassmorphism, emoji, stock photography,
> looping background animation, marquees, or any purple. Do not centre content
> that is currently left-aligned. Do not change any wording.

---

## Step 7 — warm editorial pass, and the audit fixes

FixGuard audited this site on 6 September and scored it **76**. Accessibility
came back **0**: fourteen contrast failures at 3.56:1 where 4.5:1 is the
minimum. Mobile scored 65 on six tap targets under 44px and eighteen text
elements rendering below 12px on a phone.

Those failures and this redesign are the same job. The contrast failures exist
because muted grey sits on a light ground; a warmer ground with darker text
fixes them as a side effect. So this prompt does both.

> Keep every section, all copy, all links and all page structure exactly as
> they are. Change only the visual treatment and the specific accessibility
> problems listed at the end.
>
> **Ground.** Replace the white page background with a warm off-white
> `#F7F4EF`. Cards sit on `#FDFCFA` with a hairline `#E7E1D8` border and a
> 20px radius. The effect to aim for is a warm editorial magazine, not a white
> SaaS page. Sections alternate between the warm ground and `#FDFCFA`.
>
> **Keep the accent blue `#0055FF` exactly as it is.** Do not introduce orange
> or terracotta. The three status colours - `#059669` pass, `#D97706` warning,
> `#DC2626` critical - are reserved for status and must never be used for
> decoration, buttons or headings.
>
> **Headings.** Section headings become uppercase, tightly tracked, two lines
> where the text allows - the "EFFORTLESS PROCESS / EXCEPTIONAL RESULTS"
> treatment. Archivo 800, letter-spacing -0.01em, around 40px. The hero
> headline stays sentence case.
>
> **Hero.** Put the hero content on a large rounded panel, 24px radius, on the
> warm ground, with the report card overlapping its right edge so it breaks
> the panel boundary.
>
> **Floating findings cluster.** Behind and around the report card, add three
> smaller finding cards, each rotated between -4 and +4 degrees, partially
> overlapping, at lower opacity than the main card. They should read as a
> stack of results, and must not cover any text in the main card.
>
> **Stat band.** Add a row of three stat tiles below the hero, the middle one
> filled solid `#0055FF` with white text and the outer two on `#FDFCFA`:
> - "29s" — average full audit, seven checks, one real browser
> - "49 to 97" — one test site, after four scoped prompts
> - "0" — invented numbers in any report
>
> **Category pills.** Where the checks are listed, render them as soft pills:
> pale blue, pale green, pale amber and pale grey backgrounds with dark text
> at 4.5:1 or better. Not solid colour, not white text on pale.
>
> **Fix these, measured on this site:**
> - Every piece of body and muted text must reach 4.5:1 against its actual
>   background. On `#F7F4EF` that means muted text no lighter than `#5B6470`
>   and body text no lighter than `#3F4854`. Do not use `#94A3B8` for text
>   anywhere.
> - Every button, link-button and pill that can be tapped must be at least
>   44px tall, including in the header.
> - No text renders below 14px at a 390px viewport. Check the footer small
>   print and any caption text.
>
> **Do not** add orange, gradients on text, glassmorphism, emoji, stock
> photography, or looping animation. Do not change any wording.

Re-run the audit afterwards. The score moving from 76 with accessibility at 0
to something higher, on the tool's own marketing site, is a stronger demo than
any screenshot.
