"""FixGuard AI API gateway."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, errors
from .routers import audits, prompts, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
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
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)

errors.register(app)

app.include_router(audits.router)
app.include_router(prompts.router)
app.include_router(reports.router)


@app.get("/api/v1/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "fixguard-api", "version": "0.1.0"}
