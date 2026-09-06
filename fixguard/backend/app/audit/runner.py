"""Audit lifecycle: queue, run, broadcast progress, persist.

No Redis. A single asyncio semaphore caps concurrency at one browser, which is
all a 1 vCPU VPS can honestly serve. Progress is fanned out to any connected
SSE clients through per-run subscriber queues.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from typing import Any

from .. import agents, config, db, ratelimit, reachability, scoring
from .probe import run_audit

_sem = asyncio.Semaphore(config.MAX_CONCURRENT_AUDITS)
_subscribers: dict[str, set[asyncio.Queue]] = {}
_tasks: dict[str, asyncio.Task] = {}

ALL_MODULES = ["form", "router", "assets", "reach", "a11y", "perf", "mobile"]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def subscribe(run_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.setdefault(run_id, set()).add(q)
    return q


def unsubscribe(run_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(run_id)
    if subs:
        subs.discard(q)
        if not subs:
            _subscribers.pop(run_id, None)


async def _broadcast(run_id: str, event: str, data: dict[str, Any]) -> None:
    payload = {"event": event, **data}
    for q in list(_subscribers.get(run_id, ())):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def start(
    target_url: str,
    test_email: str,
    modules: list[str] | None = None,
    retry_of: str | None = None,
    rate_key: str | None = None,
    max_pages: int = 1,
    auth: dict[str, Any] | None = None,
    owner_id: str | None = None,
) -> str:
    mods = [m for m in (modules or ALL_MODULES) if m in ALL_MODULES] or ALL_MODULES
    run_id = str(uuid.uuid4())
    db.insert_run(
        run_id, target_url, _now(), modules=mods, retry_of=retry_of,
        owner_id=owner_id,
    )
    _tasks[run_id] = asyncio.create_task(
        _execute(run_id, target_url, test_email, mods, rate_key, max_pages, auth)
    )
    return run_id


async def _execute(
    run_id: str,
    target_url: str,
    test_email: str,
    modules: list[str],
    rate_key: str | None = None,
    max_pages: int = 1,
    auth: dict[str, Any] | None = None,
) -> None:
    completed: list[str] = []

    async def progress(
        stage: str,
        message: str,
        percent: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        # stage == "module_complete" means `message` is the module name.
        if stage == "module_complete":
            completed.append(message)
            db.update_run(run_id, modules_complete=completed)
            await _broadcast(
                run_id,
                "module_complete",
                {"module": message, "result": payload or {}},
            )
            return

        fields: dict[str, Any] = {"stage": message}
        if percent is not None:
            fields["progress_percent"] = percent
        db.update_run(run_id, **fields)
        await _broadcast(
            run_id,
            "progress",
            {"step": message, "stage": stage, "percent": percent},
        )

    try:
        async with _sem:
            db.update_run(run_id, status="running", stage="Starting", progress_percent=2)
            await _broadcast(
                run_id, "progress", {"step": "Starting", "stage": "start", "percent": 2}
            )

            # Reachability runs first: it needs no browser, takes about a
            # second, and when the page then fails to load its DNS/TLS/status
            # findings are what explain why. UC4 requires partial results
            # rather than failing the whole audit when one module cannot run.
            reach = None
            if "reach" in modules:
                await progress("reach", "Checking DNS, TLS and reachability", 8)
                reach = await reachability.probe(target_url)
                _persist_geo(run_id, reach)
                await progress(
                    "module_complete", "reach", None,
                    {"status": reach.get("status_code"),
                     "tls_valid": (reach.get("tls") or {}).get("valid")},
                )

            browser_modules = [m for m in modules if m != "reach"]
            browser_error: str | None = None
            try:
                # Each extra page costs another load and another set of
                # checks, so the ceiling has to grow with the scan.
                budget = config.AUDIT_HARD_TIMEOUT_S + (max_pages - 1) * 25
                result = await asyncio.wait_for(
                    run_audit(
                        target_url, test_email, progress, browser_modules,
                        max_pages, auth,
                    ),
                    timeout=budget,
                )
            except (RuntimeError, asyncio.TimeoutError) as exc:
                # Partial results are only honest when the host actually
                # answered. A 403 or 500 means reachable-but-blocked, and the
                # reachability findings explain it. No DNS or no response at
                # all means unreachable, which is a failure, not a report.
                # A rejected session is a setup problem the user must fix, not
                # a finding about their site. Degrading it to a partial audit
                # would bury the one message they need to read.
                if isinstance(exc, RuntimeError) and str(exc).startswith(
                    "SESSION_INVALID"
                ):
                    raise

                answered = bool(
                    reach
                    and reach.get("dns_resolved")
                    and reach.get("status_code") is not None
                )
                if not answered:
                    raise
                # A blocked or unreachable page still has reachability
                # findings worth reporting - that is the whole point of the
                # module. Degrade to a partial audit instead of failing.
                browser_error = (
                    f"exceeded {config.AUDIT_HARD_TIMEOUT_S}s"
                    if isinstance(exc, asyncio.TimeoutError)
                    else str(exc).partition("::")[2] or str(exc)
                )
                result = {
                    "console_errors": [],
                    "router_result": {},
                    "form_results": [],
                    "asset_issues": [],
                    "modules_complete": [],
                    "site_map": {"measured": False},
                    "auth": {"used": bool(auth), "verified": False},
                    "accessibility": {"measured": False},
                    "performance": {"measured": False},
                    "mobile": {"measured": False},
                    "pages": [],
                    "pages_audited": 1,
                    "duration_ms": 0,
                }

            if reach is not None:
                result["reachability"] = reach
            result["modules_selected"] = modules
            result["modules_failed"] = browser_modules if browser_error else []
            result["partial_reason"] = browser_error

        # Agent 1: raw console output -> plain English.
        await progress("agents", "Explaining findings", 95)
        parsed_errors = await agents.parse_logs(result.get("console_errors") or [])

        score = scoring.compute(result)
        # Agent 3 needs the score, so it runs after scoring.
        summary = await agents.summarise({**result, **{
            "health_score": score["composite_score"],
            "grade": score["grade"],
            "score_breakdown": score,
            "target_url": target_url,
        }})

        db.update_run(
            run_id,
            status="complete",
            stage="Complete",
            progress_percent=100,
            reachability=result.get("reachability"),
            site_map=result.get("site_map"),
            auth_info=result.get("auth"),
            accessibility=result.get("accessibility"),
            performance=result.get("performance"),
            mobile=result.get("mobile"),
            pages=result.get("pages") or [],
            pages_audited=result.get("pages_audited") or 1,
            modules_failed=result.get("modules_failed") or [],
            partial_reason=result.get("partial_reason"),
            parsed_errors=parsed_errors,
            executive_summary=summary["summary"],
            # Merge both sources: probe.py reports the browser modules, the
            # progress callback records reach, which runs outside the browser.
            modules_complete=list(
                dict.fromkeys((result.get("modules_complete") or []) + completed)
            ),
            health_score=score["composite_score"],
            grade=score["grade"],
            score_breakdown=score,
            console_errors=result["console_errors"],
            router_result=result["router_result"],
            form_results=result["form_results"],
            asset_issues=result["asset_issues"],
            duration_ms=result["duration_ms"],
            completed_at=_now(),
        )
        await _broadcast(
            run_id,
            "complete",
            {
                "audit_id": run_id,
                "health_score": score["composite_score"],
                "grade": score["grade"],
                "label": score["label"],
                "partial": bool(result.get("partial_reason")),
            },
        )

    except asyncio.TimeoutError:
        await _fail(
            run_id,
            "AUDIT_TIMEOUT",
            f"The audit exceeded {config.AUDIT_HARD_TIMEOUT_S} seconds.",
            retryable=True,
        )

    except RuntimeError as exc:
        raw = str(exc)
        code, _, detail = raw.partition("::")
        code = code or "WORKER_CRASH"
        # An unreachable host cost a DNS lookup, not a browser run. Charging a
        # slot for it means a few typos lock the user out for an hour.
        if code == "UNREACHABLE_TARGET" and rate_key:
            ratelimit.refund(rate_key)
        await _fail(run_id, code, detail or raw, retryable=True)

    except Exception as exc:  # noqa: BLE001 - last-resort guard
        await _fail(
            run_id,
            "WORKER_CRASH",
            f"{type(exc).__name__}: {exc}"[:500],
            retryable=True,
        )

    finally:
        _tasks.pop(run_id, None)
        await _broadcast(run_id, "end", {})


async def _fail(run_id: str, code: str, detail: str, retryable: bool) -> None:
    db.update_run(
        run_id,
        status="failed",
        stage="Failed",
        error_code=code,
        error_detail=detail,
        retryable=1 if retryable else 0,
        completed_at=_now(),
    )
    await _broadcast(
        run_id,
        "failed",
        {
            "audit_id": run_id,
            "error": {
                "code": code,
                "message": detail,
                "audit_id": run_id,
                "retryable": retryable,
            },
        },
    )


def _persist_geo(run_id: str, reach: dict[str, Any]) -> None:
    """One row per region, so adding probes later needs no schema change."""
    try:
        db.insert_geo_result(
            {
                "id": str(uuid.uuid4()),
                "audit_id": run_id,
                "region_code": reach.get("region_code") or "unknown",
                "status_code": reach.get("status_code"),
                "response_time_ms": reach.get("response_time_ms"),
                "ip_blocked": reach.get("ip_blocked"),
                "ssl_valid": (reach.get("tls") or {}).get("valid"),
                "dns_resolved": reach.get("dns_resolved"),
                "detail": {
                    "issues": reach.get("issues"),
                    "redirect_chain": reach.get("redirect_chain"),
                    "ip_addresses": reach.get("ip_addresses"),
                },
                "created_at": _now(),
            }
        )
    except Exception:
        # Telemetry must not fail the audit that produced it.
        pass


def sse_format(payload: dict[str, Any]) -> str:
    event = payload.pop("event", "message")
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
