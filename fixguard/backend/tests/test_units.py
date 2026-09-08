"""Unit tests for the decision logic, with no network and no browser.

SRS 11.1 asks for unit testing alongside the end-to-end scenarios, and until
now there was none: everything was verified through a real browser against a
real site. That is the right way to test a browser automation tool and the
wrong way to test a threshold, because a rule that fires one time in fifty
cannot be exercised by pointing at a website and hoping.

These cover the judgements that decide what a report says - when addresses
count as disagreeing, when a password is accepted, when a score is withheld -
including the cases that would otherwise only appear in production.
"""
from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import _scopecheck  # noqa: E402
from app import accounts, dns_health, scope, scoring  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"  {'PASS' if passed else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def answer(ip="1.2.3.4", status=200, size=1000, error=None):
    return {"address": ip, "status": status, "bytes": size, "error": error}


# --------------------------------------------------------------- dns_health
def dns_tests() -> None:
    check(
        "U-01  Identical answers do not count as disagreement",
        dns_health._disagree([answer("1.1.1.1"), answer("2.2.2.2")]) is False,
    )
    check(
        "U-02  Different status codes count as disagreement",
        dns_health._disagree(
            [answer("1.1.1.1", status=200), answer("2.2.2.2", status=404)]
        ) is True,
    )
    check(
        "U-03  One address failing counts as disagreement",
        dns_health._disagree(
            [answer("1.1.1.1"), answer("2.2.2.2", error="timed out")]
        ) is True,
    )
    # A page with a timestamp or a rotating banner differs slightly between two
    # identical servers. Treating that as a split would fire on healthy sites.
    check(
        "U-04  A small size difference is not a disagreement",
        dns_health._disagree(
            [answer("1.1.1.1", size=1000), answer("2.2.2.2", size=1100)]
        ) is False,
        "10% apart",
    )
    check(
        "U-05  A large size difference is a disagreement",
        dns_health._disagree(
            [answer("1.1.1.1", size=1000), answer("2.2.2.2", size=9000)]
        ) is True,
    )
    check(
        "U-06  A single address is never a disagreement",
        dns_health._disagree([answer("1.1.1.1")]) is False,
    )


# -------------------------------------------------------------------- scope
def scope_tests() -> None:
    """The guard that decides whether a request can be scoped at all.

    This is the rule that failed in production: "make the landing page more
    modern with best seo" was accepted, matched against a logo link, and came
    back as a confident instruction to change that logo's colour.
    """
    broad = [
        "I want to make the landing page more modern with best seo",
        "make it modern",
        "make my site look better",
        "redesign the whole site",
        "improve the seo",
        "make this page more professional",
        "revamp the layout",
        "make the design cleaner",
        "add a new pricing page",
        "fix everything",
    ]
    missed = [t for t in broad if not scope.is_broad_request(t)]
    check("U-17  Requests that name no element are refused",
          not missed, f"missed: {missed}")

    # A false positive here refuses work the engine can actually do, which is
    # the more expensive mistake of the two once the guard is wide.
    narrow = [
        "Make the Send message button background red",
        "Make the main title bigger",
        "Hide the phone field",
        "Round the send message button corners to 12px",
        "Change the heading to uppercase",
        "Make the email field border red",
        "Center the main title",
        "Set the form font family to Georgia",
        "Make the paragraph font size 18px",
        "Make the send message button bold",
    ]
    wrong = [t for t in narrow if scope.is_broad_request(t)]
    check("U-18  Single-element requests are still accepted",
          not wrong, f"wrongly refused: {wrong}")

    check("U-19  The confidence floor sits above a bare guess",
          0.4 < scope.MIN_CONFIDENCE <= 0.85,
          f"MIN_CONFIDENCE={scope.MIN_CONFIDENCE}; an unjustified match scores 0.4")


# ------------------------------------------------------------------- scopes
BUG_SHAPE = """
def start(payload, who):
    return payload

def handler(payload, person):
    return start(payload, who)
"""

# The constructs that legitimately bind a name somewhere the reader cannot see
# on the same line. A checker that flags any of these is worse than none.
LEGAL_SHAPES = """
import os
TOP = 1

def outer(items):
    total = sum(x for x in items if x)

    def inner(y=TOP):
        return y + total + os.sep.count("/")

    try:
        return inner()
    except ValueError as exc:
        return str(exc)

class C:
    attr = TOP

    def m(self):
        return self.attr
"""


