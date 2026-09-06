"""Public, unauthenticated report access via share token (FR-4.3)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from .. import config, db, report_render, schemas
from ..errors import FixGuardError
from .audits import require_key

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/reports/{token}")
async def get_shared_report(
    token: str,
    mode: str = Query("client", pattern="^(client|developer)$"),
) -> dict:
    link = db.get_share_link(token)
    if not link:
        raise FixGuardError("REPORT_NOT_FOUND", "This report could not be found.")

    if dt.datetime.fromisoformat(link["expires_at"]) < dt.datetime.now(dt.timezone.utc):
        raise FixGuardError("REPORT_EXPIRED", "This report link has expired.")

    run = db.get_run(link["audit_id"])
    if not run:
        raise FixGuardError("REPORT_NOT_FOUND", "This report could not be found.")

    return schemas.public_view(run, mode)


def _run_for_token(token: str) -> dict:
    link = db.get_share_link(token)
    if not link:
        raise FixGuardError("REPORT_NOT_FOUND", "This report could not be found.")
    if dt.datetime.fromisoformat(link["expires_at"]) < dt.datetime.now(dt.timezone.utc):
        raise FixGuardError("REPORT_EXPIRED", "This report link has expired.")
    run = db.get_run(link["audit_id"])
    if not run:
        raise FixGuardError("REPORT_NOT_FOUND", "This report could not be found.")
    return run


@router.get("/badge/{token}.json")
async def badge_json(token: str) -> dict:
    """Data for the embedded badge. Public: the badge lives on public pages."""
    run = _run_for_token(token)
    return {
        "score": run.get("health_score"),
        "grade": run.get("grade"),
        "svg": report_render.badge_svg(run.get("health_score"), run.get("grade") or ""),
        "report_url": f"{config.PUBLIC_BASE_URL}/r/{token}",
        "checked_at": run.get("completed_at"),
    }


@router.get("/badge/{token}.svg")
async def badge_image(token: str) -> Response:
    run = _run_for_token(token)
    return Response(
        report_render.badge_svg(run.get("health_score"), run.get("grade") or ""),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/badge/{token}.js")
async def badge_embed(token: str) -> Response:
    _run_for_token(token)
    return Response(
        report_render.badge_script(token),
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )
