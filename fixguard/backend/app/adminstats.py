"""Measurements behind the admin console.

Everything here is read from something that already exists: the SQLite file,
this process, and the cgroup the container runs in. Nothing is sampled on a
timer and nothing is estimated, because a monitoring page that quietly
interpolates is worse than no monitoring page - it is the one screen whose
whole value is that you can believe it.

Three things are therefore deliberately absent, and the console says so
rather than drawing an empty chart:

* Host CPU and host memory. A container can read the host's /proc/stat and
  it would look authoritative, but it describes the whole VPS - four other
  applications included - not FixGuard.
* Request latency percentiles. Nothing records per-request timings, and
  inventing them from the audit durations would be measuring something else.
* Anything before this process started. The counters below reset on deploy
  and are labelled with the moment they started counting.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import time
from typing import Any

from . import accounts, config
from .db import get_conn

STARTED_AT = dt.datetime.now(dt.timezone.utc)
_STARTED_MONOTONIC = time.monotonic()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(d: dt.datetime) -> str:
    return d.isoformat()


# ------------------------------------------------------------------ counters
class RequestCounter:
    """What this process has served since it started.

    In memory on purpose. Persisting it would mean a write on every request
    to a SQLite file that a running audit is already contending for, to
    answer a question nobody asks about last week.
    """

    def __init__(self) -> None:
        self.total = 0
        self.by_status: dict[str, int] = {}
        self.errors_by_code: dict[str, int] = {}
        self.slowest_ms = 0.0
        self.slowest_path = ""

    def record(self, path: str, status: int, ms: float) -> None:
        self.total += 1
        bucket = f"{status // 100}xx"
        self.by_status[bucket] = self.by_status.get(bucket, 0) + 1
        if ms > self.slowest_ms:
            self.slowest_ms = ms
            self.slowest_path = path

    def record_error(self, code: str) -> None:
        self.errors_by_code[code] = self.errors_by_code.get(code, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_status": dict(sorted(self.by_status.items())),
            "errors_by_code": dict(
                sorted(self.errors_by_code.items(), key=lambda kv: -kv[1])[:10]
            ),
            "slowest_ms": round(self.slowest_ms),
            "slowest_path": self.slowest_path,
            "counting_since": _iso(STARTED_AT),
        }


requests = RequestCounter()


# ------------------------------------------------------------------- process
def _read_int(path: str) -> int | None:
    try:
        with open(path) as fh:
            value = fh.read().strip()
        return int(value)
    except (OSError, ValueError):
        return None


def _rss_bytes() -> int | None:
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return None


def process_stats() -> dict[str, Any]:
    """This container, not the host it shares."""
    data_dir = str(config.DATA_DIR)
    try:
        usage = shutil.disk_usage(data_dir)
        disk = {
            "total_bytes": usage.total,
            "free_bytes": usage.free,
            "used_percent": round((usage.total - usage.free) / usage.total * 100, 1),
        }
    except OSError:
        disk = None

    # cgroup v2 first; v1 is the fallback for older hosts. A cgroup with no
    # limit reports the literal string "max", which is not a number and must
    # not become one.
    limit = _read_int("/sys/fs/cgroup/memory.max")
    current = _read_int("/sys/fs/cgroup/memory.current")
    if current is None:
        current = _read_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")
        limit = _read_int("/sys/fs/cgroup/memory/memory.limit_in_bytes")

    return {
        "started_at": _iso(STARTED_AT),
        "uptime_seconds": round(time.monotonic() - _STARTED_MONOTONIC),
        "python": sys.version.split()[0],
        "pid": os.getpid(),
        "rss_bytes": _rss_bytes(),
        "container_memory_bytes": current,
        "container_memory_limit_bytes": limit,
        "disk": disk,
        "max_concurrent_audits": config.MAX_CONCURRENT_AUDITS,
        "rate_limit_per_hour": config.RATE_LIMIT_PER_HOUR,
        "llm_provider": config.LLM_PROVIDER,
    }


def database_stats() -> dict[str, Any]:
    path = str(config.DB_PATH)
    sizes = {}
    for label, suffix in (("db", ""), ("wal", "-wal"), ("shm", "-shm")):
        try:
            sizes[label + "_bytes"] = os.path.getsize(path + suffix)
        except OSError:
            sizes[label + "_bytes"] = 0
    with get_conn() as conn:
        tables = {}
        for name in (
            "audit_runs", "users", "sessions", "share_links",
            "surgical_prompts", "agent_calls", "geo_ping_results", "rate_events",
        ):
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()
            tables[name] = row["n"]
    return {**sizes, "rows": tables}


# --------------------------------------------------------------------- audits
def _pct(values: list[int], p: float) -> int | None:
    """Nearest-rank percentile. Exact on the list given, no interpolation."""
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, round(p / 100 * len(ordered)) - 1))
    return ordered[idx]


def audit_overview(days: int = 30) -> dict[str, Any]:
    since = _iso(_now() - dt.timedelta(days=days))
    with get_conn() as conn:
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM audit_runs GROUP BY status"
            )
        }
        by_grade = {
            (r["grade"] or "not_assessed"): r["n"]
            for r in conn.execute(
                "SELECT grade, COUNT(*) AS n FROM audit_runs "
                "WHERE status = 'complete' GROUP BY grade"
            )
        }
        failures = [
            {"code": r["error_code"] or "unknown", "count": r["n"],
             "retryable": bool(r["retryable"])}
            for r in conn.execute(
                "SELECT error_code, retryable, COUNT(*) AS n FROM audit_runs "
                "WHERE status = 'failed' AND created_at >= ? "
                "GROUP BY error_code, retryable ORDER BY n DESC LIMIT 12",
                (since,),
            )
        ]
        durations = [
            r["duration_ms"]
            for r in conn.execute(
                "SELECT duration_ms FROM audit_runs "
                "WHERE status = 'complete' AND duration_ms > 0 AND created_at >= ?",
                (since,),
            )
        ]
        scores = [
            r["health_score"]
            for r in conn.execute(
                "SELECT health_score FROM audit_runs "
                "WHERE status = 'complete' AND health_score IS NOT NULL "
                "AND created_at >= ?",
                (since,),
            )
        ]
        daily = [
            {"day": r["day"], "total": r["n"], "failed": r["failed"]}
            for r in conn.execute(
                "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n, "
                "SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed "
                "FROM audit_runs WHERE created_at >= ? "
                "GROUP BY day ORDER BY day",
                (since,),
            )
        ]

    complete = by_status.get("complete", 0)
    failed = by_status.get("failed", 0)
    finished = complete + failed
    return {
        "window_days": days,
        "by_status": by_status,
        "by_grade": by_grade,
        "failures": failures,
        # A success rate over runs that have finished. Counting the queued
        # ones as failures would make every busy moment look like an outage.
        "success_rate": round(complete / finished * 100, 1) if finished else None,
        "duration_ms": {
            "samples": len(durations),
            "p50": _pct(durations, 50),
            "p90": _pct(durations, 90),
            "p99": _pct(durations, 99),
            "max": max(durations) if durations else None,
        },
        "health_score": {
            "samples": len(scores),
            "median": _pct(scores, 50),
            "worst": min(scores) if scores else None,
        },
        "daily": daily,
    }


def stuck_runs(minutes: int = 20) -> list[dict[str, Any]]:
    """Runs still claiming to be in flight long after any audit could be.

    A run only leaves queued/running when its task writes the ending, so a
    process that is killed mid-audit - every deploy - leaves rows that look
    live forever. reconcile_orphans() closes those on boot; this catches the
    ones a still-running process has genuinely lost.
    """
    cutoff = _iso(_now() - dt.timedelta(minutes=minutes))
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, target_url, status, stage, progress_percent, "
                "created_at, owner_id FROM audit_runs "
                "WHERE status IN ('queued', 'running') AND created_at < ? "
                "ORDER BY created_at",
                (cutoff,),
            )
        ]


def reconcile_orphans() -> int:
    """Close runs left in flight by a process that is no longer alive.

    Called once at startup, before anything can serve. Their task died with
    the previous process, so nothing will ever finish them; leaving them is
    how a dashboard ends up showing a spinner that never resolves.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE audit_runs SET status = 'failed', error_code = 'RUN_INTERRUPTED', "
            "error_detail = 'The server restarted while this audit was running. "
            "Nothing was left behind on the audited site.', retryable = 1, "
            "completed_at = ? WHERE status IN ('queued', 'running')",
            (_iso(_now()),),
        )
        return cur.rowcount


