"""Audit endpoints, following the SRS section 8 paths and contract."""
from __future__ import annotations

import asyncio
import datetime as dt
import secrets

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response, StreamingResponse

from .. import (
    accounts, auth_session, compare, config, db, ratelimit, report_render,
    schemas,
)
from ..audit import runner
from ..errors import FixGuardError
from . import auth

router = APIRouter(prefix="/api/v1", tags=["audits"])

# Everything run with the API key rather than a session belongs to one
# synthetic owner. It is a real value rather than NULL so that keyed runs are
# still scoped to something, and so they can never be confused with the
# pre-accounts rows, which stay unowned and therefore invisible.
SERVICE_OWNER = "svc:api-key"


def require_key(x_api_key: str | None = Header(default=None)) -> str:
    if not secrets.compare_digest(x_api_key or "", config.API_KEY):
        raise FixGuardError("AUTH_INVALID", "The API key is missing or invalid.")
    return x_api_key or ""


def _load(audit_id: str, owner_id: str | None = None) -> dict:
    """Fetch an audit, refusing one that belongs to somebody else.

    Somebody else's audit answers AUDIT_NOT_FOUND rather than a distinct
    "forbidden". A different status would let anyone with a valid session
    walk the id space and learn which audit ids exist, and the ids are the
    only thing standing between a stranger and a report about a real site.

    owner_id is optional so the public share-link path, which has no session
    at all and is authorised by holding the token, can still read a run.
    """
    run = db.get_run(audit_id)
    missing = FixGuardError(
        "AUDIT_NOT_FOUND", "The requested audit_id does not exist.", audit_id
    )
    if not run:
        raise missing
    if owner_id is not None and run.get("owner_id") != owner_id:
        raise missing
    return run


def identity(request: Request) -> dict:
    """Who is making this call, and what their work belongs to.

    Two ways in, and they are not equivalent:

    * A **session cookie** - a person using the dashboard. Their audits are
      owned by their account and only they can read them back.
    * The **API key** - the acceptance suite and anything scripted. It gets a
      single fixed owner rather than a per-caller one, because a shared key
      cannot distinguish its callers and pretending otherwise would put one
      script's results in front of another.

    Rate limits count against ``bucket``, which is the account for a signed-in
    person and the address for a keyed caller. Counting keyed calls per key
    would put every scripted client in one bucket again, which is the problem
    accounts were introduced to fix.
    """
    user = auth.current_user(request)
    if user:
        return {"owner_id": user["id"], "bucket": f"user:{user['id']}", "user": user}

    key = request.headers.get("x-api-key") or ""
    if secrets.compare_digest(key, config.API_KEY):
        ip = (request.headers.get("x-real-ip") or "").strip()
        return {
            "owner_id": SERVICE_OWNER,
            "bucket": f"svc:{ip}" if ip else "svc:key",
            "user": None,
        }

    raise FixGuardError(
        "AUTH_REQUIRED",
        "Sign in to run an audit. Your audits stay private to your account.",
    )


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
    who: dict = Depends(identity),
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

    remaining = _enforce_rate_limit(who["bucket"])
    test_email = payload.test_email or f"test-{secrets.token_hex(6)}@fixguard.test"
    audit_id = runner.start(
        payload.domain_url,
        test_email,
        payload.modules,
        rate_key=who["bucket"],
        owner_id=who["owner_id"],
        form_selector=payload.form_selector,
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
    return await start_audit(payload, who)


@router.post(
    "/audits/{audit_id}/retry",
    response_model=schemas.StartAuditResponse,
    status_code=201,
)
async def retry_audit(
    audit_id: str, who: dict = Depends(identity)
) -> schemas.StartAuditResponse:
    """NFR 5.3: failed audits are retryable in one click."""
    run = _load(audit_id, who["owner_id"])
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
        rate_key=who["bucket"],
        owner_id=who["owner_id"],
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
@router.get("/audits")
async def list_audits(limit: int = 25, who: dict = Depends(identity)) -> dict:
    return {
        "audits": db.list_runs(min(max(limit, 1), 100), who["owner_id"]),
        "quota": ratelimit.quota(who["bucket"]),
    }


@router.get("/quota")
async def get_quota(who: dict = Depends(identity)) -> dict:
    return ratelimit.quota(who["bucket"])


@router.get(
    "/audits/{audit_id}/status",
    response_model=schemas.AuditStatusResponse,
)
async def audit_status(audit_id: str, who: dict = Depends(identity)) -> dict:
    return schemas.status_view(_load(audit_id, who["owner_id"]))


@router.get("/audits/{audit_id}/report")
async def audit_report(audit_id: str, who: dict = Depends(identity)) -> dict:
    run = _load(audit_id, who["owner_id"])
    share = db.find_share_link_for_audit(audit_id)
    run["share_url"] = f"{config.PUBLIC_BASE_URL}/r/{share['token']}" if share else None
    return run


# Alias: the full report is the natural default for GET /audits/{id}.
@router.get("/audits/{audit_id}")
async def get_audit(audit_id: str, who: dict = Depends(identity)) -> dict:
    return await audit_report(audit_id, who)


@router.get("/audits/{audit_id}/stream")
async def stream_audit(
    audit_id: str, request: Request, who: dict = Depends(identity)
) -> StreamingResponse:
    """SSE progress.

    EventSource cannot attach headers, which is why this used to lean on
    the unguessable audit id as its only capability. It is same-origin
    though, so the browser sends the session cookie without being asked -
    and a guessed id now gets nothing.
    """
    run = _load(audit_id, who["owner_id"])
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


@router.get("/audits/{audit_id}/compare")
async def compare_audits(
    audit_id: str, baseline: str | None = None,
    who: dict = Depends(identity),
) -> dict:
    """Diff this audit against an earlier one of the same site.

    With no ``baseline`` it picks the most recent earlier audit of the same
    URL, which is what you want right after re-running a fix.
    """
    after = _load(audit_id, who["owner_id"])
    if after["status"] != "complete":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE", "This audit has not finished yet.", audit_id
        )

    if baseline:
        before = _load(baseline, who["owner_id"])
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


