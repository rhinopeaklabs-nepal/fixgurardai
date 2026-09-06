# Deploying FixGuard on Coolify

Coolify runs on the Hostinger VPS at `31.97.70.188:8000`. It brings its own
reverse proxy (Traefik) and its own Let's Encrypt integration, so the
`nginx` service in `docker-compose.yml` is **not** used on this path — it
would fight Traefik for ports 80 and 443.

Deploy the backend only. The dashboard stays on Hostinger Web Hosting, so
both products still do real work:

    Web Hosting  ->  dashboard (static React build)
    VPS/Coolify  ->  audit engine (FastAPI + Chromium)

---

## 1. Create the application

In the `FixGuard AI / production` environment: **New resource -> Application**.

* Source: **Public Repository** if the repo is public. If it is private,
  first connect GitHub under *Sources*, then pick **Private Repository
  (GitHub App)** — a plain HTTPS URL cannot authenticate.
* Repository: `https://github.com/rhinopeaklabs-nepal/fixgurardai`
* Branch: `main`
* Build Pack: **Dockerfile**

## 2. Build configuration

| Field | Value |
|---|---|
| Base Directory | `/fixguard/backend` |
| Dockerfile Location | `Dockerfile` |
| Ports Exposes | `8000` |

`Base Directory` matters: the Dockerfile does `COPY requirements.txt .` and
`COPY app ./app`, both relative to the build context. Pointing Coolify at
the repository root makes the context the root, where neither path exists,
and the build fails on the first COPY.

## 3. Custom Docker options  (required, not optional)

Under *Advanced -> Custom Docker Options*:

    --shm-size=1g

Docker's default `/dev/shm` is 64 MB. Chromium uses shared memory for
renderer surfaces and crashes partway through a page load without warning
when it runs out — the audit reports a dead site that is actually fine.
`docker-compose.yml` sets `shm_size: 1gb` for the same reason; on Coolify
this is the only place to say it.

## 4. Resource limits

VPS KVM 1 is 1 vCPU / 4 GB, and Coolify itself holds roughly 1 GB.

* Memory limit: `2500M`
* CPU limit: leave unset — the audit is one browser at a time already
  (`MAX_CONCURRENT_AUDITS=1`), and capping CPU only makes each audit
  slower, not the box safer.

## 5. Environment variables

    FIXGUARD_API_KEY=<a long random string, not the dev key>
    CORS_ORIGINS=https://<your-web-hosting-domain>
    PUBLIC_BASE_URL=https://<your-web-hosting-domain>
    MAX_CONCURRENT_AUDITS=1
    AUDIT_HARD_TIMEOUT_S=90
    FIXGUARD_DATA_DIR=/data

Generate the key rather than reusing `fixguard-dev-key`:

    openssl rand -hex 32

`CORS_ORIGINS` is where the dashboard is served from, not where the API
lives. Getting these two backwards is why the browser reports a CORS
failure while curl against the same endpoint succeeds.

`PUBLIC_BASE_URL` is the origin written into shareable report links, so it
must be the dashboard's domain for those links to resolve.

## 6. Persistent storage

*Storages -> Add* :

| Name | Mount Path |
|---|---|
| `fixguard-data` | `/data` |

Without this the SQLite database lives in the container's writable layer
and every redeploy silently discards all audit history.

## 7. Domain and TLS

Set the application's domain to an FQDN that already resolves to
`31.97.70.188` — the VPS hostname `srv1953517.hstgr.cloud` does, so it
works without buying anything. Coolify requests the certificate itself; do
not add one manually.

Enter it as `https://...` so Traefik issues a certificate rather than
serving plain HTTP.

## 8. Health check

* Path: `/api/v1/health`
* Port: `8000`

The image already declares a `HEALTHCHECK`, but Coolify uses its own to
decide when a deploy succeeded, and the default `/` returns 404 here — the
deploy would be marked failed on a container that is working.

## 9. Point the dashboard at it

On Web Hosting, rebuild the dashboard with:

    VITE_API_BASE_URL=https://<api-domain>
    VITE_API_KEY=<the same FIXGUARD_API_KEY>

then upload `dashboard/dist/`.

---

## First deploy is slow

The Playwright base image is roughly 2 GB and the VPS has 1 vCPU. Expect
8-15 minutes for the first build. Later deploys reuse the layers unless
`requirements.txt` changes.

## If audits fail but the API answers

Almost always one of three things, in order of likelihood:

1. `--shm-size=1g` missing (step 3) — Chromium dies mid-page.
2. Memory limit too low — the container is OOM-killed during a page load.
   Check `docker inspect` for `OOMKilled: true`.
3. Playwright client and image out of step. `requirements.txt` pins
   `playwright>=1.62,<1.63` against image tag `v1.62.0-noble`; if either
   moved without the other, the error names a missing browser revision.