def scope_resolution_tests() -> None:
    """Names a handler reads have to be bound somewhere.

    Two routes shipped broken exactly this way: the POST /audits alias read
    `who` and the retry route read `bucket`, both left behind by a rename.
    Nothing caught them, because a NameError inside a request handler is a
    runtime event - the module still imports, and every test that did not
    call that one route stayed green.
    """
    found = _scopecheck.scan_source(BUG_SHAPE)
    check(
        "U-20  A renamed-away parameter is caught",
        len(found) == 1 and "'who'" in found[0],
        found[0] if found else "the checker saw nothing",
    )

    quiet = _scopecheck.scan_source(LEGAL_SHAPES)
    check(
        "U-21  Comprehensions, closures and except-as stay quiet",
        not quiet,
        "; ".join(quiet),
    )

    live = _scopecheck.scan("app")
    check(
        "U-22  No shipped function reads an unbound name",
        not live,
        "; ".join(live[:4]),
    )


# ----------------------------------------------------------------- accounts
def account_tests() -> None:
    pw = "a few ordinary words"
    stored = accounts.hash_password(pw)
    check("U-07  A correct password verifies", accounts.verify_password(pw, stored))
    check(
        "U-08  A wrong password does not verify",
        not accounts.verify_password(pw + "!", stored),
    )
    check(
        "U-09  The same password hashes differently each time (salted)",
        accounts.hash_password(pw) != stored,
    )
    check(
        "U-10  A corrupt stored hash is rejected, not crashed on",
        accounts.verify_password(pw, "not-a-real-hash") is False,
    )

    ok = True
    for bad in ["", "short", "nine char"]:
        try:
            accounts.check_password_strength(bad)
            ok = False
        except accounts.AccountError:
            pass
    check("U-11  Passwords under 10 characters are refused", ok)

    try:
        accounts.check_password_strength("ten chars!")
        length_ok = True
    except accounts.AccountError:
        length_ok = False
    check("U-12  Exactly 10 characters is accepted", length_ok)

    ok = True
    for bad in ["nope", "a@b", "a@b.c", "@example.com", "spaces @example.com"]:
        try:
            accounts.normalise_email(bad)
            ok = False
        except accounts.AccountError:
            pass
    check("U-13  Malformed emails are refused", ok)
    check(
        "U-14  Emails are normalised to lower case",
        accounts.normalise_email("  Alice@Example.COM ") == "alice@example.com",
    )


# ------------------------------------------------------------------ metrics
def metrics_tests() -> None:
    """The bucketing, which is where a latency number could quietly lie.

    Percentiles here are the upper bound of the bucket a value falls in, not
    an interpolation inside it. That is a real loss of precision, and these
    pin down that it is the honest direction: never reported as faster than
    the data can support.
    """
    from app import metrics

    bounds = metrics.BUCKETS_MS
    check(
        "U-32  A duration lands in the first bucket it fits",
        metrics.bucket_index(0) == 0
        and metrics.bucket_index(bounds[0]) == 0
        and metrics.bucket_index(bounds[0] + 0.001) == 1,
        f"boundary at {bounds[0]}ms",
    )
    check(
        "U-33  Anything past the last bound is the overflow bucket",
        metrics.bucket_index(bounds[-1] + 1) == len(bounds),
    )

    # 100 requests, all in the 5-10ms bucket. p95 must not claim 5ms.
    fast = [0, 100] + [0] * (len(bounds) - 1)
    p95 = metrics.percentile_bound(fast, 95)
    check(
        "U-34  A percentile is the bucket's upper bound, never below it",
        p95["bound_ms"] == bounds[1] and p95["over"] is False,
        f"p95 reported {p95}",
    )

    # Two slow requests in a hundred reach p99; one does not, and should not.
    # A single outlier in a hundred is the hundredth value, so a p99 that
    # surfaced it would be reporting something worse than the data says. The
    # honest home for that one request is max_ms, which the console shows.
    two_slow = [98] + [0] * (len(bounds) - 1) + [2]
    one_slow = [99] + [0] * (len(bounds) - 1) + [1]
    check(
        "U-35  p99 reflects the sample, not the single worst request",
        metrics.percentile_bound(two_slow, 99)["over"] is True
        and metrics.percentile_bound(one_slow, 99)["over"] is False
        and metrics.percentile_bound(two_slow, 50)["bound_ms"] == bounds[0],
        f"two_slow p99={metrics.percentile_bound(two_slow, 99)}",
    )
    check(
        "U-36  No samples means no percentile, not a zero",
        metrics.percentile_bound([0] * (len(bounds) + 1), 50)["bound_ms"] is None,
    )

# -------------------------------------------------------------------- admin
class FakeRequest:
    """Enough of a Request for the gate: cookies and headers."""

    def __init__(self, cookies=None, headers=None):
        self.cookies = cookies or {}
        self.headers = headers or {}


