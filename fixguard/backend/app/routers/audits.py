"""Audit endpoints, following the SRS section 8 paths and contract."""
from __future__ import annotations

import asyncio
import datetime as dt
import secrets

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response, StreamingResponse

from .. import auth_session, compare, config, db, ratelimit, report_render, schemas
from ..audit import runner
from ..errors import FixGuardError

router = APIRouter(prefix="/api/v1", tags=["audits"])


def require_key(x_api_key: str | None = Header(default=None)) -> str:
    if not secrets.compare_digest(x_api_key or "", config.API_KEY):
        raise FixGuardError("AUTH_INVALID", "The API key is missing or invalid.")
    return x_api_key or ""


def _load(audit_id: str) -> dict:
    run = db.get_run(audit_id)
    if not run:
        raise FixGuardError(
            "AUDIT_NOT_FOUND", "The requested audit_id does not exist.", audit_id
        )
    return run


def client_bucket(request: Request, api_key: str = Depends(require_key)) -> str:
    """The identity a rate limit should be counted against.

    Counting per API key made sense when the key was per-user. The dashboard
    now ships one shared key in its bundle, so per-key counting means the
    first visitor of the hour spends everyone else's quota - including a
    judge's, halfway through evaluating the tool. Without accounts, the
    closest honest unit is the client itself.

    X-Real-IP is set by our own nginx from the address it resolved, never
    copied from the incoming request, so a caller cannot widen its own quota
    by sending the header. A request that did not come through nginx has no
    such header and falls back to the key, which is the old behaviour and
    still bounded.
    """
    ip = (request.headers.get("x-real-ip") or "").strip()
    return f"ip:{ip}" if ip else f"key:{api_key}"


def _enforce_rate_limit(bucket: str) -> int:
    allowed, remaining, retry = ratelimit.check_and_record(bucket)
    if not allowed:
        wait = ratelimit.describe_wait(retry["seconds"])
        raise FixGuardError(
            "RATE_LIMIT_EXCEEDED",
            f"You have used all {config.RATE_LIMIT_PER_HOUR} audits for this "
            f"hour. The next one frees up {wait}.",
        )
    return remaining


# --------------------------------------------------------------------------
# Start
# --------------------------------------------------------------------------
@router.post(
    "/audits/start",
    response_model=schemas.StartAuditResponse,
    status_code=201,
)
async def start_audit(
    payload: schemas.StartAuditRequest,
    bucket: str = Depends(client_bucket),
) -> schemas.StartAuditResponse:
    auth: dict | None = None
    if payload.auth and (payload.auth.cookie_header or payload.auth.headers):
        cookies: list = []
        found_headers: dict = {}
        if payload.auth.cookie_header:
            try:
                cookies, found_headers = auth_session.parse_paste(
                    payload.auth.cookie_header, payload.domain_url
                )
            except auth_session.AuthError as exc:
                raise FixGuardError("VALIDATION_ERROR", str(exc)) from exc
        auth = {
            "cookies": cookies,
            "headers": {**found_headers, **(payload.auth.headers or {})},
            "verify_text": payload.auth.verify_text,
            "submit_forms": payload.auth.submit_forms,
        }

    remaining = _enforce_rate_limit(bucket)
    test_email = payload.test_email or f"test-{secrets.token_hex(6)}@fixguard.test"
    audit_id = runner.start(
        payload.domain_url,
        test_email,
        payload.modules,
        rate_key=bucket,
        max_pages=payload.max_pages,
        auth=auth,
    )
    return schemas.StartAuditResponse(
        audit_id=audit_id,
        status="queued",
        sse_url=f"/api/v1/audits/{audit_id}/stream",
        modules=payload.modules,
        rate_limit_remaining=remaining,
    )


# Convenience alias so `POST /audits` behaves the same as `/audits/start`.
@router.post("/audits", response_model=schemas.StartAuditResponse, status_code=201)
async def start_audit_alias(
    payload: schemas.StartAuditRequest,
    bucket: str = Depends(client_bucket),
) -> schemas.StartAuditResponse:
    return await start_audit(payload, bucket)


@router.post(
    "/audits/{audit_id}/retry",
    response_model=schemas.StartAuditResponse,
    status_code=201,
)
async def retry_audit(
    audit_id: str, bucket: str = Depends(client_bucket)
) -> schemas.StartAuditResponse:
    """NFR 5.3: failed audits are retryable in one click."""
    run = _load(audit_id)
    if run["status"] != "failed":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE",
            "Only a failed audit can be retried.",
            audit_id,
        )
    remaining = _enforce_rate_limit(bucket)
    modules = run.get("modules_selected") or schemas.ALL_MODULES
    new_id = runner.start(
        run["target_url"],
        f"test-{secrets.token_hex(6)}@fixguard.test",
        modules,
        retry_of=audit_id,
        rate_key=bucket,
    )
    return schemas.StartAuditResponse(
        audit_id=new_id,
        status="queued",
        sse_url=f"/api/v1/audits/{new_id}/stream",
        modules=modules,
        rate_limit_remaining=remaining,
    )


# --------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------
@router.get("/audits", dependencies=[Depends(require_key)])
async def list_audits(limit: int = 25, bucket: str = Depends(client_bucket)) -> dict:
    return {
        "audits": db.list_runs(min(max(limit, 1), 100)),
        "quota": ratelimit.quota(bucket),
    }


@router.get("/quota")
async def get_quota(bucket: str = Depends(client_bucket)) -> dict:
    return ratelimit.quota(bucket)


@router.get(
    "/audits/{audit_id}/status",
    response_model=schemas.AuditStatusResponse,
    dependencies=[Depends(require_key)],
)
async def audit_status(audit_id: str) -> dict:
    return schemas.status_view(_load(audit_id))


