# FixGuard AI — from laptop to submitted

Challenge closes **24 September 2026**; winners announced **29 September**.
Everything below is ordered so that if you stop at any point, what you have is
still demonstrable.

---

## Day 1 — get it live

### 1. Upload the code to the VPS

From the project folder on your laptop:

```bash
scp -r "C:/My Files/FIX GUARD/fixguard" root@31.97.70.188:/opt/
```

If `scp` is slow, exclude what the server does not need:

```bash
tar --exclude=node_modules --exclude=.venv --exclude=dist --exclude=__pycache__ \
    -czf fixguard.tar.gz -C "C:/My Files/FIX GUARD" fixguard
scp fixguard.tar.gz root@31.97.70.188:/opt/
ssh root@31.97.70.188 'cd /opt && tar xzf fixguard.tar.gz'
```

### 2. Bootstrap the server

```bash
ssh root@31.97.70.188 'CERT_EMAIL=you@example.com bash /opt/fixguard/deploy/bootstrap-vps.sh'
```

It installs Docker if missing, adds 2 GB of swap (KVM 1 has 4 GB and Chromium
is spiky), opens 80/443, generates an API key into `.env`, requests a TLS
certificate for `srv1953517.hstgr.cloud`, and starts the stack.

The first run stops and asks you to edit `.env`. Set your dashboard domain:

```bash
ssh root@31.97.70.188 'nano /opt/fixguard/.env'
```

```
CORS_ORIGINS=https://your-dashboard-domain
PUBLIC_BASE_URL=https://your-dashboard-domain
API_PUBLIC_URL=https://srv1953517.hstgr.cloud
```

Then run the bootstrap again. Note the API key it prints — you need it next.

### 3. Check it

```bash
curl https://srv1953517.hstgr.cloud/api/v1/health
```

Expect `{"status":"ok","service":"fixguard-api","version":"0.1.0"}`.

### 4. Build and upload the dashboard

On your laptop, in `fixguard/dashboard`, create `.env`:

```
VITE_API_BASE_URL=https://srv1953517.hstgr.cloud
VITE_API_KEY=<the key the bootstrap printed>
```

```bash
npm run build
```

Upload **the contents of `dist/`** to `public_html` on Web Hosting, then upload
`deploy/htaccess-for-web-hosting.txt` as `.htaccess`. Without it, `/prompts`
and every `/r/<token>` share link 404 on refresh.

### 5. Verify the join

Open your dashboard, run an audit against any public site, and confirm the
progress bar moves. If it does not, it is almost always CORS: `CORS_ORIGINS` on
the VPS must exactly match your dashboard origin, scheme included.

### 6. AI Builder page

Follow `deploy/AI-BUILDER-BRIEF.md`. One page, one prompt, hand-edit after.
Keep 10+ credits in reserve.

**End of Day 1 you have all four products live.** That alone beats most entries.

---

## Days 2–3 — prove it on real sites

Audit five real AI Builder sites. Ask in Discord for volunteers — that doubles
as visible participation, which Igor has said he notices.

For each: record the score, what it found, and whether the finding was true.
A false positive on a real site is worth more to you now than another feature.

Then run the acceptance suite against the deployed API and keep the output:

```bash
cd backend && .venv/Scripts/python -m tests.test_acceptance
```

---

## Days 4–5 — the pitch video

Two minutes. Structure that works:

| Time | What | Shown |
|---|---|---|
| 0:00–0:20 | The problem | A form showing "Message sent" with the network tab empty |
| 0:20–1:00 | The fix loop | Audit scores 49 → copy a fix prompt → paste into AI Builder → re-audit → **49 to 97, +48** |
| 1:00–1:30 | Architecture | Your `/architecture` page, live status per product |
| 1:30–2:00 | Proof | PDF certificate, shared report, badge |

The 49 → 97 comparison is your strongest thirty seconds. Rehearse it until it
runs without a stumble. Reproduce it with `testbed/fixed/` — the steps are in
that folder's README.

Record with the deployed URLs, never localhost.

---

## Days 6–7 — submission

- README, `docs/SRS-TRACEABILITY.md`, and the acceptance output as evidence.
- Screenshots of Hostinger Agent sessions where you actually used it.
- Submit early. Do not discover a broken link at 23:50 on the 24th.

---

## What to say, and what not to

**Say:**
- FixGuard confirms a submission leaves the browser and the server accepts it.
- Reachability is measured from one region, of three the spec wants.
- The scoping engine runs with no model at all — zero inference cost per prompt.

**Never say:**
- That it verifies email reached an inbox. It cannot; your site's mail never
  passes through FixGuard.
- That it calls a Hostinger AI API. Hostinger Agent is an hPanel assistant with
  no endpoint. You used it to build, which is what the challenge asked for.

A judge who catches one overclaim discounts everything else you said.

---

## If something breaks

```bash
ssh root@31.97.70.188
cd /opt/fixguard
docker compose logs -f api        # what the API is doing
docker compose restart            # most transient problems
docker stats --no-stream          # memory, if audits are timing out
free -h                           # confirm swap is active
```

Audits timing out on the VPS but not your laptop usually means memory
pressure. Confirm swap is on, and keep `MAX_CONCURRENT_AUDITS=1`.
