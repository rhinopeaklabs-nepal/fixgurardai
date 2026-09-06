"""SRS section 11.2 acceptance scenarios, T-01 to T-12.

Runs against a live API and the local testbed rather than mocks, because the
thing under test is browser behaviour: mocking Playwright would only prove the
mock works.

    # terminal 1
    python testbed/server.py
    # terminal 2
    cd backend && ALLOW_PRIVATE_TARGETS=1 .venv/Scripts/python -m uvicorn app.main:app --port 8000
    # terminal 3
    cd backend && .venv/Scripts/python -m tests.test_acceptance

Exits non-zero if any scenario fails, so it can gate a deploy.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
TESTBED = "http://127.0.0.1:8080"
KEY = "fixguard-dev-key"
DB = Path(__file__).resolve().parent.parent / "data" / "fixguard.db"

results: list[tuple[str, str, bool, str]] = []


# --------------------------------------------------------------------------
def call(method: str, path: str, body: dict | None = None, key: str | None = KEY):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-API-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
            return r.status, (json.loads(raw) if "json" in ctype else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def run_audit(url: str, modules: list[str] | None = None, timeout_s: int = 180):
    status, body = call(
        "POST", "/api/v1/audits/start",
        {"domain_url": url, "i_own_this_site": True,
         **({"modules": modules} if modules else {})},
    )
    if status != 201:
        return None, body, 0.0
    aid = body["audit_id"]
    started = time.monotonic()
    while time.monotonic() - started < timeout_s:
        _, st = call("GET", f"/api/v1/audits/{aid}/status")
        if st.get("status") in {"complete", "failed"}:
            break
        time.sleep(2)
    _, report = call("GET", f"/api/v1/audits/{aid}/report")
    return aid, report, time.monotonic() - started


def check(tid: str, name: str, passed: bool, detail: str = "") -> None:
    results.append((tid, name, passed, detail))
    print(f"  {'PASS' if passed else 'FAIL'}  {tid}  {name}"
          + (f"\n          {detail}" if detail else ""))


def not_applicable(tid: str, name: str, reason: str) -> None:
    """A scenario this system cannot satisfy by construction.

    Recording one as a failure would leave the suite permanently red, and a
    suite that is always red is a suite nobody reads - the next real
    regression would land unnoticed. Recording it as a pass would be a lie
    about what was verified. It is a third thing, and counted as such.
    """
    results.append((tid, name, None, reason))
    print(f"  N/A   {tid}  {name}")
    print(f"          {reason}")


def clear_rate_limit() -> None:
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM rate_events")
        c.commit()


def clean_up() -> None:
    """Leave no trace: the suite deliberately burns the hourly quota and
    creates junk audits, and neither should land on the user's dashboard."""
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM rate_events")
        c.execute(
            "DELETE FROM audit_runs WHERE target_url LIKE '%example.invalid%' "
            "OR target_url LIKE '%127.0.0.1:9%'"
        )
        c.execute("DELETE FROM share_links WHERE token = ?",
                  ("expired-token-for-acceptance-test",))
        c.commit()


