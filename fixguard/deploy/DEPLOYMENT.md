# Deploying FixGuard

There are three compose files in this repository and they are not
alternatives to taste - each one answers a different question about who owns
ports 80 and 443.

| File | Use when | Who terminates TLS |
|---|---|---|
| `docker-compose.yaml` (repo root) | Deploying through the **Coolify UI** | Coolify's Traefik |
| `deploy-vps.yaml` (repo root) | Deploying **by hand next to** an existing Coolify | Coolify's Traefik |
| `fixguard/docker-compose.yml` | A **bare VPS** with nothing else on it | The bundled nginx |

The live deployment uses the first one.

Both of the first two publish **no host ports**. On a box already running
Coolify, its proxy holds 80 and 443, and a second thing binding them does not
produce a clear error - it produces an intermittently broken site. The third
file is the only one with its own nginx on those ports, and it must not be
used on a box that has Coolify.

---

## Through the Coolify UI  (what the live site runs)

**New resource -> Application**, source = the GitHub repository.

| Field | Value |
|---|---|
| Build Pack | `Docker Compose` |
| Base Directory | `/` |
| Docker Compose Location | `/docker-compose.yaml` |

Two environment variables are required; a third turns on the admin console.
Everything else is already in the compose file:

    FIXGUARD_API_KEY=<generate: openssl rand -hex 32>
    PUBLIC_BASE_URL=https://<your domain>
    ADMIN_EMAILS=you@example.com          # optional, comma-separated

Then set the domain on the **web** service. Leave the **api** service's domain
empty - `web` already proxies `/api` to it from the same origin, and giving
`api` its own hostname just exposes it for no gain.

DNS must already point at the VPS *before* the first deploy. Let's Encrypt
validates over HTTP against whatever the name currently resolves to, so
deploying first and pointing DNS afterwards produces a self-signed
certificate and a browser warning until the next retry.

### The admin console

`ADMIN_EMAILS` is the only way in. Any signed-in account whose email is on
that list sees **System** in its account menu at `/admin`; everyone else gets
a 404 from the API, identical to the answer a stranger gets, so the console
does not advertise itself to accounts that cannot use it.

There is no endpoint that grants admin, and no column storing it. Membership
is read from this variable on every request, which means two things worth
knowing:

* Adding an address takes effect on that account's next request - no restart,
  and it works for somebody who signs up after the deploy.
* Removing one revokes access immediately, including for a session that is
  already open.

Leaving the variable empty disables the console entirely. The boot log says
which of the two it did:

    [boot] admin console: 1 address(es) configured
    [boot] admin console: disabled (ADMIN_EMAILS is empty)

### Settings that live in the compose file, not the UI

`shm_size: 1gb` and `mem_limit` are declared per-service. Coolify honours
both. This matters more than it looks: Docker's default 64 MB `/dev/shm`
makes Chromium die partway through a page load, and FixGuard would report
that as *the audited site* being broken.

---

## By hand, next to an existing Coolify

    git archive --format=tar HEAD | ssh <host> 'tar -x -C /opt/fixguard'
    ssh <host>
    cd /opt/fixguard
    umask 077 && cat > .env <<'ENV'
    FIXGUARD_DOMAIN=<your domain>
    PUBLIC_BASE_URL=https://<your domain>
    ENV
    echo "FIXGUARD_API_KEY=$(openssl rand -hex 32)" >> .env
    docker compose -f deploy-vps.yaml up -d --build

The Traefik labels in that file name the `coolify` network and the
`letsencrypt` resolver, which is what Coolify's proxy is configured with. It
routes to the `web` container only; `api` is deliberately kept off the shared
network, because nothing outside the stack has any business reaching it.

---

## On a bare VPS

    cd fixguard
    cp .env.example .env      # then fill it in
    docker compose up -d --build

This is the only variant that binds 80 and 443 itself, via `nginx/`.

---

## Two health endpoints, on purpose

`/api/v1/health` is liveness: it answers as long as the process is running.
That is what the container healthcheck uses, and it is the only one anything
with a restart policy should watch.

`/api/v1/health/ready` is readiness, and it does real work - writes a row to
prove the disk is not full (SQLite serves reads from a full disk, so a read
proves very little), checks disk headroom, and checks that `/dev/shm` has room
for Chromium's renderer surfaces. It answers 503 when a check fails, so
nothing watching it has to parse the body.

They are separate deliberately. Wiring a restart policy to readiness means one
full disk becomes a restart loop, which takes the service down instead of
leaving it up and complaining.

---

## Verifying a deploy

    curl -s https://<domain>/api/v1/health
    # {"status":"ok","service":"fixguard-api","version":"0.1.0"}

A health check only proves the process is alive. To prove the browser works,
start a real audit - that is the part that needs Chromium, shared memory and
enough RAM:

    curl -X POST https://<domain>/api/v1/audits/start \
      -H 'Content-Type: application/json' -H "X-API-Key: $FIXGUARD_API_KEY" \
      -d '{"domain_url":"https://example.com","i_own_this_site":true,"max_pages":1}'

## When the API answers but audits fail

Three causes, in order of how often they are the cause:

1. **`/dev/shm` too small.** Chromium dies mid-page. Check
   `docker inspect <api container> --format '{{.HostConfig.ShmSize}}'`;
   it should be `1073741824`.
2. **Memory limit too low.** The container is OOM-killed during a page load.
   `docker inspect ... --format '{{.State.OOMKilled}}'`.
3. **Playwright client and image out of step.** `requirements.txt` pins
   `playwright>=1.62,<1.63` against image tag `v1.62.0-noble`. If either moved
   without the other, the error names a browser revision that was never
   downloaded.
