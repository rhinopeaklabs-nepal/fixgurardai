"""The audit engine: one browser, three detectors, one structured result.

Detectors
---------
1. Console + page errors      -> what the site is complaining about
2. Navigation loop            -> React Router / useEffect redirect loops
3. Form silent failure        -> "Success!" shown while nothing left the browser

All three share a single page and a single network log, so a form submit is
evaluated against the same request stream the rest of the audit sees.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from playwright.async_api import Error as PWError
from playwright.async_api import async_playwright

from .. import auth_session, config
from . import (
    discovery,
    extract_js,
    extract_quality,
    extract_sitemap,
    page_audit,
    quality,
)
from .payloads import TEST_MARKER, is_sensitive, value_for

ProgressFn = Callable[..., Awaitable[None]]

THROTTLE_RE = re.compile(r"throttling navigation", re.I)

SUCCESS_RE = re.compile(
    r"thank you|thanks!|thanks for|success|successfully|"
    r"message (?:has been )?sent|we(?:'| ha)ve received|we will be in touch|"
    r"we'?ll be in touch|submitted|your (?:message|request|enquiry|inquiry|booking)"
    r"|received your|confirmation",
    re.I,
)

ERROR_TEXT_RE = re.compile(
    r"something went wrong|an error occurred|failed to send|try again later|"
    r"could not be sent|unable to submit",
    re.I,
)

ASSET_TYPES = {"image", "stylesheet", "font", "media", "script"}

# Response headers that name a bot-protection or WAF layer in front of a site.
PROTECTION_HEADERS = (
    "server", "cf-ray", "cf-mitigated", "x-sucuri-id", "x-akamai-transformed",
    "x-iinfo", "x-datadome", "x-cache", "akamai-grn",
)

_PROTECTION_SERVER = re.compile(
    r"cloudflare|sucuri|incapsula|imperva|akamai|datadome|awselb|barracuda", re.I
)
_CHALLENGE_TEXT = re.compile(
    r"just a moment|checking your browser|attention required|access denied|"
    r"cf-browser-verification|are you a robot|enable javascript and cookies",
    re.I,
)


def behind_protection(headers: dict[str, str]) -> str | None:
    """Name the protection layer that answered, if one did."""
    if not headers:
        return None
    if "cf-ray" in headers or "cf-mitigated" in headers:
        return "Cloudflare"
    server = (headers.get("server") or "").lower()
    m = _PROTECTION_SERVER.search(server)
    if m:
        return m.group(0).title()
    if "x-sucuri-id" in headers:
        return "Sucuri"
    if "x-datadome" in headers:
        return "DataDome"
    if "x-iinfo" in headers:
        return "Imperva"
    if "akamai-grn" in headers or "x-akamai-transformed" in headers:
        return "Akamai"
    return None

# Hard cap on recorded navigations; a redirect loop can emit thousands/second.
MAX_NAV_LOG = 4000

# Hosts grouped by what they are for, so a report can say "analytics" rather
# than making the reader recognise a domain.
THIRD_PARTY_KINDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"google-analytics|googletagmanager|analytics\.|plausible|"
                r"segment\.|mixpanel|hotjar|clarity\.ms|matomo|amplitude|"
                r"cloudflareinsights|heap(analytics)?\.|fullstory|posthog|"
                r"statcounter|quantserve", re.I), "analytics"),
    (re.compile(r"facebook\.|fbcdn|doubleclick|googlesyndication|adservice|"
                r"criteo|taboola|outbrain|bat\.bing|bing\.com/action|"
                r"ads\.|adnxs|pubmatic", re.I), "advertising"),
    (re.compile(r"fonts\.googleapis|fonts\.gstatic|use\.typekit|fontawesome",
                re.I), "fonts"),
    (re.compile(r"cdn\.|cdnjs|jsdelivr|unpkg|akamai|cloudfront|fastly", re.I), "cdn"),
    (re.compile(r"youtube|vimeo|wistia|cloudinary|imgix|cloudflarestream", re.I),
     "media"),
    (re.compile(r"stripe|paypal|checkout\.|braintree|razorpay", re.I), "payments"),
    (re.compile(r"recaptcha|hcaptcha|turnstile|challenges\.cloudflare", re.I),
     "bot protection"),
    (re.compile(r"intercom|crisp\.|tawk\.|zendesk|drift\.", re.I), "support chat"),
    (re.compile(r"formspree|getform|basin|web3forms|netlify", re.I), "form handling"),
]


def classify_host(host: str) -> str:
    for pattern, kind in THIRD_PARTY_KINDS:
        if pattern.search(host):
            return kind
    return "other"


DEFAULT_MODULES = ["form", "router", "assets", "reach", "a11y", "perf", "mobile"]


# --------------------------------------------------------------------------
# Collected raw signals
# --------------------------------------------------------------------------
@dataclass
class NetEvent:
    t: float
    method: str
    url: str
    resource_type: str
    status: int | None = None
    failure: str | None = None
    is_navigation: bool = False
    # Only the handful that identify a protection layer, never the whole set.
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Signals:
    console: list[dict[str, Any]] = field(default_factory=list)
    page_errors: list[dict[str, Any]] = field(default_factory=list)
    navigations: list[tuple[float, str]] = field(default_factory=list)
    network: list[NetEvent] = field(default_factory=list)


def _normalise(url: str) -> str:
    """Strip query/hash so ?retry=1 loops still register as the same URL."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def _attach(page, sig: Signals) -> None:
    def on_console(msg):
        try:
            loc = msg.location or {}
            sig.console.append(
                {
                    "severity": msg.type,
                    "message": (msg.text or "")[:1000],
                    "source_url": loc.get("url", ""),
                    "line": loc.get("lineNumber"),
                    "t": time.monotonic(),
                }
            )
        except Exception:
            pass

    def on_page_error(exc):
        text = str(exc)
        sig.page_errors.append({"message": text[:1000], "t": time.monotonic()})

    def on_nav(frame):
        # Only top-level frame navigations count toward loop detection.
        # Capped: a looping page can fire thousands per second.
        try:
            if frame.parent_frame is None and len(sig.navigations) < MAX_NAV_LOG:
                sig.navigations.append((time.monotonic(), frame.url))
        except Exception:
            pass

    def on_request(req):
        try:
            sig.network.append(
                NetEvent(
                    t=time.monotonic(),
                    method=req.method,
                    url=req.url,
                    resource_type=req.resource_type,
                    is_navigation=req.is_navigation_request(),
                )
            )
        except Exception:
            pass

    def on_response(resp):
        try:
            for ev in reversed(sig.network):
                if ev.url == resp.url and ev.status is None:
                    ev.status = resp.status
                    if resp.status >= 400:
                        h = resp.headers or {}
                        ev.headers = {
                            k: h[k][:120]
                            for k in PROTECTION_HEADERS
                            if k in h
                        }
                    break
        except Exception:
            pass

    def on_request_failed(req):
        try:
            for ev in reversed(sig.network):
                if ev.url == req.url and ev.status is None:
                    ev.failure = (req.failure or "failed")
                    break
        except Exception:
            pass

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("framenavigated", on_nav)
    page.on("request", on_request)
    page.on("response", on_response)
    page.on("requestfailed", on_request_failed)


