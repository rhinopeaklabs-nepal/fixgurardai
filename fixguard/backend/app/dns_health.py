"""DNS-level checks: does this name point at one site, or several?

Reachability already asks "can I open this address". That question is answered
by whichever address the resolver happened to hand back, which hides the
failure this module exists to find: a domain with more than one A record, where
the records disagree.

That shape is common and almost invisible to the owner. A site is moved to a
new host, the new A record is added, the old one is never removed, and from
then on roughly half of all visitors are sent to the old server. The owner
loads the site, gets the working address, and sees nothing wrong. Support gets
"it works for me" from one person and "the domain is broken" from another, and
the usual next step - reinstalling the certificate, or recreating the site - is
work on the half that was never the problem.

Everything here is measured rather than inferred: each address is asked for the
page directly, with the Host header set, and the answers are compared.
"""
from __future__ import annotations

import http.client
import socket
import ssl
from typing import Any
from urllib.parse import urlparse

# One address per family is the normal, healthy shape. More than that is not
# automatically wrong - large sites use several deliberately - so the check is
# whether they AGREE, never the count on its own.
FETCH_TIMEOUT = 8


def _addresses(host: str) -> tuple[list[str], list[str], str | None]:
    """Every address this name resolves to, split by family."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return [], [], str(exc)
    v4 = sorted({i[4][0] for i in infos if i[0] == socket.AF_INET})
    v6 = sorted({i[4][0] for i in infos if i[0] == socket.AF_INET6})
    return v4, v6, None


def _ask_one(ip: str, host: str, https: bool) -> dict[str, Any]:
    """Fetch the root path from one specific address, as a browser would.

    The Host header carries the real name so name-based virtual hosting still
    serves the right site, and the TLS handshake carries it as SNI for the same
    reason.
    """
    out: dict[str, Any] = {
        "address": ip,
        "status": None,
        "bytes": None,
        "location": None,
        "cert_covers_host": None,
        "cert_error": None,
        "error": None,
    }
    conn = None
    try:
        if https:
            # Two questions, one handshake each way round. A verified
            # connection answers "is this certificate valid for this name" by
            # succeeding or failing - which is more reliable than reading the
            # certificate back, because getpeercert() returns nothing parseable
            # once verification is off.
            #
            # The socket is built by hand so SNI carries the real name while
            # the connection goes to a chosen address. HTTPSConnection derives
            # SNI from whatever it was told to connect to, so passing the IP
            # sends the IP as SNI - and a server hosting many sites rejects
            # that handshake outright, which would report every site as
            # unreachable from every one of its own addresses.
            sock = None
            try:
                raw = socket.create_connection((ip, 443), timeout=FETCH_TIMEOUT)
                sock = ssl.create_default_context().wrap_socket(
                    raw, server_hostname=host
                )
                out["cert_covers_host"] = True
            except ssl.SSLCertVerificationError as exc:
                out["cert_covers_host"] = False
                out["cert_error"] = str(exc.verify_message or exc)[:120]

            if sock is None:
                # Retry without verification so the HTTP answer is still
                # collected. A bad certificate is a finding about this
                # address, not a reason to stop measuring it.
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                raw = socket.create_connection((ip, 443), timeout=FETCH_TIMEOUT)
                sock = ctx.wrap_socket(raw, server_hostname=host)

            conn = http.client.HTTPSConnection(host, 443, timeout=FETCH_TIMEOUT)
            conn.sock = sock
        else:
            conn = http.client.HTTPConnection(ip, 80, timeout=FETCH_TIMEOUT)

        conn.request("GET", "/", headers={"Host": host, "User-Agent": "FixGuard/1.0"})
        resp = conn.getresponse()
        body = resp.read(200_000)
        out["status"] = resp.status
        out["bytes"] = len(body)
        out["location"] = resp.getheader("Location")
    except Exception as exc:  # noqa: BLE001 - the failure itself is the result
        out["error"] = f"{type(exc).__name__}: {exc}"[:160]
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    return out


def _disagree(answers: list[dict[str, Any]]) -> bool:
    """Whether the addresses are serving materially different things.

    Byte counts are compared loosely: a page with a timestamp or a rotating
    banner differs slightly between two identical servers, and calling that a
    split would make the check useless. A different status code, or one
    address failing while another works, is never noise.
    """
    live = [a for a in answers if a["error"] is None]
    if len(live) != len(answers):
        return True
    if len({a["status"] for a in live}) > 1:
        return True
    sizes = [a["bytes"] or 0 for a in live]
    if sizes and max(sizes) > 0:
        spread = (max(sizes) - min(sizes)) / max(sizes)
        if spread > 0.25:
            return True
    return False


def inspect(url: str) -> dict[str, Any]:
    """What this name points at, and whether those places agree."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    https = parsed.scheme != "http"

    v4, v6, err = _addresses(host)
    result: dict[str, Any] = {
        "checked": True,
        "host": host,
        "ipv4": v4,
        "ipv6": v6,
        "address_count": len(v4) + len(v6),
        "answers": [],
        "addresses_disagree": False,
        "cert_mismatch_on": [],
        "issues": [],
    }

    if err:
        result["issues"].append(
            f"The name does not resolve ({err}). Nothing below could be checked."
        )
        return result

    # Only IPv4 is probed. An IPv6 address that this host cannot route to would
    # report a failure caused by the auditor's own network rather than by the
    # site, and a false finding is worse than a missing one.
    answers = [_ask_one(ip, host, https) for ip in v4[:6]]
    result["answers"] = answers

    if len(v4) > 1:
        if _disagree(answers):
            result["addresses_disagree"] = True
            broken = [a["address"] for a in answers if a["error"] is not None]
            detail = (
                f"{len(broken)} of {len(answers)} did not answer at all"
                if broken
                else "they answered differently"
            )
            result["issues"].append(
                f"This domain points at {len(v4)} different addresses and "
                f"{detail}. Visitors are sent to one at random, so some reach "
                "a working site and some do not - and whoever owns the domain "
                "usually sees the working one. Remove the address that is no "
                "longer yours."
            )
        # Nothing is said when they agree. Every CDN-fronted site resolves to
        # several addresses on purpose, so "this domain has 2 A records" is
        # true of most of the web and actionable on almost none of it. A
        # finding nobody can act on trains people to skim the ones they can.

    mismatched = [a["address"] for a in answers if a["cert_covers_host"] is False]
    if mismatched:
        result["cert_mismatch_on"] = mismatched
        result["issues"].append(
            f"The certificate served by {', '.join(mismatched)} does not cover "
            f"{host}. Visitors routed to that address get a browser security "
            "warning, which no amount of reinstalling the certificate on the "
            "other address will fix."
        )

    return result
