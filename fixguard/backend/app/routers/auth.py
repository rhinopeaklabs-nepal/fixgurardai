"""Sign up, sign in, sign out.

The session travels in an httpOnly cookie rather than a token the dashboard
stores itself. localStorage is readable by any script that ends up on the
page, and this is a tool whose whole job is telling people which third-party
scripts their site loads - shipping a design where one stray script can lift
a session would be hard to defend.

Because the dashboard and the API are served from the same origin, the cookie
needs no cross-site relaxation: SameSite stays Lax, and nothing here has to
be widened for the browser to send it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from .. import accounts, config
from ..errors import FixGuardError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

COOKIE = "fixguard_session"


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=512)
    name: str | None = Field(default=None, max_length=80)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=512)


def _secure_cookies() -> bool:
    """Only mark the cookie Secure when the site is actually on https.

    Setting it unconditionally would silently break local development over
    http, where the browser simply declines to store it and every request
    then looks signed-out for no visible reason.
    """
    return str(config.PUBLIC_BASE_URL or "").startswith("https://")


def _cookie_kwargs() -> dict:
    """Shared by the set and the delete, so a session can always be cleared.

    A cookie set with a Domain can only be removed by a delete carrying the
    same Domain. Building both from one place is what stops sign-out silently
    leaving the cookie in place on a subdomain deployment.
    """
    kw = {"path": "/"}
    if config.SESSION_COOKIE_DOMAIN:
        kw["domain"] = config.SESSION_COOKIE_DOMAIN
    return kw


def _issue(response: Response, user_id: str) -> None:
    token, expires = accounts.start_session(user_id)
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=_secure_cookies(),
        # Lax is enough even with the dashboard and the API on different
        # subdomains: they share a registrable domain, so a call between them
        # is same-site. None would be needed only for genuinely cross-site.
        samesite="lax",
        max_age=accounts.SESSION_DAYS * 24 * 3600,
        **_cookie_kwargs(),
    )


def current_user(request: Request) -> dict | None:
    """The signed-in user, or None. Never raises - callers decide."""
    return accounts.resolve_session(request.cookies.get(COOKIE))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise FixGuardError("AUTH_REQUIRED", "Sign in to use this.")
    return user


# --------------------------------------------------------------------------
@router.post("/signup", status_code=201)
async def signup(payload: SignupRequest, response: Response) -> dict:
    try:
        user = accounts.create_user(payload.email, payload.password, payload.name)
    except accounts.AccountError as exc:
        raise FixGuardError("VALIDATION_ERROR", str(exc)) from exc
    _issue(response, user["id"])
    return {"user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@router.post("/login")
async def login(payload: LoginRequest, response: Response) -> dict:
    try:
        user = accounts.authenticate(payload.email, payload.password)
    except accounts.AccountError as exc:
        # Deliberately not 404-vs-401: the message and the status are the same
        # whether the email is unknown or the password is wrong.
        raise FixGuardError("AUTH_INVALID", str(exc)) from exc
    _issue(response, user["id"])
    return {"user": user}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    accounts.end_session(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, **_cookie_kwargs())
    return {"signed_out": True}


@router.get("/me")
async def me(user: dict | None = Depends(current_user)) -> dict:
    """Who is signed in, if anyone.

    Answers 200 with a null user rather than 401, because the dashboard calls
    this on every load to decide which screen to draw. A 401 here would be a
    normal, expected state reported as an error, and the console noise would
    train everyone to ignore real ones.
    """
    return {"user": user}
