"""Per-page checks, factored out so a multi-page scan reuses them exactly.

Everything here runs against an already-navigated page, so one visit feeds
every detector rather than loading the site once per check.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Error as PWError

from .. import config
from . import extract_js, extract_quality


async def collect_quality(page, want_a11y: bool, want_perf: bool) -> dict[str, Any]:
    """Accessibility and performance for the page currently loaded."""
    out: dict[str, Any] = {"a11y_raw": None, "vitals_raw": None}

    if want_a11y:
        try:
            out["a11y_raw"] = await page.evaluate(extract_quality.A11Y_AUDIT)
        except PWError:
            pass

    if want_perf:
        try:
            out["vitals_raw"] = await page.evaluate(extract_quality.READ_VITALS)
        except PWError:
            pass

    return out


async def audit_mobile(context_factory, url: str) -> dict[str, Any] | None:
    """Reload the page at phone width and check the layout.

    A separate context rather than a viewport resize: some sites branch on the
    user agent at load time, so resizing an already-loaded desktop page would
    measure the desktop layout squeezed, not the mobile layout.
    """
    context = await context_factory(
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1 FixGuardAI/1.0"
        ),
    )
    try:
        page = await context.new_page()
        try:
            resp = await page.goto(
                url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS
            )
        except PWError:
            return None
        if resp is None or resp.status >= 400:
            return None
        await page.wait_for_timeout(config.RENDER_SETTLE_MS)
        try:
            return await page.evaluate(extract_quality.MOBILE_AUDIT)
        except PWError:
            return None
    finally:
        await context.close()


async def audit_subpage(
    page,
    url: str,
    want_a11y: bool,
    want_perf: bool,
) -> dict[str, Any] | None:
    """Load one additional page and run the non-destructive checks on it."""
    try:
        resp = await page.goto(
            url, wait_until="domcontentloaded", timeout=config.ROUTE_TIMEOUT_MS
        )
    except PWError as exc:
        return {"url": url, "error": str(exc)[:160], "status": None}

    status = resp.status if resp else None
    await page.wait_for_timeout(config.RENDER_SETTLE_MS)

    quality = await collect_quality(page, want_a11y, want_perf)
    try:
        forms = await page.evaluate(extract_js.EXTRACT_FORMS)
    except PWError:
        forms = []

    return {
        "url": url,
        "status": status,
        "forms_found": len(forms),
        "form_descs": forms,
        **quality,
    }