# --------------------------------------------------------------------------
def main() -> int:
    print("\nSRS 11.2 acceptance scenarios\n" + "=" * 62)
    clear_rate_limit()

    # T-01 ------------------------------------------------------------------
    aid, report, _ = run_audit(f"{TESTBED}/")
    forms = (report or {}).get("form_results") or []
    check("T-01", "Valid URL returns a form result",
          report.get("status") == "complete" and len(forms) == 1,
          f"status={report.get('status')} forms={len(forms)}")

    # T-03 ------------------------------------------------------------------
    silent = forms and forms[0].get("verdict") == "silent_failure"
    check("T-03", "Success shown, no request -> silent_failure",
          bool(silent),
          f"verdict={forms[0].get('verdict') if forms else 'none'}")

    # T-06 ------------------------------------------------------------------
    errs = report.get("console_errors") or []
    with_src = [e for e in errs if e.get("source_url") and e.get("line") is not None]
    check("T-06", "Console errors captured with source and line",
          len(with_src) > 0, f"{len(with_src)} of {len(errs)} carry source+line")

    # T-10 (score + PDF) ----------------------------------------------------
    st, pdf = call("GET", f"/api/v1/reports/{aid}/pdf")
    is_pdf = st == 200 and isinstance(pdf, bytes) and pdf.startswith(b"%PDF")
    took = (report.get("duration_ms") or 0) / 1000
    check("T-10", "Full audit < 60s, score and PDF produced",
          took < 60 and report.get("health_score") is not None and is_pdf,
          f"{took:.1f}s score={report.get('health_score')} pdf={len(pdf) if is_pdf else 0}B")

    # T-02 ------------------------------------------------------------------
    _, r2, _ = run_audit("http://127.0.0.1:9/")
    check("T-02", "Unreachable URL -> UNREACHABLE_TARGET",
          r2.get("error_code") == "UNREACHABLE_TARGET",
          f"error_code={r2.get('error_code')}")

    # T-04 ------------------------------------------------------------------
    not_applicable(
        "T-04", "Reply-To header verification",
        "Form mail is sent by the host directly to the site owner and never "
        "reaches FixGuard, so there is no header for it to inspect. "
        "Documented in docs/SRS-TRACEABILITY.md.")

    # T-05 ------------------------------------------------------------------
    _, r5, _ = run_audit(f"{TESTBED}/loop.html")
    router5 = r5.get("router_result") or {}
    check("T-05", "Router loop -> has_navigation_loop true",
          router5.get("has_navigation_loop") is True,
          f"loop_count={router5.get('loop_count')} "
          f"blocked_load={router5.get('page_load_blocked_by_loop')}")

    # T-07 ------------------------------------------------------------------
    _, r7, _ = run_audit(f"{TESTBED}/blocked", modules=["reach"])
    reach7 = r7.get("reachability") or {}
    check("T-07", "403 response -> ip_blocked true",
          reach7.get("ip_blocked") is True,
          f"status={reach7.get('status_code')} ip_blocked={reach7.get('ip_blocked')} "
          f"(single region only; cross-region comparison not implemented)")

    # T-08 ------------------------------------------------------------------
    st8, r8 = call("POST", "/api/v1/prompts/surgify",
                   {"intent": "change the send message button colour to blue",
                    "page_url": f"{TESTBED}/"})
    prompt = (r8 or {}).get("prompt", "")
    check("T-08", "Surgical prompt scopes to a selector with DO NOT clauses",
          st8 == 200 and bool(r8.get("selector")) and "DO NOT" in prompt
          and r8.get("selector") in prompt,
          f"selector={r8.get('selector')} property={r8.get('property')} "
          f"value={r8.get('value')}")

    # T-09 ------------------------------------------------------------------
    clear_rate_limit()
    codes = []
    for _ in range(11):
        # A reachable host, so no slot is refunded mid-count.
        s, b = call("POST", "/api/v1/audits/start",
                    {"domain_url": TESTBED + "/good.html", "i_own_this_site": True,
                     "modules": ["reach"]})
        codes.append(s if s != 429 else (b.get("error") or {}).get("code"))
    check("T-09", "11th audit in an hour -> RATE_LIMIT_EXCEEDED",
          codes[-1] == "RATE_LIMIT_EXCEEDED" and codes[:10] == [201] * 10,
          f"first10={set(codes[:10])} eleventh={codes[-1]}")

    # T-11 ------------------------------------------------------------------
    _, share = call("POST", f"/api/v1/audits/{aid}/share")
    token = share.get("token")
    st11, pub = call("GET", f"/api/v1/public/reports/{token}?mode=client", key=None)
    leaked = [k for k in ("console_errors", "routes_map", "asset_issues") if k in pub]
    check("T-11", "Shared link renders unauthenticated in client mode",
          st11 == 200 and pub.get("mode") == "client" and not leaked,
          f"score={pub.get('health_score')} leaked_dev_fields={leaked or 'none'}")

    # T-12 ------------------------------------------------------------------
    expired = "expired-token-for-acceptance-test"
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)).isoformat()
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM share_links WHERE token = ?", (expired,))
        c.execute(
            "INSERT INTO share_links (token, audit_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (expired, aid, past, past),
        )
        c.commit()
    st12, body12 = call("GET", f"/api/v1/public/reports/{expired}", key=None)
    check("T-12", "Expired share link -> 410 Gone",
          st12 == 410 and (body12.get("error") or {}).get("code") == "REPORT_EXPIRED",
          f"http={st12} code={(body12.get('error') or {}).get('code')}")

    # ----------------------------------------------------------------------
    clean_up()

    passed = [t for t, _, ok, _ in results if ok is True]
    failed = [t for t, _, ok, _ in results if ok is False]
    skipped = [t for t, _, ok, _ in results if ok is None]

    print("=" * 62)
    print(f"  {len(passed)} of {len(passed) + len(failed)} applicable "
          f"scenarios pass")
    if skipped:
        print(f"  not applicable: {', '.join(skipped)}")
    if failed:
        print(f"  FAILING: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