@router.get("/audits/{audit_id}/report", dependencies=[Depends(require_key)])
async def audit_report(audit_id: str) -> dict:
    run = _load(audit_id)
    share = db.find_share_link_for_audit(audit_id)
    run["share_url"] = f"{config.PUBLIC_BASE_URL}/r/{share['token']}" if share else None
    return run


# Alias: the full report is the natural default for GET /audits/{id}.
@router.get("/audits/{audit_id}", dependencies=[Depends(require_key)])
async def get_audit(audit_id: str) -> dict:
    return await audit_report(audit_id)


@router.get("/audits/{audit_id}/stream")
async def stream_audit(audit_id: str, request: Request) -> StreamingResponse:
    """SSE progress.

    Browsers cannot attach headers to EventSource, so the unguessable audit
    UUID acts as the capability for this read-only progress channel.
    """
    run = _load(audit_id)
    queue = runner.subscribe(audit_id)

    async def gen():
        try:
            yield runner.sse_format(
                {
                    "event": "progress",
                    "step": run.get("stage") or "Queued",
                    "stage": "connected",
                    "percent": run.get("progress_percent") or 0,
                }
            )
            if run["status"] in {"complete", "failed"}:
                if run["status"] == "complete":
                    yield runner.sse_format(
                        {
                            "event": "complete",
                            "audit_id": audit_id,
                            "health_score": run.get("health_score"),
                            "grade": run.get("grade"),
                        }
                    )
                else:
                    yield runner.sse_format(
                        {
                            "event": "failed",
                            "audit_id": audit_id,
                            "error": {
                                "code": run.get("error_code"),
                                "message": run.get("error_detail"),
                                "audit_id": audit_id,
                                "retryable": bool(run.get("retryable")),
                            },
                        }
                    )
                return

            while True:
                if await request.is_disconnected():
                    return
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if payload.get("event") == "end":
                    return
                yield runner.sse_format(payload)
        finally:
            runner.unsubscribe(audit_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # stop NGINX buffering the stream
        },
    )


@router.get("/audits/{audit_id}/compare", dependencies=[Depends(require_key)])
async def compare_audits(audit_id: str, baseline: str | None = None) -> dict:
    """Diff this audit against an earlier one of the same site.

    With no ``baseline`` it picks the most recent earlier audit of the same
    URL, which is what you want right after re-running a fix.
    """
    after = _load(audit_id)
    if after["status"] != "complete":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE", "This audit has not finished yet.", audit_id
        )

    if baseline:
        before = _load(baseline)
    else:
        before = db.previous_run_for(
            after["target_url"], after["created_at"], after["id"]
        )
    if not before:
        raise FixGuardError(
            "AUDIT_NOT_FOUND",
            "There is no earlier completed audit of this address to compare "
            "against. Run the audit again after applying a fix.",
            audit_id,
        )
    if before["status"] != "complete":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE", "The baseline audit did not complete.", before["id"]
        )

    return compare.build(before, after)


@router.get("/reports/{audit_id}/pdf", dependencies=[Depends(require_key)])
async def report_pdf(audit_id: str) -> Response:
    """FR-4.2: branded PDF certificate."""
    run = _load(audit_id)
    if run["status"] != "complete":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE", "The audit is not complete yet.", audit_id
        )
    pdf = await report_render.render_pdf(run)
    host = (run["target_url"].split("//")[-1].split("/")[0] or "site").replace(":", "-")
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="fixguard-{host}-{audit_id[:8]}.pdf"'
        },
    )


@router.get("/reports/{audit_id}/badge", dependencies=[Depends(require_key)])
async def report_badge(audit_id: str) -> dict:
    """FR-4.4: the embed snippet, once the audit has a share link."""
    run = _load(audit_id)
    share = db.find_share_link_for_audit(audit_id)
    if not share:
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE",
            "Create a share link first; the badge links back to the public report.",
            audit_id,
        )
    token = share["token"]
    return {
        "token": token,
        "embed_script": f'<script src="{config.API_PUBLIC_URL}'
                        f'/api/v1/public/badge/{token}.js" async></script>',
        "image_url": f"{config.API_PUBLIC_URL}/api/v1/public/badge/{token}.svg",
        "report_url": f"{config.PUBLIC_BASE_URL}/r/{token}",
        "preview_svg": report_render.badge_svg(
            run.get("health_score"), run.get("grade") or ""
        ),
    }


# --------------------------------------------------------------------------
# Share
# --------------------------------------------------------------------------
@router.post(
    "/audits/{audit_id}/share",
    response_model=schemas.ShareResponse,
    dependencies=[Depends(require_key)],
)
async def create_share(audit_id: str) -> schemas.ShareResponse:
    run = _load(audit_id)
    if run["status"] != "complete":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE", "The audit is not complete yet.", audit_id
        )

    existing = db.find_share_link_for_audit(audit_id)
    now = dt.datetime.now(dt.timezone.utc)
    if existing and dt.datetime.fromisoformat(existing["expires_at"]) > now:
        return schemas.ShareResponse(
            token=existing["token"],
            share_url=f"{config.PUBLIC_BASE_URL}/r/{existing['token']}",
            expires_at=existing["expires_at"],
        )

    token = secrets.token_urlsafe(24)
    expires = now + dt.timedelta(days=config.SHARE_LINK_TTL_DAYS)
    db.insert_share_link(token, audit_id, now.isoformat(), expires.isoformat())
    return schemas.ShareResponse(
        token=token,
        share_url=f"{config.PUBLIC_BASE_URL}/r/{token}",
        expires_at=expires.isoformat(),
    )