# --------------------------------------------------------------------------
# Detector 2: navigation loop
# --------------------------------------------------------------------------
def detect_loop(sig: Signals) -> dict[str, Any]:
    throttle_hits = [
        c for c in sig.console if THROTTLE_RE.search(c.get("message", ""))
    ]

    counts: dict[str, list[float]] = {}
    for t, url in sig.navigations:
        counts.setdefault(_normalise(url), []).append(t)

    worst_url, worst_count = None, 0
    for url, times in counts.items():
        times.sort()
        # Sliding window: most navigations to this URL inside LOOP_NAV_WINDOW_S
        left = 0
        for right in range(len(times)):
            while times[right] - times[left] > config.LOOP_NAV_WINDOW_S:
                left += 1
            span = right - left + 1
            if span > worst_count:
                worst_count, worst_url = span, url

    rapid_loop = worst_count >= config.LOOP_NAV_THRESHOLD
    has_loop = rapid_loop or bool(throttle_hits)

    return {
        "has_navigation_loop": has_loop,
        "throttling_warning_detected": bool(throttle_hits),
        "throttling_messages": [c["message"] for c in throttle_hits[:5]],
        "loop_url": worst_url if rapid_loop else None,
        "loop_count": worst_count if rapid_loop else 0,
        "window_seconds": config.LOOP_NAV_WINDOW_S,
        "total_navigations": len(sig.navigations),
        "routes_seen": sorted({_normalise(u) for _, u in sig.navigations})[:25],
    }


# --------------------------------------------------------------------------
# FR-3.2: infinite re-render detection
# --------------------------------------------------------------------------
def assess_rerender(mutations: dict[str, Any]) -> dict[str, Any]:
    """Flag suspected useEffect dependency loops from DOM churn.

    A settled page mutates a handful of nodes. A component re-rendering in a
    loop produces hundreds of mutations per second with no user input.
    """
    peak = int(mutations.get("peak") or 0)
    suspected = peak >= config.MUTATION_THRESHOLD
    return {
        "suspected_infinite_rerender": suspected,
        "peak_mutations_in_window": peak,
        "window_ms": int(mutations.get("window_ms") or 2000),
        "total_mutations": int(mutations.get("total") or 0),
        "threshold": config.MUTATION_THRESHOLD,
    }


# --------------------------------------------------------------------------
# FR-3.3: console severity categories
# --------------------------------------------------------------------------
_CORS_RE = re.compile(r"cors|cross-origin|access-control-allow", re.I)
_DEPRECATION_RE = re.compile(r"deprecat|obsolete|will be removed|no longer supported", re.I)


