"""Error envelope and codes, per SRS section 8.3.

Every failure the API emits uses the same shape:

    {"error": {"code", "message", "audit_id", "retryable"}}
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# code -> (http status, retryable)
ERROR_CODES: dict[str, tuple[int, bool]] = {
    "INVALID_URL": (400, False),
    "UNREACHABLE_TARGET": (422, True),
    "RATE_LIMIT_EXCEEDED": (429, True),
    "AUDIT_NOT_FOUND": (404, False),
    "AUDIT_TIMEOUT": (504, True),
    "WORKER_CRASH": (500, True),
    "AI_AGENT_ERROR": (502, True),
    "AUTH_INVALID": (401, False),
    # Not signed in at all, as opposed to signed in with something wrong.
    # Same status, different code, because the dashboard reacts to them
    # differently: one shows the sign-in screen, the other an error.
    "AUTH_REQUIRED": (401, False),
    "CONSENT_REQUIRED": (400, False),
    "VALIDATION_ERROR": (400, False),
    "SESSION_INVALID": (422, False),
    "AUDIT_NOT_COMPLETE": (409, True),
    "REPORT_NOT_FOUND": (404, False),
    "REPORT_EXPIRED": (410, False),
    "INTERNAL_ERROR": (500, True),
    # Used where saying "you may not" would itself be information - the admin
    # console answers a non-admin exactly as it answers a stranger.
    "NOT_FOUND": (404, False),
}


class FixGuardError(Exception):
    """Raised anywhere in the app; rendered by the handler below."""

    def __init__(self, code: str, message: str, audit_id: str | None = None):
        self.code = code
        self.message = message
        self.audit_id = audit_id
        super().__init__(message)

    @property
    def status(self) -> int:
        return ERROR_CODES.get(self.code, (500, False))[0]

    @property
    def retryable(self) -> bool:
        return ERROR_CODES.get(self.code, (500, False))[1]


def envelope(
    code: str, message: str, audit_id: str | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "audit_id": audit_id,
            "retryable": ERROR_CODES.get(code, (500, False))[1],
        }
    }


def _count_error(code: str) -> None:
    """Tell the admin counters, without making errors depend on them.

    Imported inside the function because adminstats imports the database and
    this module is imported by nearly everything; a module-level import here
    would make the error envelope part of that cycle. A monitoring counter
    must never be able to turn an error into a different error, so a failure
    to count is swallowed.
    """
    try:
        from . import adminstats

        adminstats.requests.record_error(code)
    except Exception:
        pass


def register(app) -> None:
    """Attach handlers so even framework errors use the SRS envelope."""

    @app.exception_handler(FixGuardError)
    async def _fixguard(_: Request, exc: FixGuardError):
        # Counted here rather than in the request middleware, which sees only
        # a status code. Which code fired is the part an operator can act on:
        # a hundred UNREACHABLE_TARGETs is somebody typing addresses wrong, a
        # hundred WORKER_CRASHes is the browser falling over.
        _count_error(exc.code)
        return JSONResponse(
            status_code=exc.status,
            content=envelope(exc.code, exc.message, exc.audit_id),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        msg = str(first.get("msg", "Request validation failed"))
        msg = msg.replace("Value error, ", "")
        field = ".".join(str(p) for p in first.get("loc", ())[1:])
        if "i_own_this_site" in field:
            code = "CONSENT_REQUIRED"
        elif "domain_url" in field or "target_url" in field:
            code = "INVALID_URL"
        else:
            code = "VALIDATION_ERROR"
            msg = f"{field}: {msg}" if field else msg
        return JSONResponse(status_code=ERROR_CODES[code][0], content=envelope(code, msg))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {
            401: "AUTH_INVALID",
            404: "AUDIT_NOT_FOUND",
            409: "AUDIT_NOT_COMPLETE",
            410: "REPORT_EXPIRED",
            429: "RATE_LIMIT_EXCEEDED",
        }.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(code, str(exc.detail)),
        )
