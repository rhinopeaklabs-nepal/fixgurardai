"""FR-3.4, scoped to what one host can honestly measure.

The spec asks for probes from three regions. The challenge grant is one VPS, so
comparing regions is impossible and inventing the comparison would be fabricated
data. What a single host *can* measure is still worth having, and is exactly
what breaks client sites in practice:

  - DNS resolves at all, and to what
  - the TLS certificate is valid, matches the host, and is not about to expire
  - the redirect chain terminates
  - the response status and latency
  - whether the host answers with a block page (403/451)

Results are stored per region, so adding proxies later needs no schema change.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlparse

from . import config


def _resolve(host: str) -> tuple[bool, list[str], str | None]:
    try:
        infos = socket.getaddrinfo(host, None)
        ips = sorted({i[4][0] for i in infos})
        return True, ips, None
    except socket.gaierror as exc:
        return False, [], str(exc)


def _tls_info(host: str, port: int = 443) -> dict[str, Any]:
    out: dict[str, Any] = {
        "checked": True, "valid": None, "expires_at": None,
        "days_remaining": None, "issuer": None, "error": None,
    }
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection(
            (host, port), timeout=config.REACHABILITY_TIMEOUT_S
        ) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
        not_after = cert.get("notAfter")
        if not_after:
            expires = dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                tzinfo=dt.timezone.utc
            )
            out["expires_at"] = expires.isoformat()
            out["days_remaining"] = (expires - dt.datetime.now(dt.timezone.utc)).days
        issuer = dict(x[0] for x in cert.get("issuer", ()) if x)
        out["issuer"] = issuer.get("organizationName") or issuer.get("commonName")
        out["valid"] = True
    except ssl.SSLCertVerificationError as exc:
        out["valid"] = False
        out["error"] = f"Certificate verification failed: {exc.verify_message or exc}"
    except (socket.timeout, TimeoutError):
        out["valid"] = None
        out["error"] = "Timed out opening a TLS connection"
    except OSError as exc:
        out["valid"] = None
        out["error"] = str(exc)
    return out


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects manually so the chain can be reported."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _fetch_chain(url: str, max_hops: int = 6) -> dict[str, Any]:
    chain: list[dict[str, Any]] = []
    current = url
    opener = urllib.request.build_opener(_NoRedirect)
    started = time.monotonic()
    status: int | None = None
    error: str | None = None

    for _ in range(max_hops):
        req = urllib.request.Request(
            current,
            headers={"User-Agent": "FixGuardAI/1.0 (+site health audit)"},
            method="GET",
        )
        try:
            with opener.open(req, timeout=config.REACHABILITY_TIMEOUT_S) as resp:
                status = resp.status
                chain.append({"url": current, "status": status})
                break
        except urllib.error.HTTPError as exc:
            status = exc.code
            location = exc.headers.get("Location") if exc.headers else None
            chain.append({"url": current, "status": status, "location": location})
            if status in (301, 302, 303, 307, 308) and location:
                current = urllib.parse.urljoin(current, location)
                continue
            break
        except urllib.error.URLError as exc:
            error = str(exc.reason)
            chain.append({"url": current, "status": None, "error": error})
            break
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            chain.append({"url": current, "status": None, "error": error})
            break
    else:
        error = "Too many redirects"

    return {
        "status": status,
        "response_time_ms": int((time.monotonic() - started) * 1000),
        "chain": chain,
        "error": error,
        "redirect_hops": max(0, len(chain) - 1),
    }


def _probe_sync(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    dns_ok, ips, dns_err = _resolve(host)

    if not dns_ok:
        return {
            "region_code": config.REGION_LABEL,
            "dns_resolved": False,
            "dns_error": dns_err,
            "ip_addresses": [],
            "tls": {"checked": False},
            "status_code": None,
            "response_time_ms": None,
            "redirect_chain": [],
            "ip_blocked": False,
            "issues": ["The domain name does not resolve. Check its DNS records."],
        }

    tls = (
        _tls_info(host, parsed.port or 443)
        if parsed.scheme == "https"
        else {"checked": False, "valid": None}
    )
    http = _fetch_chain(url)

    issues: list[str] = []
    status = http["status"]
    if status in (403, 451):
        issues.append(
            f"The server answered {status}, which usually means requests from this "
            "network are being blocked."
        )
    elif status is not None and status >= 500:
        issues.append(f"The server returned {status}.")
    elif status is None:
        issues.append(f"No HTTP response: {http.get('error')}")

    if tls.get("valid") is False:
        issues.append(tls.get("error") or "The TLS certificate is not valid.")
    days = tls.get("days_remaining")
    if isinstance(days, int):
        if days < 0:
            issues.append("The TLS certificate has expired.")
        elif days <= config.TLS_EXPIRY_WARN_DAYS:
            issues.append(f"The TLS certificate expires in {days} days.")

    if http["redirect_hops"] >= 4:
        issues.append(f"The URL redirects {http['redirect_hops']} times before settling.")

    return {
        "region_code": config.REGION_LABEL,
        "dns_resolved": True,
        "dns_error": None,
        "ip_addresses": ips[:5],
        "tls": tls,
        "status_code": status,
        "response_time_ms": http["response_time_ms"],
        "redirect_chain": http["chain"],
        "ip_blocked": status in (403, 451),
        "issues": issues,
    }


async def probe(url: str) -> dict[str, Any]:
    """Run the reachability checks off the event loop."""
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_probe_sync, url),
            timeout=config.REACHABILITY_TIMEOUT_S * 3,
        )
    except asyncio.TimeoutError:
        result = {
            "region_code": config.REGION_LABEL,
            "dns_resolved": None,
            "tls": {"checked": False},
            "status_code": None,
            "response_time_ms": None,
            "redirect_chain": [],
            "ip_blocked": False,
            "issues": ["Reachability checks timed out."],
        }

    result["regions_measured"] = 1
    result["regions_requested"] = 3
    result["multi_region_note"] = (
        "Measured from one host. Comparing regions to detect geo-blocking needs "
        "probes in separate regions, which this deployment does not have."
    )
    return result


def score(reach: dict[str, Any]) -> tuple[int, list[str]]:
    """0-100 for the reachability category."""
    if not reach:
        return 100, []
    notes = list(reach.get("issues") or [])
    value = 100
    if reach.get("dns_resolved") is False:
        return 0, notes
    status = reach.get("status_code")
    if status is None:
        value -= 60
    elif status in (403, 451):
        value -= 50
    elif status >= 500:
        value -= 40
    elif status >= 400:
        value -= 25

    tls = reach.get("tls") or {}
    if tls.get("valid") is False:
        value -= 40
    days = tls.get("days_remaining")
    if isinstance(days, int):
        if days < 0:
            value -= 40
        elif days <= config.TLS_EXPIRY_WARN_DAYS:
            value -= 15

    if len(reach.get("redirect_chain") or []) >= 5:
        value -= 10
    return max(0, value), notes