def classify_severity(severity: str, message: str) -> str:
    """Map a raw console entry onto the SRS categories."""
    if _CORS_RE.search(message):
        return "info"
    if _DEPRECATION_RE.search(message):
        return "warning"
    if severity == "error":
        return "critical"
    if severity == "warning":
        return "warning"
    return "info"


# --------------------------------------------------------------------------
# FR-3.1: route crawl
# --------------------------------------------------------------------------
# Detector 3: form silent failure
# --------------------------------------------------------------------------
async def probe_form(
    page, sig: Signals, form_desc: dict[str, Any], test_email: str
) -> dict[str, Any]:
    idx = form_desc["index"]
    result: dict[str, Any] = {
        "form_index": idx,
        "heading": form_desc.get("heading", ""),
        "action": form_desc.get("action", ""),
        "method": form_desc.get("method", "get"),
        "field_count": form_desc.get("field_count", 0),
        "submit_text": form_desc.get("submit_text", ""),
        "filled_fields": [],
        "skipped": False,
        "skip_reason": None,
        "verdict": None,
        "severity": "info",
        "explanation": "",
        "submission_requests": [],
        "success_text_shown": False,
        "error_text_shown": False,
        "js_errors_on_submit": [],
        "navigated": False,
        "protection_detected": None,
    }

    fields = form_desc.get("fields", [])
    sensitive = [f for f in fields if is_sensitive(f)]
    if sensitive:
        result.update(
            skipped=True,
            skip_reason="credential_or_payment_field",
            verdict="skipped",
            explanation=(
                "Skipped on purpose. This form asks for a password or payment "
                "details, so FixGuard never submits it."
            ),
        )
        return result

    if not form_desc.get("has_submit"):
        result.update(
            skipped=True,
            skip_reason="no_submit_control",
            verdict="no_submit_control",
            severity="warning",
            explanation="No submit button was found, so this form cannot be sent by a visitor.",
        )
        return result

    if form_desc.get("field_count", 0) == 0:
        result.update(
            skipped=True,
            skip_reason="no_fields",
            verdict="skipped",
            explanation="Form has no input fields.",
        )
        return result

    # --- fill ------------------------------------------------------------
    for f in fields:
        if not f.get("visible") and f.get("type") != "hidden":
            continue
        if f.get("type") in {"hidden", "file"}:
            continue
        sel = f'[data-fixguard-field="{f["fid"]}"]'
        try:
            loc = page.locator(sel).first
            if f["tag"] == "select":
                opts = f.get("options") or []
                if opts:
                    await loc.select_option(opts[0]["value"], timeout=3000)
                    result["filled_fields"].append(
                        {"field": f.get("name") or f["fid"], "value": opts[0]["value"]}
                    )
                continue
            if f["type"] in {"checkbox", "radio"}:
                if f.get("required") or f["type"] == "radio":
                    await loc.check(timeout=3000, force=True)
                    result["filled_fields"].append(
                        {"field": f.get("name") or f["fid"], "value": "checked"}
                    )
                continue
            val = value_for(f, test_email)
            await loc.fill(str(val), timeout=3000)
            result["filled_fields"].append(
                {"field": f.get("name") or f["fid"], "value": str(val)}
            )
        except (PWError, asyncio.TimeoutError):
            continue

    # --- snapshot before submit -------------------------------------------
    try:
        text_before = await page.evaluate(extract_js.VISIBLE_TEXT)
    except PWError:
        text_before = ""
    url_before = page.url
    net_mark = len(sig.network)
    err_mark = len(sig.page_errors)
    t_mark = time.monotonic()

    # --- submit -----------------------------------------------------------
    try:
        await page.locator(f'[data-fixguard-submit="{idx}"]').first.click(
            timeout=5000, no_wait_after=True
        )
    except (PWError, asyncio.TimeoutError) as exc:
        result.update(
            verdict="submit_click_failed",
            severity="warning",
            explanation=f"The submit control could not be clicked: {exc}".strip()[:300],
        )
        return result

    await page.wait_for_timeout(config.POST_SUBMIT_WAIT_MS)

    # --- collect ----------------------------------------------------------
    try:
        text_after = await page.evaluate(extract_js.VISIBLE_TEXT)
    except PWError:
        text_after = text_before

    new_text = text_after.replace(text_before, "") if text_before else text_after
    # If the page re-rendered wholesale, fall back to scanning everything new.
    scan_text = new_text if new_text.strip() else text_after

    result["success_text_shown"] = bool(SUCCESS_RE.search(scan_text))
    result["error_text_shown"] = bool(ERROR_TEXT_RE.search(scan_text))
    result["navigated"] = page.url != url_before
    result["js_errors_on_submit"] = [
        e["message"] for e in sig.page_errors[err_mark:]
    ][:5]

    submissions: list[NetEvent] = []
    for ev in sig.network[net_mark:]:
        if ev.t < t_mark:
            continue
        if ev.resource_type in ASSET_TYPES and ev.method == "GET":
            continue
        if ev.method in {"POST", "PUT", "PATCH"}:
            submissions.append(ev)
        elif ev.resource_type in {"xhr", "fetch"}:
            submissions.append(ev)
        elif ev.is_navigation and _normalise(ev.url) != _normalise(url_before):
            submissions.append(ev)

    result["submission_requests"] = [
        {
            "method": e.method,
            "url": e.url[:300],
            "status": e.status,
            "resource_type": e.resource_type,
            "failure": e.failure,
        }
        for e in submissions[:10]
    ]

    failed = [
        e for e in submissions
        if (e.status is not None and e.status >= 400) or e.failure
    ]

    # A 403 from a WAF is not the same finding as a 403 from the application.
    # Cloudflare and friends routinely reject headless browsers while serving
    # real visitors perfectly, so reporting "submissions are being lost" would
    # be crying wolf on a large share of the web.
    blocker = None
    for e in failed:
        if e.status in (403, 429, 503):
            blocker = behind_protection(e.headers)
            if blocker:
                break
    if blocker and SUCCESS_RE.search(scan_text) is None:
        result["protection_detected"] = blocker

    # --- classify ---------------------------------------------------------
    if result["js_errors_on_submit"]:
        result.update(
            verdict="js_crash",
            severity="critical",
            explanation=(
                "JavaScript threw an error when the form was submitted, so the "
                "submission almost certainly never completed."
            ),
        )
    elif not submissions and result["success_text_shown"]:
        result.update(
            verdict="silent_failure",
            severity="critical",
            explanation=(
                "The page displayed a success message but the browser never sent "
                "any request. Nothing was delivered anywhere. Visitors will "
                "believe they contacted you when they did not."
            ),
        )
    elif not submissions:
        result.update(
            verdict="no_submission",
            severity="critical",
            explanation=(
                "Clicking submit produced no network request at all. The form is "
                "not wired to any backend."
            ),
        )
    elif failed and blocker:
        codes = ", ".join(str(e.status or e.failure) for e in failed[:3])
        result.update(
            verdict="blocked_by_protection",
            severity="warning",
            explanation=(
                f"The submission was rejected with {codes} by {blocker}, which "
                "sits in front of this site. That usually means automated "
                "traffic is being blocked rather than the form being broken - "
                "real visitors are probably fine. Submit the form yourself once "
                "to confirm, or allow this checker through if you want it "
                "tested end to end."
            ),
        )
    elif failed:
        codes = ", ".join(
            str(e.status or e.failure) for e in failed[:3]
        )
        result.update(
            verdict="endpoint_error",
            severity="critical",
            explanation=(
                f"The form sent its data but the server rejected it ({codes}). "
                "Submissions are being lost."
            ),
        )
    elif result["error_text_shown"]:
        result.update(
            verdict="error_shown",
            severity="warning",
            explanation="The request completed but the page displayed an error message.",
        )
    elif result["success_text_shown"] or result["navigated"]:
        result.update(
            verdict="pass",
            severity="ok",
            explanation=(
                "The form sent its data, the server accepted it, and the visitor "
                "got confirmation. Email delivery to your inbox is not verified "
                "by this check."
            ),
        )
    else:
        result.update(
            verdict="no_feedback",
            severity="warning",
            explanation=(
                "The submission was sent and accepted, but the visitor saw no "
                "confirmation. Many people will submit twice or assume it failed."
            ),
        )

    return result


