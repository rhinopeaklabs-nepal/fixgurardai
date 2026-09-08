"""The admin console's data.

Every route here is behind a signed-in account whose email is in the
deployment's ADMIN_EMAILS. Two things that would each be an easy shortcut are
deliberately not done:

* **The API key does not open this.** identity() elsewhere accepts either a
  session or the service key, because a script running audits is a legitimate
  caller. Administration is not something a shared key spread across CI logs
  and acceptance suites should be able to do, so this gate takes a session
  and nothing else.
* **Nothing here writes.** The console reports; it does not suspend accounts,
  delete other people's audits or hand out admin. A read-only console is a
  much smaller thing to get wrong, and every write it might offer already has
  a safer home - promotion in the environment, deletion in the account that
  owns the data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from .. import adminstats, config, metrics
from ..audit import runner
from ..errors import FixGuardError
from . import auth

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_admin(request: Request) -> dict:
    """A session belonging to a listed administrator.

    The unauthenticated case and the signed-in-but-not-admin case answer the
    same way on purpose. Telling a curious signed-in user that this endpoint
    exists but is not theirs is a map of what to attack next; from outside,
    the console should be indistinguishable from a route that is not there.
    """
    user = auth.current_user(request)
    if not user or not user.get("is_admin"):
        raise FixGuardError("NOT_FOUND", "Not found.")
    # Recorded before the handler runs, and deduplicated inside, so a console
    # left open all afternoon leaves one row rather than a thousand. A read-
    # only console still shows real customers' addresses; who looked at that
    # should not rest on everyone remembering that they did.
    try:
        adminstats.log_admin_access(
            user,
            request.url.path,
            (request.headers.get("x-real-ip") or "").strip() or None,
        )
    except Exception:  # noqa: BLE001
        # Never let the audit trail's own failure lock an operator out of the
        # console during the incident they opened it for.
        pass
    return user


@router.get("/overview")
async def overview(
    days: int = Query(30, ge=1, le=365),
    _: dict = Depends(require_admin),
) -> dict:
    """One call for the whole console, so its panels cannot disagree.

    Fetching each panel separately would mean six queries against a moving
    database and a screen where the totals do not add up - which on a
    monitoring page reads as a bug in the thing being monitored.
    """
    return {
        "audits": adminstats.audit_overview(days),
        "live": runner.snapshot(),
        "stuck": adminstats.stuck_runs(),
        "process": adminstats.process_stats(),
        "database": adminstats.database_stats(),
        "requests": adminstats.requests.snapshot(),
        # Latency and availability from the persisted rollups, which unlike
        # the in-memory counters above survive a deploy.
        "traffic": metrics.summary(24),
        "admin_access": adminstats.recent_admin_access(10),
        "quota_pressure": adminstats.quota_pressure(),
        "admin_emails_configured": len(config.ADMIN_EMAILS),
    }


@router.get("/users")
async def users(
    limit: int = Query(200, ge=1, le=1000),
    _: dict = Depends(require_admin),
) -> dict:
    return {"users": adminstats.users_table(limit)}


@router.get("/audits")
async def all_audits(
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, pattern="^(queued|running|complete|failed)$"),
    _: dict = Depends(require_admin),
) -> dict:
    """Every account's runs, which is the one thing the normal list refuses.

    Addresses people audited are visible here. That is the unavoidable cost
    of an operator being able to see why a run failed, and it is the reason
    the list of who can do this lives in the environment rather than in a
    table anyone can write to.
    """
    return {"audits": adminstats.recent_audits(limit, status)}
