"""Auditing behind a login, without ever handling a password.

The user signs in themselves and hands FixGuard the resulting session. That
choice is deliberate:

* FixGuard already refuses to submit any form containing a password field.
  Asking for credentials to log in would contradict its own safety model.
* A session is scoped, expiring and revocable. Logging out invalidates it.
  A password is none of those things.
* Nothing secret is ever written to the database. The audit record stores
  that a session was used and which cookie *names* were sent, never a value.

Being logged in also changes what crawling means. On a public page every link
is safe to follow. Behind a login, `/logout` ends the audit and
`/invoices/42/delete` destroys someone's data. So an authenticated crawl is
deliberately more timid than an anonymous one.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Paths that end the session. Following one mid-crawl silently turns the rest
# of the audit into a tour of the login page.
SESSION_ENDING = re.compile(
    r"/(logout|log-out|signout|sign-out|disconnect|leave)\b"
    r"|[?&](action|do)=(logout|signout)\b",
    re.I,
)

# Links that change or destroy state. A crawler must never follow these, and
# plenty of applications still expose them as plain GET links.
DESTRUCTIVE = re.compile(
    r"/(delete|remove|destroy|revoke|cancel|deactivate|close-account|"
    r"unsubscribe|reset|wipe|purge|archive|trash|refund|terminate)\b"
    r"|[?&](action|do|op|cmd)=(delete|remove|destroy|cancel|revoke|reset)\b"
    r"|/(pay|checkout|charge|billing/confirm|orders?/\d+/(cancel|refund))\b",
    re.I,
)

# Pages that mean the session is gone.
LOGIN_PAGE = re.compile(
    r"/(login|signin|sign-in|auth|session/new|account/login)\b", re.I
)

COOKIE_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$")


class AuthError(ValueError):
    """The supplied session could not be used."""


# Every shape a browser will hand a user when they copy a request.
# Named backreferences throughout: a numbered one shifts as soon as a named
# group is added earlier in the pattern, which silently matched the wrong
# quote and truncated the cookie string.
_CURL_COOKIE = re.compile(
    r"""-H\s+(?P<q1>['"])\s*cookie\s*:\s*(?P<v>.*?)(?P=q1)"""
    r"""|-H\s+\^?["']cookie:\s*(?P<v2>[^"'^]*)"""
    r"""|(?:^|\s)-b\s+(?P<q3>['"])(?P<v3>.*?)(?P=q3)""",
    re.I | re.S,
)
_CURL_AUTH = re.compile(
    r"""-H\s+(?P<q>['"])\s*authorization\s*:\s*(?P<v>.*?)(?P=q)""", re.I | re.S
)
_HEADER_LINE = re.compile(r"^\s*cookie\s*:\s*(?P<v>.+)$", re.I | re.M)
_AUTH_LINE = re.compile(r"^\s*authorization\s*:\s*(?P<v>.+)$", re.I | re.M)


def extract_session(raw: str) -> tuple[str, str | None]:
    """Pull the cookie string, and any bearer token, out of whatever was pasted.

    A person signed into their own site can reach three things in about two
    clicks: "Copy as cURL" on a request, the raw request-headers block, or the
    cookie string itself. Asking which one they have is a question they should
    not have to answer, so all three are accepted.
    """
    text = (raw or "").strip()
    if not text:
        raise AuthError("Nothing was pasted.")

    auth_header: str | None = None

    # 1. A copied cURL command.
    if "curl " in text[:400].lower() or " -H " in text or " -b " in text:
        m = _CURL_COOKIE.search(text)
        if m:
            cookie_str = m.group("v") or m.group("v2") or m.group("v3") or ""
            a = _CURL_AUTH.search(text)
            if a:
                auth_header = a.group("v").strip()
            if cookie_str.strip():
                return cookie_str.strip(), auth_header

    # 2. A block of request headers.
    m = _HEADER_LINE.search(text)
    if m:
        a = _AUTH_LINE.search(text)
        if a:
            auth_header = a.group("v").strip()
        return m.group("v").strip(), auth_header

    # 3. The cookie string on its own.
    if "=" in text and "\n" not in text.strip():
        return text, None
    if "=" in text:
        # Multi-line paste with no Cookie: label - take the line that looks most
        # like cookies rather than failing on the surrounding noise.
        best = max(
            (ln for ln in text.splitlines() if "=" in ln),
            key=lambda ln: ln.count("="),
            default="",
        )
        if best.strip():
            return best.strip(), None

    raise AuthError(
        "Could not find any cookies in that. Paste either the whole "
        "\u201cCopy as cURL\u201d command, or the line starting with "
        "\u201cCookie:\u201d."
    )


def extract_auth_header(raw: str) -> str | None:
    """Any Authorization header in the paste, found independently of cookies.

    Looked for on its own rather than alongside the cookie search, because a
    single-page app talking to an API on another subdomain often sends *only*
    a bearer token. Folding this into the cookie path meant a token-only paste
    was reported as "no cookies found", which is the one case this feature is
    most needed for.
    """
    text = (raw or "").strip()
    if not text:
        return None
    for pattern in (_CURL_AUTH, _AUTH_LINE):
        m = pattern.search(text)
        if m:
            value = m.group("v").strip().strip("'\"^")
            if value:
                return value[:4000]
    return None


def parse_paste(raw: str, target_url: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Cookies and any bearer token found in the same paste.

    Either alone is a usable session; only finding neither is an error.
    """
    headers: dict[str, str] = {}
    token = extract_auth_header(raw)
    if token:
        headers["Authorization"] = token

    try:
        cookies = parse_cookie_header(raw, target_url)
    except AuthError:
        if not headers:
            raise AuthError(
                "No session was found in that. Copy the request again while "
                "signed in - FixGuard needs either its cookies or its "
                "Authorization header."
            )
        cookies = []
    return cookies, headers


def parse_cookie_header(raw: str, target_url: str) -> list[dict[str, Any]]:
    """Turn whatever the user pasted into Playwright cookie objects."""
    host = urlparse(target_url).hostname
    if not host:
        raise AuthError("The target URL has no host, so cookies cannot be scoped.")

    cookie_str, _ = extract_session(raw)

    cookies: list[dict[str, Any]] = []
    skipped = 0
    for part in cookie_str.replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            if part:
                skipped += 1
            continue
        name, _, value = part.partition("=")
        name, value = name.strip(), value.strip().strip('"')
        if not COOKIE_NAME.match(name):
            skipped += 1
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": host,
                "path": "/",
                "httpOnly": False,
                "secure": urlparse(target_url).scheme == "https",
                "sameSite": "Lax",
            }
        )

    if not cookies:
        raise AuthError(
            "No usable cookies were found in that. Make sure you copied the "
            "request while signed in."
        )
    if len(cookies) > 60:
        raise AuthError(
            f"That contained {len(cookies)} cookies, which is more than any "
            "session needs. Paste a single request rather than a whole page."
        )
    return cookies


def redact(cookies: list[dict[str, Any]] | None, headers: dict[str, str] | None) -> dict:
    """What is safe to store about a session: shape, never content."""
    return {
        "authenticated": bool(cookies or headers),
        "cookie_names": sorted({c["name"] for c in (cookies or [])}),
        "header_names": sorted(headers.keys()) if headers else [],
    }


def is_safe_to_follow(url: str, authenticated: bool) -> tuple[bool, str | None]:
    """Whether a crawler may open this link.

    Anonymously, the only real risk is wasting time. Authenticated, a GET can
    delete a record or end the session, so the same link is refused.
    """
    if SESSION_ENDING.search(url):
        return False, "signs the session out"
    if not authenticated:
        return True, None
    if DESTRUCTIVE.search(url):
        return False, "looks like it changes or deletes data"
    return True, None


def looks_like_login_page(url: str, title: str = "", body_text: str = "") -> bool:
    """Detect that we have been bounced back to a sign-in screen."""
    if LOGIN_PAGE.search(url):
        return True
    haystack = f"{title} {body_text[:600]}".lower()
    signals = ("sign in", "log in", "login", "password")
    hits = sum(1 for s in signals if s in haystack)
    return hits >= 2


def verify(
    url: str, title: str, body_text: str, expect: str | None
) -> tuple[bool, str]:
    """Confirm the session actually worked before crawling anything.

    An expired cookie does not error - it silently returns the login page, and
    without this check the audit would cheerfully report that the login screen
    is in excellent health.
    """
    if expect:
        if expect.lower() in (body_text or "").lower():
            return True, f"Found {expect!r} on the page, so the session is active."
        return False, (
            f"Could not find {expect!r} on the page after loading it with your "
            "session. The session has probably expired."
        )

    if looks_like_login_page(url, title, body_text):
        return False, (
            "The target still shows a sign-in page with your session applied, "
            "so the session is not being accepted. Copy a fresh one."
        )
    return True, "The target did not redirect to a sign-in page."
