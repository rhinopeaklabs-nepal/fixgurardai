"""Request metrics that survive a deploy.

The admin console used to say, honestly, that it could not show latency
percentiles or anything from before the current process, because the only
counters were in memory. This is the part that fixes both, without turning
every request into a disk write.

How it works: each request updates an in-memory aggregate keyed by minute,
route template and status class. A background task flushes those aggregates
into SQLite every FLUSH_SECONDS and on shutdown. Nothing is sampled, and no
request waits on a write.

Two deliberate imprecisions, both stated wherever the numbers are read:

* **Latency is bucketed.** Percentiles cannot be averaged across minutes, and
  keeping every duration to compute them exactly would cost more than the
  answer is worth on this box. So durations land in fixed buckets and a
  percentile is reported as the upper bound of the bucket that contains it -
  "at or under 250ms", never a precise-looking 237ms that was invented.
* **The route, not the URL.** /api/v1/audits/{audit_id} rather than the
  thousand real ids, because a metrics table with one row per audit id is a
  second copy of the audit table wearing a disguise.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any

from .db import get_conn

# Upper bounds in milliseconds. The last bucket is everything above the one
# before it. Chosen around what this service actually does: most calls are a
# database read in single digits, a report render is tens, and anything past
# a second is a browser being driven.
BUCKETS_MS: list[float] = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
OVERFLOW = "over"

FLUSH_SECONDS = 30
RETAIN_DAYS = 30

# {(minute, route, status_class): {"count", "sum_ms", "max_ms", "buckets"}}
_pending: dict[tuple[str, str, str], dict[str, Any]] = {}
_lock = asyncio.Lock()


def _minute(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M")


def bucket_index(ms: float) -> int:
    """Which bucket a duration belongs in. The last index is the overflow."""
    for i, bound in enumerate(BUCKETS_MS):
        if ms <= bound:
            return i
    return len(BUCKETS_MS)


def record(route: str, status: int, ms: float) -> None:
    """Called from the request middleware. Never touches the disk.

    No lock: this runs on the event loop thread and does no awaiting, so it
    cannot interleave with itself. The flush does take the lock, because it
    awaits between reading the aggregates and clearing them.
    """
    key = (_minute(dt.datetime.now(dt.timezone.utc)), route, f"{status // 100}xx")
    slot = _pending.get(key)
    if slot is None:
        slot = {
            "count": 0,
            "sum_ms": 0.0,
            "max_ms": 0.0,
            "buckets": [0] * (len(BUCKETS_MS) + 1),
        }
        _pending[key] = slot
    slot["count"] += 1
    slot["sum_ms"] += ms
    slot["max_ms"] = max(slot["max_ms"], ms)
    slot["buckets"][bucket_index(ms)] += 1


async def flush() -> int:
    """Write the aggregates out and start fresh. Returns rows written.

    Rows are merged rather than replaced, because a minute can be flushed
    twice - once mid-minute by the timer and again when it ends - and the
    second write must add to the first, not overwrite it.
    """
    async with _lock:
        batch = _pending.copy()
        _pending.clear()
    if not batch:
        return 0

    cutoff = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RETAIN_DAYS)
    ).strftime("%Y-%m-%dT%H:%M")

    with get_conn() as conn:
        for (minute, route, klass), slot in batch.items():
            row = conn.execute(
                "SELECT count, sum_ms, max_ms, buckets FROM request_metrics "
                "WHERE minute = ? AND route = ? AND status_class = ?",
                (minute, route, klass),
            ).fetchone()
            if row:
                merged = [
                    a + b
                    for a, b in zip(json.loads(row["buckets"]), slot["buckets"])
                ]
                conn.execute(
                    "UPDATE request_metrics SET count = ?, sum_ms = ?, max_ms = ?, "
                    "buckets = ? WHERE minute = ? AND route = ? AND status_class = ?",
                    (
                        row["count"] + slot["count"],
                        row["sum_ms"] + slot["sum_ms"],
                        max(row["max_ms"], slot["max_ms"]),
                        json.dumps(merged),
                        minute, route, klass,
                    ),
                )
            else:
                conn.execute(
                    "INSERT INTO request_metrics "
                    "(minute, route, status_class, count, sum_ms, max_ms, buckets) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        minute, route, klass, slot["count"], slot["sum_ms"],
                        slot["max_ms"], json.dumps(slot["buckets"]),
                    ),
                )
        conn.execute("DELETE FROM request_metrics WHERE minute < ?", (cutoff,))
    return len(batch)


async def flusher() -> None:
    """Background loop. Cancelled at shutdown, which flushes one last time."""
    try:
        while True:
            await asyncio.sleep(FLUSH_SECONDS)
            try:
                await flush()
            except Exception as exc:  # noqa: BLE001
                # A metrics write must never take the service down with it.
                print(f"[metrics] flush failed: {exc}", flush=True)
    except asyncio.CancelledError:
        await flush()
        raise


# ---------------------------------------------------------------- reading it
def percentile_bound(buckets: list[int], p: float) -> dict[str, Any]:
    """The bucket a percentile falls in, reported as its upper bound.

    Returns the bound and whether the answer is an overflow, so the caller can
    render "at or under 250ms" and "over 5s" differently. Never interpolates
    inside a bucket: the data to do that honestly was not kept.
    """
    total = sum(buckets)
    if total == 0:
        return {"bound_ms": None, "over": False, "samples": 0}
    target = p / 100 * total
    seen = 0
    for i, n in enumerate(buckets):
        seen += n
        if seen >= target:
            if i >= len(BUCKETS_MS):
                return {"bound_ms": BUCKETS_MS[-1], "over": True, "samples": total}
            return {"bound_ms": BUCKETS_MS[i], "over": False, "samples": total}
    return {"bound_ms": BUCKETS_MS[-1], "over": True, "samples": total}


def summary(hours: int = 24) -> dict[str, Any]:
    """Latency and availability over a window, from the persisted rollups."""
    since = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    ).strftime("%Y-%m-%dT%H:%M")

    totals = [0] * (len(BUCKETS_MS) + 1)
    by_class: dict[str, int] = {}
    per_route: dict[str, dict[str, Any]] = {}
    hourly: dict[str, dict[str, int]] = {}
    count = 0
    sum_ms = 0.0
    max_ms = 0.0

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT minute, route, status_class, count, sum_ms, max_ms, buckets "
            "FROM request_metrics WHERE minute >= ?",
            (since,),
        ).fetchall()

    for r in rows:
        buckets = json.loads(r["buckets"])
        count += r["count"]
        sum_ms += r["sum_ms"]
        max_ms = max(max_ms, r["max_ms"])
        by_class[r["status_class"]] = by_class.get(r["status_class"], 0) + r["count"]
        for i, n in enumerate(buckets):
            totals[i] += n

        route = per_route.setdefault(
            r["route"],
            {"route": r["route"], "count": 0, "sum_ms": 0.0, "max_ms": 0.0,
             "errors": 0, "buckets": [0] * (len(BUCKETS_MS) + 1)},
        )
        route["count"] += r["count"]
        route["sum_ms"] += r["sum_ms"]
        route["max_ms"] = max(route["max_ms"], r["max_ms"])
        if r["status_class"] == "5xx":
            route["errors"] += r["count"]
        for i, n in enumerate(buckets):
            route["buckets"][i] += n

        hour = r["minute"][:13]
        slot = hourly.setdefault(hour, {"total": 0, "errors": 0})
        slot["total"] += r["count"]
        if r["status_class"] == "5xx":
            slot["errors"] += r["count"]

    served = sum(by_class.values())
    failed = by_class.get("5xx", 0)

    routes = sorted(per_route.values(), key=lambda x: -x["count"])[:12]
    for route in routes:
        route["p50"] = percentile_bound(route["buckets"], 50)
        route["p95"] = percentile_bound(route["buckets"], 95)
        route["mean_ms"] = round(route["sum_ms"] / route["count"], 1) if route["count"] else 0
        route.pop("buckets")
        route.pop("sum_ms")

    return {
        "window_hours": hours,
        "requests": count,
        "by_status": dict(sorted(by_class.items())),
        # Availability as served-minus-server-errors. A 4xx is the API
        # correctly refusing something, not the service being down, so
        # counting it here would make a wrong password look like an outage.
        "availability_percent": (
            round((served - failed) / served * 100, 3) if served else None
        ),
        "mean_ms": round(sum_ms / count, 1) if count else None,
        "max_ms": round(max_ms) if count else None,
        "p50": percentile_bound(totals, 50),
        "p95": percentile_bound(totals, 95),
        "p99": percentile_bound(totals, 99),
        "bucket_bounds_ms": BUCKETS_MS,
        "routes": routes,
        "hourly": [
            {"hour": h, **v} for h, v in sorted(hourly.items())
        ],
    }
