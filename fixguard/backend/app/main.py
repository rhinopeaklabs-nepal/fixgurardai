"""FixGuard AI API gateway."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import adminstats, config, db, errors
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

    yield


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
    adminstats.requests.record(
        request.url.path, response.status_code,
        (time.perf_counter() - started) * 1000,
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