# --------------------------------------------------------------------------
async def walk_site(
    page,
    entry_url: str,
    emit: Callable[..., Awaitable[None]],
    max_pages: int,
    authenticated: bool,
    seeds: list[str] | None = None,
    guessed: set[str] | None = None,
) -> dict[str, Any]:
    """Breadth-first walk of the site, visiting each page at most once.

    Every page is opened exactly once and everything wanted from it is taken in
    that visit: status, whether it is really a 404, its links, and its forms.
    An earlier version crawled links and then re-opened the same pages to audit
    them, which doubled the load count for no extra information.
    """
    origin = f"{urlparse(entry_url).scheme}://{urlparse(entry_url).netloc}"
    entry_norm = discovery.normalise(entry_url)

    queue: list[tuple[str, int]] = []
    seen: set[str] = {entry_norm}
    skipped: list[dict[str, str]] = []
    guessed = guessed or set()

    def enqueue(url: str, depth: int) -> None:
        if not discovery.same_site(url, origin) or not discovery.is_page(url):
            return
        n = discovery.normalise(url)
        if n in seen:
            return
        ok, why = auth_session.is_safe_to_follow(n, authenticated)
        if not ok:
            seen.add(n)
            skipped.append({"url": n, "reason": why or "unsafe"})
            return
        seen.add(n)
        queue.append((n, depth))

    # Links on the entry page, then anything the site declares about itself.
    try:
        for link in await page.evaluate(extract_js.EXTRACT_LINKS):
            enqueue(link, 1)
    except PWError:
        pass

    for url in seeds or []:
        enqueue(url, 1)

    routes_map: list[dict[str, Any]] = []
    broken: list[str] = []
    visited_pages: list[dict[str, Any]] = []
    session_lost = False

    while queue and len(routes_map) < max_pages - 1:
        url, depth = queue.pop(0)
        path = urlparse(url).path or "/"
        await emit(
            "routes",
            f"Page {len(routes_map) + 2} of up to {max_pages}: {path}",
        )

        # A path FixGuard invented is a probe, not a promise the site made.
        # Its 404 says nothing about the site and must not be reported as a
        # broken link.
        was_guessed = url in guessed
        entry: dict[str, Any] = {
            "path": path,
            "url": url,
            "depth": depth,
            "guessed": was_guessed,
            "status": None,
            "redirect_target": None,
            "soft_404": False,
            "ok": False,
        }

        try:
            resp = await page.goto(
                url, wait_until="domcontentloaded", timeout=config.ROUTE_TIMEOUT_MS
            )
            if resp is not None:
                entry["status"] = resp.status
                if discovery.normalise(resp.url) != discovery.normalise(url):
                    entry["redirect_target"] = resp.url
            await page.wait_for_timeout(config.RENDER_SETTLE_MS)
        except PWError as exc:
            entry["error"] = str(exc)[:160]
            routes_map.append(entry)
            if not was_guessed:
                broken.append(path)
            continue

        # A session that dies mid-walk turns everything after it into a tour of
        # the login page, so stop rather than reporting nonsense.
        if authenticated and auth_session.looks_like_login_page(page.url):
            entry["error"] = "redirected to the sign-in page"
            entry["session_lost"] = True
            routes_map.append(entry)
            session_lost = True
            break

        try:
            probe = await page.evaluate(extract_js.SOFT_404)
            entry["soft_404"] = bool(probe.get("looks_404"))
            entry["title"] = (probe.get("title") or "")[:100]
        except PWError:
            pass

        status = entry["status"] or 0
        entry["ok"] = status < 400 and not entry["soft_404"]
        if not entry["ok"] and not was_guessed:
            broken.append(path)

        # Keep discovering. A sitemap covers a marketing site; an app behind a
        # login usually has none, and its routes only exist as links.
        if entry["ok"] and len(seen) < max_pages * 6:
            try:
                for link in await page.evaluate(extract_js.EXTRACT_LINKS):
                    enqueue(link, depth + 1)
            except PWError:
                pass

        if was_guessed and not entry["ok"]:
            continue  # a guess that missed is not a finding
        routes_map.append(entry)
        visited_pages.append(entry)

    return {
        "routes_map": routes_map,
        "broken_routes_list": broken,
        "routes_crawled": len(routes_map),
        "links_discovered": len(seen),
        "queue_remaining": len(queue),
        "skipped_links": skipped,
        "session_lost": session_lost,
        "visited": visited_pages,
    }


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
async def run_audit(
    target_url: str,
    test_email: str,
    progress: ProgressFn | None = None,
    modules: list[str] | None = None,
    max_pages: int = 1,
    auth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the selected modules. Raises RuntimeError with a stable code on failure.

    ``modules`` is any subset of {"form", "router", "assets"}; empty or None
    means run everything (SRS FR-X.1).
    """
    selected = set(modules or DEFAULT_MODULES)

    async def emit(stage: str, message: str, percent: int | None = None) -> None:
        if progress:
            await progress(stage, message, percent)

    async def emit_module(name: str, summary: dict[str, Any]) -> None:
        if progress:
            await progress("module_complete", name, None, summary)

    started = time.monotonic()
    sig = Signals()
    forms_out: list[dict[str, Any]] = []
    route_data: dict[str, Any] = {
        "routes_map": [],
        "broken_routes_list": [],
        "routes_crawled": 0,
        "links_discovered": 0,
    }
    mutations: dict[str, Any] = {"peak": 0, "total": 0, "window_ms": 2000}
    load_blocked_by_loop = False
    modules_complete: list[str] = []
    a11y_raw: dict[str, Any] | None = None
    vitals_raw: dict[str, Any] | None = None
    mobile_raw: dict[str, Any] | None = None
    site_structure: dict[str, Any] | None = None
    pages_audited: list[dict[str, Any]] = []
    want_a11y = "a11y" in selected
    want_perf = "perf" in selected
    form_budget = config.MAX_FORMS_PER_AUDIT
    authenticated = bool(auth and (auth.get("cookies") or auth.get("headers")))
    auth_report: dict[str, Any] = {
        "used": authenticated,
        "verified": None,
        "detail": None,
        "skipped_links": [],
        "session_lost": False,
    }
    # Behind a login a form is as likely to change a setting as send a message,
    # so submitting is opt-in rather than the default.
    if authenticated and not (auth or {}).get("submit_forms"):
        selected.discard("form")

    async with async_playwright() as pw:
        await emit("launch", "Starting headless browser", 5)
        browser = await pw.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--js-flags=--max-old-space-size=512",
            ]
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
                    "FixGuardAI/1.0 (+site health audit)"
                ),
            )
            if authenticated:
                if auth.get("headers"):
                    await context.set_extra_http_headers(auth["headers"])
                if auth.get("cookies"):
                    await context.add_cookies(auth["cookies"])

            # Both re-arm on every navigation, including client-side routes.
            await context.add_init_script(extract_js.INSTALL_MUTATION_OBSERVER)
            if "perf" in selected:
                # Must be installed before first paint or LCP and CLS are gone.
                await context.add_init_script(extract_quality.INSTALL_VITALS)

            page = await context.new_page()
            _attach(page, sig)

            await emit("navigate", f"Loading {target_url}", 10)
            try:
                resp = await page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_LOAD_TIMEOUT_MS,
                )
            except PWError as exc:
                # A page trapped in a redirect loop never reaches
                # domcontentloaded. That is the headline finding, not an
                # unreachable target - keep the navigation evidence.
                if len(sig.navigations) >= config.LOOP_NAV_THRESHOLD:
                    load_blocked_by_loop = True
                    resp = None
                else:
                    raise RuntimeError(f"UNREACHABLE_TARGET::{exc}") from exc

            if not load_blocked_by_loop:
                if resp is None:
                    raise RuntimeError("UNREACHABLE_TARGET::no response from target")
                if resp.status >= 400:
                    raise RuntimeError(
                        f"UNREACHABLE_TARGET::target returned HTTP {resp.status}"
                    )

            if load_blocked_by_loop:
                await emit(
                    "watch", "Page is redirecting continuously - recording the loop", 40
                )
                form_descs = []
            else:
                # Let first paint finish, then zero the counters. Building the
                # DOM initially is not churn, and counting it flags every site
                # as a re-render loop.
                await page.wait_for_timeout(config.RENDER_SETTLE_MS)
                try:
                    await page.evaluate(extract_js.RESET_MUTATIONS)
                except PWError:
                    pass

                await emit("watch", "Watching console and navigation", 20)
                await page.wait_for_timeout(config.SETTLE_MS)

                # Read before FixGuard touches the DOM: extracting forms stamps
                # data attributes, which are themselves mutations.
                try:
                    mutations = await page.evaluate(extract_js.READ_MUTATIONS)
                except PWError:
                    pass

                if authenticated:
                    await emit("auth", "Checking the session was accepted", 18)
                    try:
                        title = await page.title()
                        body = await page.evaluate(extract_js.VISIBLE_TEXT)
                    except PWError:
                        title, body = "", ""
                    ok, detail = auth_session.verify(
                        page.url, title, body, auth.get("verify_text")
                    )
                    auth_report["verified"] = ok
                    auth_report["detail"] = detail
                    if not ok:
                        raise RuntimeError(f"SESSION_INVALID::{detail}")

                await emit("structure", "Mapping the site's structure", 24)
                try:
                    site_structure = await page.evaluate(
                        extract_sitemap.SITE_STRUCTURE
                    )
                except PWError:
                    site_structure = None

                if want_a11y or want_perf:
                    await emit("quality", "Checking accessibility and speed", 26)
                    q = await page_audit.collect_quality(page, want_a11y, want_perf)
                    a11y_raw, vitals_raw = q["a11y_raw"], q["vitals_raw"]

                if "form" in selected:
                    await emit("forms", "Detecting forms", 30)
                    try:
                        form_descs = await page.evaluate(extract_js.EXTRACT_FORMS)
                    except PWError:
                        form_descs = []
                else:
                    form_descs = []

            # ---- Module: forms -------------------------------------------
            if "form" in selected and not load_blocked_by_loop:
                testable = [f for f in form_descs if f.get("visible")] or form_descs
                testable = testable[:form_budget]
                form_budget -= len(testable)

                for n, desc in enumerate(testable, start=1):
                    label = (
                        desc.get("heading") or desc.get("id") or f"form {desc['index'] + 1}"
                    )
                    pct = 30 + int(25 * n / max(len(testable), 1))
                    await emit("forms", f"Testing {label} ({n}/{len(testable)})", pct)

                    if n > 1:
                        try:
                            await page.goto(
                                target_url,
                                wait_until="domcontentloaded",
                                timeout=config.PAGE_LOAD_TIMEOUT_MS,
                            )
                            await page.wait_for_timeout(1200)
                            await page.evaluate(extract_js.EXTRACT_FORMS)
                        except PWError:
                            break

                    try:
                        forms_out.append(
                            await probe_form(page, sig, desc, test_email)
                        )
                    except PWError as exc:
                        forms_out.append(
                            {
                                "form_index": desc["index"],
                                "verdict": "probe_error",
                                "severity": "warning",
                                "explanation": f"Form could not be tested: {exc}"[:300],
                                "skipped": True,
                            }
                        )

                modules_complete.append("form")
                await emit_module(
                    "form",
                    {
                        "forms_tested": len(forms_out),
                        "critical": sum(
                            1 for f in forms_out if f.get("severity") == "critical"
                        ),
                    },
                )

            # ---- Module: router ------------------------------------------
            if "router" in selected and not load_blocked_by_loop:
                await emit("routes", "Looking for a sitemap", 55)
                origin = f"{urlparse(target_url).scheme}://{urlparse(target_url).netloc}"
                declared = await discovery.from_sitemap(origin)
                seeds = list(declared["urls"])
                guessed: set[str] = set()
                discovery_sources = list(declared["sources"])
                if "page links" not in discovery_sources:
                    discovery_sources.append("page links")

                # How many internal pages does this page actually link to?
                try:
                    entry_links = {
                        discovery.normalise(u)
                        for u in await page.evaluate(extract_js.EXTRACT_LINKS)
                        if discovery.same_site(u, origin) and discovery.is_page(u)
                    }
                except PWError:
                    entry_links = set()

                # Guessing is a last resort. A site that links its own pages has
                # already told us where they are, and probing invented paths
                # just spends the page budget on 404s.
                if not seeds and len(entry_links) < 3:
                    guessed = set(discovery.guesses(origin))
                    seeds = list(guessed)
                    discovery_sources.append("common paths")

                await emit(
                    "routes",
                    f"Following {len(entry_links)} link(s) from this page"
                    + (f" plus {len(declared['urls'])} from the sitemap"
                       if declared["urls"] else ""),
                    58,
                )
                try:
                    if page.url != target_url:
                        await page.goto(
                            target_url,
                            wait_until="domcontentloaded",
                            timeout=config.PAGE_LOAD_TIMEOUT_MS,
                        )
                        await page.wait_for_timeout(800)
                    route_data = await walk_site(
                        page,
                        target_url,
                        lambda st, m: emit(st, m, None),
                        max(max_pages, config.MAX_ROUTES_CRAWL + 1),
                        authenticated,
                        seeds,
                        guessed,
                    )
                    route_data["discovery_sources"] = discovery_sources
                    route_data["declared_routes"] = len(declared["urls"])
                    auth_report["skipped_links"] = route_data.get("skipped_links") or []
                    if route_data.get("session_lost"):
                        auth_report["session_lost"] = True
                except PWError:
                    pass

            if "router" in selected:
                modules_complete.append("router")
                await emit_module(
                    "router",
                    {
                        "routes_crawled": route_data["routes_crawled"],
                        "broken": len(route_data["broken_routes_list"]),
                    },
                )

            # ---- Per-page checks on what the walk found -------------------
            if max_pages > 1 and not load_blocked_by_loop:
                for sub in (route_data.get("visited") or [])[: max_pages - 1]:
                    if not sub.get("ok"):
                        continue
                    await emit("pages", f"Checking {sub['path']}", 80)
                    try:
                        await page.goto(
                            sub["url"],
                            wait_until="domcontentloaded",
                            timeout=config.ROUTE_TIMEOUT_MS,
                        )
                        await page.wait_for_timeout(config.RENDER_SETTLE_MS)
                    except PWError:
                        continue

                    q = await page_audit.collect_quality(page, want_a11y, want_perf)

                    sub_forms: list[dict[str, Any]] = []
                    if "form" in selected and form_budget > 0:
                        try:
                            descs = await page.evaluate(extract_js.EXTRACT_FORMS)
                        except PWError:
                            descs = []
                        for desc in descs[:form_budget]:
                            try:
                                r = await probe_form(page, sig, desc, test_email)
                                r["page_url"] = sub["url"]
                                sub_forms.append(r)
                                forms_out.append(r)
                            except PWError:
                                break
                        form_budget -= len(sub_forms)

                    pages_audited.append(
                        {
                            "url": sub["url"],
                            "path": sub["path"],
                            "status": sub.get("status"),
                            "title": sub.get("title"),
                            "forms_tested": len(sub_forms),
                            "a11y": quality.assess_a11y(q.get("a11y_raw")),
                            "performance": quality.assess_vitals(q.get("vitals_raw")),
                        }
                    )
                if pages_audited:
                    modules_complete.append("pages")
                    await emit_module("pages", {"pages": len(pages_audited) + 1})

            # ---- Module: mobile layout -----------------------------------
            if "mobile" in selected and not load_blocked_by_loop:
                await emit("mobile", "Checking the layout on a phone", 85)
                mobile_raw = await page_audit.audit_mobile(
                    browser.new_context, target_url
                )
                modules_complete.append("mobile")
                await emit_module(
                    "mobile",
                    {"issues": len((mobile_raw or {}).get("issues") or [])},
                )

            if want_a11y:
                modules_complete.append("a11y")
                await emit_module(
                    "a11y", {"issues": len((a11y_raw or {}).get("issues") or [])}
                )
            if want_perf:
                modules_complete.append("perf")
                await emit_module("perf", {"lcp_ms": (vitals_raw or {}).get("lcp_ms")})

            if "assets" in selected:
                modules_complete.append("assets")

            await emit("analyse", "Analysing results", 90)
        finally:
            await browser.close()

    # Every host the page actually contacted, grouped by what it is for. This
    # comes from observed requests, not from scanning the HTML for known names.
    hosts: dict[str, dict[str, Any]] = {}
    entry_host = urlparse(target_url).hostname or ""
    for ev in sig.network:
        h = urlparse(ev.url).hostname
        if not h:
            continue
        entry = hosts.setdefault(
            h,
            {
                "host": h,
                "first_party": h == entry_host,
                "kind": "first party" if h == entry_host else classify_host(h),
                "requests": 0,
                "resource_types": {},
                "failed": 0,
            },
        )
        entry["requests"] += 1
        entry["resource_types"][ev.resource_type] = (
            entry["resource_types"].get(ev.resource_type, 0) + 1
        )
        if (ev.status is not None and ev.status >= 400) or ev.failure:
            entry["failed"] += 1

    third_party = sorted(
        (h for h in hosts.values() if not h["first_party"]),
        key=lambda h: -h["requests"],
    )

    site_map = {
        "measured": bool(site_structure),
        **(site_structure or {}),
        "hosts": sorted(hosts.values(), key=lambda h: (not h["first_party"], -h["requests"])),
        "third_party_count": len(third_party),
        "third_party_kinds": sorted({h["kind"] for h in third_party}),
        "total_requests": len(sig.network),
    }

    router = detect_loop(sig)
    router["page_load_blocked_by_loop"] = load_blocked_by_loop
    if load_blocked_by_loop:
        router["has_navigation_loop"] = True
    router.update(route_data)
    router["rerender"] = assess_rerender(mutations)

    console_errors = [
        {
            "severity": classify_severity(c["severity"], c["message"]),
            "raw_severity": c["severity"],
            "message": c["message"],
            "source_url": c["source_url"],
            "line": c["line"],
        }
        for c in sig.console
        if c["severity"] in {"error", "warning"}
    ]
    for pe in sig.page_errors:
        console_errors.append(
            {
                "severity": "critical",
                "raw_severity": "error",
                "message": pe["message"],
                "source_url": "",
                "line": None,
            }
        )

    asset_issues = [
        {
            "url": e.url[:300],
            "resource_type": e.resource_type,
            "status": e.status,
            "failure": e.failure,
        }
        for e in sig.network
        if e.resource_type in ASSET_TYPES
        and ((e.status is not None and e.status >= 400) or e.failure)
    ][:25]

    return {
        "target_url": target_url,
        "site_map": site_map,
        # Only the shape of the session is recorded. Cookie values never
        # reach the database, the API response, or a shared report.
        "auth": {
            **auth_report,
            **auth_session.redact(
                (auth or {}).get("cookies"), (auth or {}).get("headers")
            ),
        },
        "accessibility": quality.assess_a11y(a11y_raw),
        "performance": quality.assess_vitals(vitals_raw),
        "mobile": quality.assess_mobile(mobile_raw),
        "pages": pages_audited,
        "pages_audited": len(pages_audited) + 1,
        "modules_selected": sorted(selected),
        "modules_complete": modules_complete,
        "console_errors": console_errors[:100],
        "router_result": router,
        "form_results": forms_out,
        "asset_issues": asset_issues,
        "forms_found": len(forms_out),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "test_marker": TEST_MARKER,
    }


# --------------------------------------------------------------------------
# Module 1: pull styling context for the surgical prompt engine
# --------------------------------------------------------------------------
async def extract_style_context(page_url: str) -> dict[str, Any]:
    """Open a page and return its candidate elements plus global styling."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
                ignore_https_errors=True,
            )
            page = await context.new_page()
            try:
                resp = await page.goto(
                    page_url,
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_LOAD_TIMEOUT_MS,
                )
            except PWError as exc:
                raise RuntimeError(f"UNREACHABLE_TARGET::{exc}") from exc
            if resp is None or resp.status >= 400:
                status = resp.status if resp else "no response"
                raise RuntimeError(f"UNREACHABLE_TARGET::target returned {status}")

            await page.wait_for_timeout(config.RENDER_SETTLE_MS)
            try:
                return await page.evaluate(extract_js.EXTRACT_STYLE_CONTEXT)
            except PWError as exc:
                raise RuntimeError(f"WORKER_CRASH::{exc}") from exc
        finally:
            await browser.close()
