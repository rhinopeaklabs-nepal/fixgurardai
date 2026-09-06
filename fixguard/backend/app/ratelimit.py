"""Rate limiting: 10 audit starts per API key per hour (SRS 5.4 / 8.1).

Backed by SQLite rather than Redis. At this volume a bounded table scan is
cheaper than running another daemon on a 1 vCPU box.

Two behaviours beyond a plain counter:

* **Refunds.** An audit that dies immediately because the host does not resolve
  cost a DNS lookup, not a browser. Charging a slot for it means a handful of
  typos locks you out for an hour, which is punishing the user for the tool's
  own cheapest failure path.
* **Visible remaining quota**, so the limit is something you can see coming
  rather than discover at the moment you are blocked.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from . import config
from .db import get_conn


def key_hash(api_key: str) -> str:
    """Never store the raw key, even locally."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:32]


def _window_rows(conn, kh: str, now: dt.datetime):
    window_start = now - dt.timedelta(hours=1)
    return conn.execute(
        "SELECT id, occurred_at FROM rate_events "
        "WHERE key_hash = ? AND occurred_at >= ? ORDER BY occurred_at",
        (kh, window_start.isoformat()),
    ).fetchall()


def check_and_record(api_key: str) -> tuple[bool, int, dict | None]:
    """Return (allowed, remaining, retry_info).

    ``retry_info`` carries both a machine-readable ``seconds`` and an
    ``at`` timestamp so callers can phrase the wait however they like.
    """
    now = dt.datetime.now(dt.timezone.utc)
    kh = key_hash(api_key)

    with get_conn() as conn:
        conn.execute(
            "DELETE FROM rate_events WHERE occurred_at < ?",
            ((now - dt.timedelta(hours=24)).isoformat(),),
        )
        rows = _window_rows(conn, kh, now)

        if len(rows) >= config.RATE_LIMIT_PER_HOUR:
            oldest = dt.datetime.fromisoformat(rows[0]["occurred_at"])
            free_at = oldest + dt.timedelta(hours=1)
            return False, 0, {
                "seconds": max(1, int((free_at - now).total_seconds())),
                "at": free_at.isoformat(),
            }

        conn.execute(
            "INSERT INTO rate_events (key_hash, occurred_at) VALUES (?, ?)",
            (kh, now.isoformat()),
        )

    return True, config.RATE_LIMIT_PER_HOUR - len(rows) - 1, None


def quota(api_key: str) -> dict:
    """Current usage, for showing the limit before it is reached."""
    now = dt.datetime.now(dt.timezone.utc)
    with get_conn() as conn:
        rows = _window_rows(conn, key_hash(api_key), now)

    used = len(rows)
    resets_at = None
    if rows:
        oldest = dt.datetime.fromisoformat(rows[0]["occurred_at"])
        resets_at = (oldest + dt.timedelta(hours=1)).isoformat()

    return {
        "limit": config.RATE_LIMIT_PER_HOUR,
        "used": used,
        "remaining": max(0, config.RATE_LIMIT_PER_HOUR - used),
        "window": "1 hour",
        "resets_at": resets_at,
    }


def refund(api_key: str) -> None:
    """Give back the most recent slot.

    Called when an audit fails before doing meaningful work, so a mistyped
    address does not cost the same as a full browser run.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM rate_events WHERE key_hash = ? "
            "ORDER BY occurred_at DESC LIMIT 1",
            (key_hash(api_key),),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM rate_events WHERE id = ?", (row["id"],))


def describe_wait(seconds: int) -> str:
    """A wait a person can act on, rather than an ISO timestamp."""
    if seconds < 60:
        return "in under a minute"
    minutes = round(seconds / 60)
    if minutes == 1:
        return "in about a minute"
    if minutes < 60:
        return f"in about {minutes} minutes"
    hours = seconds / 3600
    return "in about an hour" if hours < 1.5 else f"in about {round(hours)} hours"
