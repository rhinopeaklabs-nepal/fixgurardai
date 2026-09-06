# AI Builder page — what to paste

You have **15 AI Builder credits**. Each regeneration spends one, so the aim is
one strong prompt, then hand edits rather than rebuilds.

Build **one page**. A multi-page site costs credits you do not have and adds
nothing a judge will look at.

---

## Before you start: do not build a tool here

The prompt box says *"Create a tool that…"*, and the temptation is to build a
small audit tool inside AI Builder. Don't.

It cannot drive Chromium, submit a form, or read a console. Anything built
there would be a weaker copy of the product that already exists, it would cost
most of the fifteen credits, and it would invite the comparison. AI Builder's
job in this project is the **front door**: marketing, and an intake form that
hands a URL to the real thing.

Ignore the placeholder and the templates. A template costs credits to fight.

---

## Step 1 — the build prompt

Paste this whole block as your first prompt.

> Build a one-page marketing site for **FixGuard AI**, a pre-flight QA tool for
> websites built with Hostinger AI Builder.
>
> Tone: direct and technical, not salesy. No stock-photo people. No emoji.
> Dark navy and white, one blue accent (#0055FF). Generous whitespace, large
> readable type.
>
> Sections in this order:
>
> 1. **Hero.** Headline: "Your contact form says it sent. It didn't."
>    Sub-headline: "FixGuard opens your site in a real browser, submits your
>    forms, and tells you what actually happened — not what the page claims."
>    Below it, a single text input labelled "Your website address" with a
>    button labelled "Run a free audit".
>
> 2. **The problem**, three short cards:
>    - *Silent form failures.* The page shows "Thank you, message sent" but
>      nothing ever left the browser. Every enquiry is lost, and you find out
>      when a customer complains.
>    - *Redirect and re-render loops.* The page reloads itself forever, or
>      re-renders hundreds of times a second. No error is logged.
>    - *Wasted AI credits.* You ask the builder to change one button and it
>      rewrites your layout, so you spend more credits undoing it.
>
> 3. **How it works**, four numbered steps:
>    1. Paste your site address.
>    2. FixGuard drives a real Chromium browser, fills your forms and submits them.
>    3. You get a 0–100 health score with every finding explained in plain English.
>    4. Each finding becomes a tightly scoped prompt you paste back into AI Builder.
>
> 4. **What it checks**, a compact list: forms that silently fail, redirect
>    loops, infinite re-renders, broken internal links, JavaScript errors,
>    broken images, DNS records that disagree with each other, TLS certificate
>    expiry, accessibility, mobile layout, and Core Web Vitals.
>
> 5. **Proof.** A short before-and-after: "One test site scored 49 out of 100.
>    After applying four FixGuard prompts it scored 97, with six issues fixed
>    and none introduced."
>
> 6. **Footer.** "FixGuard AI — built for the Hostinger 21-Day Startup
>    Challenge." Small print: "Form checks confirm a submission leaves the
>    browser and is accepted by the receiving server. They do not verify
>    inbox delivery."

---

## Step 2 — wire the hero input by hand

This is the step that makes AI Builder part of the product rather than a page
beside it. Do it in the editor, not by re-prompting.

The hero button must send the visitor to the dashboard with their address
already carried across:

```
https://fixguardai.online/?url=THE_VALUE_THEY_TYPED
```

In the editor, set the button's action to open that URL, appending the input's
value to `?url=`. If AI Builder will not let you build the string, the fallback
that still works is a plain link to `https://fixguardai.online/` — the handoff
is nicer, not load-bearing.

The dashboard already handles the rest: it reads `?url=`, shows the address
back on the landing page, carries it through sign-up, and arrives at the audit
form pre-filled.

Also by hand:

- Point any "See how it works" link at `https://fixguardai.online/architecture`.
- Paste the verification badge snippet into the footer. Get it from any
  completed audit: **Badge**, then copy the `<script>` tag.

---

## Step 3 — if you must re-prompt

Change one thing at a time and say so explicitly, for example:

> Change only the hero headline to "…". Leave every other section, the colours
> and the layout exactly as they are.

That is the same discipline FixGuard sells. Using it on your own site is worth
mentioning in the pitch.

---

## Credit budget

| Spend | Credits |
|---|---|
| First generation | 1 |
| Wording tweaks | 2–3 |
| **Keep in reserve** | **10+** |

Keep the reserve. If a demo breaks on the day you will want credits to fix it,
and unspent credits cost you nothing.
