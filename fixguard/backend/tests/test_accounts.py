"""Account, session and ownership scenarios.

Separate from test_acceptance.py because those trace the SRS scenarios and
these do not - accounts came later. Run together by tests.run_acceptance.

The checks that matter most here are the negative ones. A sign-in screen that
works is easy; a sign-in screen that actually stops a signed-in stranger from
reading somebody else's audit is the part worth testing, and it is the part
that silently regresses when an endpoint is added without its ownership check.
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
import uuid

API = "http://127.0.0.1:8000"
KEY = "fixguard-dev-key"

results: list[tuple[str, bool, str]] = []


def session():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(opener, method, path, body=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-API-Key", key)
    try:
        with opener.open(req, timeout=45) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "{}")
        except ValueError:
            return e.code, {"raw": raw[:200]}


def code_of(body: dict) -> str | None:
    return (body.get("error") or {}).get("code")


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"  {'PASS' if passed else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def main() -> int:
    anon = session()
    alice = session()
    bob = session()

    a_email = f"alice-{uuid.uuid4().hex[:8]}@example.com"
    b_email = f"bob-{uuid.uuid4().hex[:8]}@example.com"
    pw = "correct horse battery staple"

    # ---- signed out -----------------------------------------------------
    s, b = call(anon, "GET", "/api/v1/auth/me")
    check("A-01  Signed out, /me answers 200 with a null user",
          s == 200 and b.get("user") is None, f"http={s}")

    s, b = call(anon, "GET", "/api/v1/audits")
    check("A-02  Signed out, history is refused",
          s == 401 and code_of(b) == "AUTH_REQUIRED", f"http={s} code={code_of(b)}")

    # ---- validation -----------------------------------------------------
    s, _ = call(anon, "POST", "/api/v1/auth/signup",
                {"email": a_email, "password": "short"})
    check("A-03  Password under 10 characters is refused", s == 400, f"http={s}")

    s, _ = call(anon, "POST", "/api/v1/auth/signup",
                {"email": "not-an-email", "password": pw})
    check("A-04  Malformed email is refused", s == 400, f"http={s}")

    # ---- signup / duplicate ---------------------------------------------
    s, b = call(alice, "POST", "/api/v1/auth/signup",
                {"email": a_email, "password": pw, "name": "Alice"})
    alice_id = (b.get("user") or {}).get("id")
    check("A-05  Signup succeeds and starts a session",
          s == 201 and bool(alice_id), f"http={s} id={alice_id}")

    s, _ = call(anon, "POST", "/api/v1/auth/signup",
                {"email": a_email.upper(), "password": pw})
    check("A-06  Duplicate email is refused regardless of case", s == 400, f"http={s}")

    # ---- login errors do not distinguish --------------------------------
    _, b1 = call(anon, "POST", "/api/v1/auth/login",
                 {"email": f"nobody-{uuid.uuid4().hex[:6]}@example.com", "password": pw})
    _, b2 = call(anon, "POST", "/api/v1/auth/login",
                 {"email": a_email, "password": "definitely not the password"})
    m1 = (b1.get("error") or {}).get("message")
    m2 = (b2.get("error") or {}).get("message")
    check("A-07  Unknown email and wrong password are indistinguishable",
          m1 == m2 and bool(m1), f"{m1!r}")

    # ---- ownership -------------------------------------------------------
    s, b = call(bob, "POST", "/api/v1/auth/signup",
                {"email": b_email, "password": pw, "name": "Bob"})
    check("A-08  A second account can be created", s == 201, f"http={s}")

    s, b = call(alice, "POST", "/api/v1/audits/start",
                {"domain_url": "http://127.0.0.1:8080/good.html",
                 "i_own_this_site": True, "max_pages": 1})
    audit_id = b.get("audit_id")
    check("A-09  A signed-in user can start an audit",
          s == 201 and bool(audit_id), f"http={s}")

    s, b = call(bob, "GET", f"/api/v1/audits/{audit_id}")
    check("A-10  Another account cannot read that audit, and is not told it exists",
          s == 404 and code_of(b) == "AUDIT_NOT_FOUND", f"http={s} code={code_of(b)}")

    s, b = call(bob, "GET", "/api/v1/audits")
    ids = [a["id"] for a in (b.get("audits") or [])]
    check("A-11  Another account's history does not contain it",
          s == 200 and audit_id not in ids, f"http={s} n={len(ids)}")

    s, b = call(alice, "GET", "/api/v1/audits")
    ids = [a["id"] for a in (b.get("audits") or [])]
    check("A-12  The owner does see it in their own history",
          s == 200 and audit_id in ids, f"http={s} n={len(ids)}")

    s, b = call(bob, "GET", f"/api/v1/reports/{audit_id}/pdf")
    check("A-13  Another account cannot download the certificate",
          s == 404, f"http={s}")

    # ---- the API key path still works ------------------------------------
    s, _ = call(anon, "GET", "/api/v1/audits", key=KEY)
    check("A-14  The API key still authenticates scripted callers", s == 200, f"http={s}")

    # ---- sign out --------------------------------------------------------
    s, _ = call(alice, "POST", "/api/v1/auth/logout")
    s2, b2 = call(alice, "GET", "/api/v1/auth/me")
    check("A-15  Signing out ends the session",
          s == 200 and b2.get("user") is None, f"logout={s} user={b2.get('user')}")

    s, b = call(alice, "GET", "/api/v1/audits")
    check("A-16  After signing out the history is refused again",
          s == 401 and code_of(b) == "AUTH_REQUIRED", f"http={s} code={code_of(b)}")

    passed = [n for n, ok, _ in results if ok]
    failed = [n for n, ok, _ in results if not ok]
    print("=" * 62)
    print(f"  {len(passed)} of {len(results)} account scenarios pass")
    if failed:
        print(f"  FAILING: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