def admin_tests() -> None:
    """The admin gate, which is the only new privilege in the system.

    Worth unit-testing rather than trusting to a live call, because the two
    interesting cases - a signed-in non-admin, and a caller holding the
    service API key - both succeed against every other route in the app.
    """
    from app.routers import admin as admin_router
    from app.routers import auth as auth_router
    from app.errors import FixGuardError

    original = auth_router.current_user
    try:
        def refuse(who):
            auth_router.current_user = lambda request: who
            try:
                admin_router.require_admin(FakeRequest())
                return None
            except FixGuardError as exc:
                return exc

        signed_out = refuse(None)
        plain_user = refuse({"id": "u1", "email": "a@b.com", "is_admin": False})
        check(
            "U-23  A signed-in non-admin is refused",
            plain_user is not None,
        )
        # Same code and same message both ways. A distinct "forbidden" tells a
        # curious account that the console exists and is worth attacking.
        check(
            "U-24  Non-admin and signed-out are indistinguishable",
            signed_out is not None
            and signed_out.code == plain_user.code
            and signed_out.message == plain_user.message,
            f"{getattr(signed_out, 'code', None)} vs {getattr(plain_user, 'code', None)}",
        )
        check(
            "U-25  The refusal does not admit the route exists",
            plain_user.status == 404,
            f"status {plain_user.status}",
        )

        auth_router.current_user = lambda request: {
            "id": "u2", "email": "boss@b.com", "is_admin": True,
        }
        allowed = admin_router.require_admin(FakeRequest())
        check("U-26  A listed admin is allowed", allowed["email"] == "boss@b.com")
    finally:
        auth_router.current_user = original

    # The service key opens audits; it must not open administration. Asserted
    # against the source because the gate calling anything else is the bug.
    import inspect

    source = inspect.getsource(admin_router.require_admin)
    check(
        "U-27  The admin gate reads a session and nothing else",
        "x-api-key" not in source.lower() and "identity" not in source,
        source.strip().splitlines()[-3:],
    )

    # Secrets are safest in a query that never selects them.
    import app.adminstats as adminstats

    reporting = inspect.getsource(adminstats)
    check(
        "U-28  No admin query selects a password hash or a session token",
        "password_hash" not in reporting
        and "token_hash" not in reporting.replace("key_hash", ""),
    )

    from app import config

    original_list = config.ADMIN_EMAILS
    try:
        config.ADMIN_EMAILS = ["boss@example.com"]
        check(
            "U-29  Admin is decided by the environment, case and space aside",
            accounts.is_admin("  BOSS@Example.com ")
            and not accounts.is_admin("someone@example.com")
            and not accounts.is_admin(None),
        )
        # The failure this shape prevents: an empty list is the off switch,
        # and must not mean "everyone" the way a permissive default would.
        config.ADMIN_EMAILS = []
        check(
            "U-30  An empty list admits nobody",
            not accounts.is_admin("boss@example.com"),
        )
    finally:
        config.ADMIN_EMAILS = original_list

    check(
        "U-31  Percentiles are exact on the sample, not interpolated",
        adminstats._pct([10, 20, 30, 40], 50) == 20
        and adminstats._pct([10, 20, 30, 40], 100) == 40
        and adminstats._pct([], 50) is None,
        f"p50={adminstats._pct([10, 20, 30, 40], 50)}",
    )

# ------------------------------------------------------------------ scoring
def scoring_tests() -> None:
    # The failure this guards against shipped once: a run that measured only
    # reachability reported 100 and "Verified Healthy" for a site nobody could
    # open.
    reach_only = {
        "modules_selected": ["reach"],
        "reachability": {"dns_resolved": True, "status_code": 200, "tls": {}},
    }
    out = scoring.compute(reach_only)
    check(
        "U-15  Reachability alone yields no score at all",
        out["composite_score"] is None and out["grade"] == "not_assessed",
        f"score={out['composite_score']} grade={out['grade']}",
    )
    check(
        "U-16  A withheld score says why",
        bool(out.get("not_assessed_reason")),
        (out.get("not_assessed_reason") or "")[:70],
    )


def main() -> int:
    print("dns_health")
    dns_tests()
    print("\nscope")
    scope_tests()
    print("\nscope resolution")
    scope_resolution_tests()
    print("\naccounts")
    account_tests()
    print("\nscoring")
    scoring_tests()
    print("\nadmin")
    admin_tests()
    print("\nmetrics")
    metrics_tests()

    passed = [n for n, ok, _ in results if ok]
    failed = [n for n, ok, _ in results if not ok]
    print("=" * 62)
    print(f"  {len(passed)} of {len(results)} unit checks pass")
    if failed:
        print(f"  FAILING: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
