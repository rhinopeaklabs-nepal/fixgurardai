"""FixGuard AI API gateway."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, errors
from . import accounts
from .routers import audits, auth, prompts, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Expired sessions are dead rows that only grow. Clearing them at boot is
    # enough for a service that restarts on every deploy, and avoids running a
    # scheduler on a box that has one core to spare for Chromium.
    accounts.purge_expired_sessions()
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

errors.register(app)

app.include_router(auth.router)
app.include_router(audits.router)
app.include_router(prompts.router)
app.include_router(reports.router)


@app.get("/api/v1/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "fixguard-api", "version": "0.1.0"}
