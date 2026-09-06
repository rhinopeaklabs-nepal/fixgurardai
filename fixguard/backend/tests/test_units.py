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

from app import accounts, dns_health, scoring  # noqa: E402

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
    print("\naccounts")
    account_tests()
    print("\nscoring")
    scoring_tests()

    passed = [n for n, ok, _ in results if ok]
    failed = [n for n, ok, _ in results if not ok]
    print("=" * 62)
    print(f"  {len(passed)} of {len(results)} unit checks pass")
    if failed:
        print(f"  FAILING: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