# ---------------------------------------------------------------------- users
def users_table(limit: int = 200) -> list[dict[str, Any]]:
    """Accounts with what each has actually done.

    No password hash and no session token leaves this function - not because
    they would be displayed, but because the safest place for them is a query
    that never selects them.
    """
    with get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT u.id, u.email, u.name, u.created_at, "
                "  (SELECT COUNT(*) FROM audit_runs a WHERE a.owner_id = u.id) "
                "    AS audits, "
                "  (SELECT COUNT(*) FROM audit_runs a WHERE a.owner_id = u.id "
                "    AND a.status = 'failed') AS failed, "
                "  (SELECT MAX(a.created_at) FROM audit_runs a "
                "    WHERE a.owner_id = u.id) AS last_audit_at, "
                "  (SELECT COUNT(*) FROM sessions s WHERE s.user_id = u.id "
                "    AND s.expires_at > ?) AS active_sessions "
                "FROM users u ORDER BY u.created_at DESC LIMIT ?",
                (_iso(_now()), limit),
            )
        ]
    # Derived rather than selected: there is no admin column, so this is the
    # same answer the session gate gives, computed from the same list.
    for r in rows:
        r["is_admin"] = accounts.is_admin(r["email"])
    return rows


def quota_pressure() -> list[dict[str, Any]]:
    """Who is close to the hourly limit right now.

    Keys are stored hashed, so this reports the shape of the load without
    naming anyone: it answers "is the limit biting" rather than "who".
    """
    since = _iso(_now() - dt.timedelta(hours=1))
    with get_conn() as conn:
        return [
            {"key_hash": r["key_hash"][:8], "used": r["n"],
             "limit": config.RATE_LIMIT_PER_HOUR}
            for r in conn.execute(
                "SELECT key_hash, COUNT(*) AS n FROM rate_events "
                "WHERE occurred_at >= ? GROUP BY key_hash "
                "HAVING n > 0 ORDER BY n DESC LIMIT 10",
                (since,),
            )
        ]


