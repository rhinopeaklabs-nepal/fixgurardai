"""Finding every route on a site, not just the ones linked from one page.

Three sources, cheapest first:

1. ``/sitemap.xml`` and whatever ``robots.txt`` points at. A site that publishes
   one has already answered the question, and fetching it costs a single HTTP
   request rather than a browser page load.
2. Links found on each page as it is visited, which is how anything without a
   sitemap gets covered.
3. A short list of paths that exist on most applications, tried only when the
   first two found almost nothing.

Sitemaps are treated as hints, never as truth: an entry is only reported once a
browser has actually opened it, because sitemaps routinely list pages that were
deleted years ago.
"""
from __future__ import annotations

import asyncio
import re
import urllib.error
import urllib.request
from typing import Iterable
from urllib.parse import urljoin, urlparse

from .. import config

# Files a crawler should never open as a page.
NON_PAGE = re.compile(
    r"\.(pdf|zip|rar|gz|tar|jpe?g|png|gif|svg|webp|ico|mp[34]|mov|avi|"
    r"docx?|xlsx?|pptx?|csv|txt|xml|json|rss|atom|css|js|woff2?|ttf|eot)$",
    re.I,
)

# Paths worth trying when a site publishes no sitemap and links few pages.
COMMON_PATHS = (
    "/about", "/contact", "/pricing", "/products", "/services", "/blog",
    "/faq", "/terms", "/privacy", "/shop", "/menu", "/gallery", "/book",
)

_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_SITEMAP_DIRECTIVE = re.compile(r"^\s*sitemap:\s*(\S+)", re.I | re.M)


def normalise(url: str) -> str:
    """Strip query, fragment and trailing slash so one page is one entry."""
    p = urlparse(url)
    path = (p.path or "/").rstrip("/") or "/"
    return f"{p.scheme}://{p.netloc}{path}"


def same_site(url: str, origin: str) -> bool:
    try:
        a, b = urlparse(url), urlparse(origin)
    except ValueError:
        return False
    return a.scheme in {"http", "https"} and a.netloc == b.netloc


def is_page(url: str) -> bool:
    return not NON_PAGE.search(urlparse(url).path or "")


def _fetch(url: str, timeout: int) -> str | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FixGuardAI/1.0 (+site health audit)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status >= 400:
                return None
            # A sitemap index can be large; a few hundred KB is plenty.
            return r.read(600_000).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _sync_discover(origin: str, timeout: int) -> tuple[list[str], list[str]]:
    """Return (urls, sources_used)."""
    found: list[str] = []
    sources: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not same_site(u, origin) or not is_page(u):
            return
        n = normalise(u)
        if n not in seen:
            seen.add(n)
            found.append(n)

    candidates = [urljoin(origin, "/sitemap.xml")]

    robots = _fetch(urljoin(origin, "/robots.txt"), timeout)
    if robots:
        declared = _SITEMAP_DIRECTIVE.findall(robots)
        if declared:
            sources.append("robots.txt")
            candidates = declared + candidates

    # Follow one level of sitemap index, which is how large sites split them.
    queue = list(dict.fromkeys(candidates))[:5]
    nested_budget = 3

    while queue and len(found) < 400:
        sm = queue.pop(0)
        body = _fetch(sm, timeout)
        if not body:
            continue
        locs = _LOC.findall(body)
        if not locs:
            continue
        if "sitemap.xml" in sm or "<sitemapindex" in body[:400].lower():
            if "sitemap" not in sources:
                sources.append("sitemap.xml")
        for loc in locs:
            if loc.lower().endswith(".xml") and nested_budget > 0:
                nested_budget -= 1
                queue.append(loc)
            else:
                add(loc)

    return found, sources


async def from_sitemap(origin: str) -> dict:
    """Routes a site declares about itself."""
    try:
        urls, sources = await asyncio.wait_for(
            asyncio.to_thread(_sync_discover, origin, config.REACHABILITY_TIMEOUT_S),
            timeout=config.REACHABILITY_TIMEOUT_S * 2,
        )
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        urls, sources = [], []
    return {"urls": urls, "sources": sources}


def guesses(origin: str) -> Iterable[str]:
    """Paths worth trying when a site declares nothing and links little."""
    for path in COMMON_PATHS:
        yield normalise(urljoin(origin, path))