@router.get("/reports/{audit_id}/pdf")
async def report_pdf(audit_id: str, who: dict = Depends(identity)) -> Response:
    """FR-4.2: branded PDF certificate."""
    run = _load(audit_id, who["owner_id"])
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


@router.get("/reports/{audit_id}/badge")
async def report_badge(audit_id: str, who: dict = Depends(identity)) -> dict:
    """FR-4.4: the embed snippet, once the audit has a share link."""
    run = _load(audit_id, who["owner_id"])
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
# Delete
# --------------------------------------------------------------------------
@router.delete("/audits/{audit_id}", status_code=200)
async def delete_audit(audit_id: str, who: dict = Depends(identity)) -> dict:
    """SRS 10.2: reports are kept until the person who made them removes one.

    Answers AUDIT_NOT_FOUND when the audit belongs to somebody else, matching
    every other read: a distinct "forbidden" would confirm that an id exists.
    """
    if not db.delete_run(audit_id, who["owner_id"]):
        raise FixGuardError(
            "AUDIT_NOT_FOUND", "The requested audit_id does not exist.", audit_id
        )
    return {"deleted": audit_id}


@router.delete("/account/data", status_code=200)
async def delete_my_data(who: dict = Depends(identity)) -> dict:
    """SRS 10.4: erase everything this account has produced, keep the account.

    Share links and geo rows follow their audit through ON DELETE CASCADE, so
    a link handed to a client stops resolving at the same moment - which is
    the point of asking for deletion.
    """
    return db.delete_everything_for(who["owner_id"])


@router.delete("/account", status_code=200)
async def delete_my_account(
    request: Request, response: Response, who: dict = Depends(identity)
) -> dict:
    """The account itself, and everything it made.

    Refused for the API-key identity: that owner is shared by every scripted
    caller, so honouring it would delete work belonging to whoever else is
    using the key.
    """
    if not who.get("user"):
        raise FixGuardError(
            "VALIDATION_ERROR",
            "Only a signed-in account can be deleted. The API key identity is "
            "shared, so removing it would take other callers' data with it.",
        )
    counts = db.delete_everything_for(who["owner_id"])
    db.delete_account(who["user"]["id"])
    accounts.end_session(request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"deleted_account": True, **counts}


# --------------------------------------------------------------------------
# Share
# --------------------------------------------------------------------------
@router.post(
    "/audits/{audit_id}/share",
    response_model=schemas.ShareResponse,
)
async def create_share(
    audit_id: str, who: dict = Depends(identity)
) -> schemas.ShareResponse:
    run = _load(audit_id, who["owner_id"])
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
