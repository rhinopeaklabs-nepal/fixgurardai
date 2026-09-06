"""Accounts and sessions for the FixGuard dashboard.

Deliberately small. The whole safety argument for this tool is that it never
asks anyone for a password to a site it audits, so its own sign-in has to be
the kind of thing that argument survives: no third-party identity provider
holding the list of who audits what, no password reset mail it cannot send,
and nothing stored that would be worth stealing.

Two decisions worth stating, because both could reasonably have gone the
other way:

* **scrypt from the standard library**, not bcrypt or argon2. Those are
  better in the abstract, and both are another wheel to build on a 1 vCPU
  box. scrypt with sane parameters is not the weak link here, and a
  dependency that fails to compile at deploy time is a real cost against a
  theoretical gain.
* **Opaque session tokens in the database**, not signed JWTs. A JWT cannot
  be revoked without keeping a list of the revoked ones, at which point the
  database round-trip it was meant to avoid is back. Signing out should
  actually end the session, and here it does: the row is deleted.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import secrets
import sqlite3
import uuid

from .db import get_conn

# scrypt parameters. n=2**14 keeps a single hash near 60-100ms on one vCPU:
# slow enough that guessing is expensive, fast enough that signing in does
# not feel broken while an audit is using the same core.
_N, _R, _P = 2**14, 8, 1
_SALT_BYTES = 16
_KEY_BYTES = 32

SESSION_DAYS = 30
MIN_PASSWORD = 10

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")


class AccountError(ValueError):
    """Something the person signing in can fix, and should be told about."""


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_BYTES
    )
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check that also survives a malformed stored value."""
    try:
        scheme, n, r, p, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        key = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p),
            dklen=len(key_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(key.hex(), key_hex)


# ---------------------------------------------------------------- validation
def normalise_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise AccountError("That does not look like an email address.")
    return email


def check_password_strength(password: str) -> None:
    """Length only, on purpose.

    Composition rules - one digit, one symbol, one capital - push people
    towards Password1! and away from a long passphrase, which is the stronger
    of the two. Length is the requirement that actually correlates with
    strength.
    """
    if len(password or "") < MIN_PASSWORD:
        raise AccountError(
            f"Use at least {MIN_PASSWORD} characters. A few ordinary words in "
            "a row is stronger than one short word with symbols in it."
        )
    if len(password) > 512:
        raise AccountError("That password is longer than 512 characters.")


# ---------------------------------------------------------------- users
def create_user(email: str, password: str, name: str | None = None) -> dict:
    email = normalise_email(email)
    check_password_strength(password)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    user_id = f"u_{uuid.uuid4().hex[:16]}"
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (id, email, name, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    email,
                    (name or "").strip()[:80] or None,
                    hash_password(password),
                    now,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise AccountError("An account with that email already exists.") from exc
    return {"id": user_id, "email": email, "name": name, "created_at": now}


def authenticate(email: str, password: str) -> dict:
    """Return the user, or raise the same error whichever half was wrong.

    Saying "no account with that email" tells an attacker which addresses are
    registered, which is worth more to them than it is to the person who
    mistyped their own email.
    """
    try:
        email = normalise_email(email)
    except AccountError:
        raise AccountError("That email and password do not match an account.")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, name, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        raise AccountError("That email and password do not match an account.")
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


def get_user(user_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def count_users() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


# ---------------------------------------------------------------- sessions
def _token_hash(token: str) -> str:
    """Sessions are stored hashed for the same reason passwords are.

    A stolen copy of the database should not hand over live sessions along
    with everything else in it.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(user_id: str) -> tuple[str, dt.datetime]:
    token = secrets.token_urlsafe(32)
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(days=SESSION_DAYS)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (_token_hash(token), user_id, now.isoformat(), expires.isoformat()),
        )
    return token, expires


def resolve_session(token: str | None) -> dict | None:
    """The user this token belongs to, or None. Expired rows are cleaned up."""
    if not token:
        return None
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT s.user_id, s.expires_at, u.email, u.name "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ?",
            (_token_hash(token),),
        ).fetchone()
        if not row:
            return None
        if row["expires_at"] <= now:
            conn.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),)
            )
            return None
    return {"id": row["user_id"], "email": row["email"], "name": row["name"]}


def end_session(token: str | None) -> None:
    if not token:
        return
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),)
        )


def purge_expired_sessions() -> int:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        return cur.rowcount or 0
