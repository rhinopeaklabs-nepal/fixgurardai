"""FixGuard AI API gateway."""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from . import adminstats, config, db, errors, metrics
from . import accounts
from .routers import admin, audits, auth, prompts, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Expired sessions are dead rows that only grow. Clearing them at boot is
    # enough for a service that restarts on every deploy, and avoids running a
    # scheduler on a box that has one core to spare for Chromium.
    accounts.purge_expired_sessions()

    # An audit's task dies with the process that owns it, so every deploy
    # leaves rows that still say running and never will again. Closing them
    # here, before anything can be served, is the difference between a report
    # page that explains what happened and one that spins forever.
    orphans = adminstats.reconcile_orphans()
    if orphans:
        print(f"[boot] closed {orphans} audit(s) interrupted by a restart", flush=True)

    # Who may open the admin console is read from the environment on every
    # request, so there is nothing to synchronise here - only something worth
    # saying out loud, because an empty list means the console is off.
    # flush because a boot line nobody can find in the logs is not a boot
    # line; stdout here is block-buffered when it is a pipe, which is what it
    # always is under a process manager.
    print(
        f"[boot] admin console: {len(config.ADMIN_EMAILS)} address(es) configured"
        if config.ADMIN_EMAILS
        else "[boot] admin console: disabled (ADMIN_EMAILS is empty)",
        flush=True,
    )

    # Metrics are batched to disk rather than written per request, so the
    # loop that does the batching has to outlive each one.
    flusher = asyncio.create_task(metrics.flusher())
    try:
        yield
    finally:
        flusher.cancel()
        # The task flushes what it is holding when cancelled. Waiting for it
        # is the difference between losing the last thirty seconds of every
        # deploy and not.
        try:
            await flusher
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="FixGuard AI",
    version="0.1.0",
    description="Pre-flight site health auditing for Hostinger AI Builder sites.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # The session cookie has to survive the cross-origin case, which is only
    # local development - in production the dashboard and the API share an
    # origin and CORS never comes into it. Credentials and a wildcard origin
    # are mutually exclusive by spec, so CORS_ORIGINS must stay an explicit
    # list; that is a constraint worth keeping rather than working around.
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# The public share and badge routes exist to be read from somebody else's
# page - that is the entire point of an embeddable badge - so the allowlist
# above, which is right for the credentialed dashboard routes, is wrong for
# them. Without this the badge script fetches its own JSON and the browser
# refuses to let it read the answer, which is what a visitor to the marketing
# site actually saw: a badge that never filled in.
#
# The wildcard is safe here precisely because these routes carry no session:
# the token in the path is the whole authorisation, and anyone holding it was
# handed it deliberately. Credentials and a wildcard are mutually exclusive by
# spec, so the credentials header is removed rather than left to contradict it.
@app.middleware("http")
async def public_routes_are_public(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/public/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        if "access-control-allow-credentials" in response.headers:
            del response.headers["access-control-allow-credentials"]
        response.headers["Vary"] = "Origin"
    return response


# Counts what this process serves, so the admin console can report load
# without a metrics daemon. The numbers reset on deploy and are labelled with
# the moment they started, because a counter that looks cumulative but is not
# is worse than one that says so.
@app.middleware("http")
async def count_requests(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - started) * 1000

    adminstats.requests.record(request.url.path, response.status_code, elapsed)

    # Recorded against the route template rather than the URL. Routing has
    # already happened by the time call_next returns, so the matched route is
    # on the scope; a request that matched nothing is bucketed as "unmatched"
    # so a scanner walking random paths cannot grow this table a row at a time.
    route = request.scope.get("route")
    metrics.record(
        getattr(route, "path", None) or "unmatched",
        response.status_code,
        elapsed,
    )
    return response


errors.register(app)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(audits.router)
app.include_router(prompts.router)
app.include_router(reports.router)


@app.get("/api/v1/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "fixguard-api", "version": "0.1.0"}


@app.get("/api/v1/health/ready", tags=["meta"])
async def ready(response: Response) -> dict:
    """Whether this instance can actually do its job, not merely reply.

    /health stays a liveness check: it answers as long as the process is
    running, which is what a container restart policy should key off. This is
    the readiness question, and it is deliberately a different endpoint,
    because wiring the two together means one full disk takes the container
    down in a restart loop instead of leaving it up and complaining.

    Answers 503 when a check fails so anything watching it does not have to
    parse the body to find out.
    """
    checks: dict[str, dict] = {}

    # A read proves very little - SQLite serves reads from a full disk. The
    # thing that breaks first is the write.
    try:
        with db.get_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _readiness (id INTEGER PRIMARY KEY, at TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO _readiness (id, at) VALUES (1, ?)",
                (dt.datetime.now(dt.timezone.utc).isoformat(),),
            )
        checks["database_writable"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        checks["database_writable"] = {"ok": False, "detail": str(exc)[:200]}

    # Chromium needs somewhere to put renderer surfaces, and a browser that
    # cannot start reports as the audited site being broken - a failure that
    # blames the customer for our own disk.
    stats = adminstats.process_stats()
    disk = stats.get("disk")
    checks["disk_headroom"] = (
        {"ok": disk["used_percent"] < 95, "used_percent": disk["used_percent"]}
        if disk
        else {"ok": True, "detail": "not measurable here"}
    )

    shm = os.statvfs("/dev/shm") if hasattr(os, "statvfs") else None
    if shm:
        free_mb = shm.f_bavail * shm.f_frsize / (1024 * 1024)
        # Docker's 64 MB default is what makes Chromium die partway through a
        # page load, so this is checked rather than assumed.
        checks["shared_memory"] = {"ok": free_mb >= 128, "free_mb": round(free_mb)}

    ok = all(c["ok"] for c in checks.values())
    if not ok:
        response.status_code = 503
    return {"ready": ok, "checks": checks, "uptime_seconds": stats["uptime_seconds"]}