def recent_audits(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    """Runs across every account, with the owner's email resolved.

    A LEFT JOIN, not an inner one: audits made before accounts existed have no
    owner, and dropping them from the operator's view would hide exactly the
    rows most likely to be confusing.
    """
    clause = "WHERE a.status = ?" if status else ""
    params: tuple = (status, limit) if status else (limit,)
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT a.id, a.target_url, a.status, a.grade, a.health_score, "
                "a.error_code, a.duration_ms, a.pages_audited, a.created_at, "
                "a.owner_id, u.email AS owner_email "
                "FROM audit_runs a LEFT JOIN users u ON u.id = a.owner_id "
                f"{clause} ORDER BY a.created_at DESC LIMIT ?",
                params,
            )
        ]


# ------------------------------------------------------------- access record
ACCESS_DEDUPE_MINUTES = 5


def log_admin_access(user: dict, path: str, ip: str | None) -> None:
    """Record that an administrator looked, without recording every poll.

    The console refreshes itself every fifteen seconds, so writing a row per
    request would produce thousands of entries a day that all say the same
    thing and bury the one that matters. A session already seen within the
    last few minutes is not written again, which keeps the table an answer to
    "who opened this, and when" rather than a request log.
    """
    now = _now()
    cutoff = _iso(now - dt.timedelta(minutes=ACCESS_DEDUPE_MINUTES))
    with get_conn() as conn:
        recent = conn.execute(
            "SELECT 1 FROM admin_access WHERE user_id = ? AND at >= ? LIMIT 1",
            (user["id"], cutoff),
        ).fetchone()
        if recent:
            return
        conn.execute(
            "INSERT INTO admin_access (user_id, email, path, ip, at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user["id"], user["email"], path, ip, _iso(now)),
        )


def recent_admin_access(limit: int = 25) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT email, path, ip, at FROM admin_access "
                "ORDER BY at DESC LIMIT ?",
                (limit,),
            )
        ]
