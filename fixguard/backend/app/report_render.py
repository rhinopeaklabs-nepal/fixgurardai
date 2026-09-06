"""FR-4.2 PDF certificate and FR-4.4 badge widget.

The SRS specifies Puppeteer in its own container. Playwright's Chromium is
already installed and running here, and `page.pdf()` is the same underlying
CDP call, so a second browser would be pure overhead on a 1 vCPU box.
"""
from __future__ import annotations

import datetime as dt
import html
import json
from typing import Any

from playwright.async_api import async_playwright

from . import config

GRADE_STYLE = {
    "verified_healthy": ("#0a8f4d", "Verified Healthy", "A"),
    "minor_issues": ("#0a8f4d", "Minor Issues", "B"),
    "needs_attention": ("#b45309", "Needs Attention", "C"),
    "critical": ("#b91c1c", "Critical", "F"),
}

VERDICT_LABEL = {
    "silent_failure": "Silent failure: success shown, nothing sent",
    "no_submission": "Form is not connected to a backend",
    "js_crash": "JavaScript crashed on submit",
    "endpoint_error": "Server rejected the submission",
    "error_shown": "Error message shown to the visitor",
    "no_feedback": "Works, but gives the visitor no confirmation",
    "no_submit_control": "No submit button found",
    "submit_click_failed": "Submit button could not be clicked",
    "probe_error": "Could not be tested",
    "skipped": "Skipped by design",
    "pass": "Working correctly",
}


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""))


SEV_COLOUR = {"critical": "#b91c1c", "warning": "#b45309", "info": "#6b7280"}


def _finding(sev: str, title: str, body: str, where: str, evidence: list[str]) -> str:
    """One finding, with the evidence that produced it.

    A certificate that only says "form failed" cannot be acted on or argued
    with; the observation is what makes it either.
    """
    colour = SEV_COLOUR.get(sev, SEV_COLOUR["info"])
    ev = ""
    if evidence:
        ev = "<div class='ev'>" + "<br>".join(evidence) + "</div>"
    return (
        f"<div class='finding' style='border-left-color:{colour}'>"
        f"<div class='f-head'><span class='f-sev' style='color:{colour}'>{sev}</span>"
        f"<span class='f-title'>{title}</span></div>"
        f"<div class='f-body'>{body}</div>"
        f"<div class='f-where'>{where}</div>{ev}</div>"
    )


def _check_row(label: str, ok: bool | None, detail: str = "") -> str:
    if ok is None:
        mark, colour = "&ndash;", "#9ca3af"
    elif ok:
        mark, colour = "&#10003;", "#0a8f4d"
    else:
        mark, colour = "&#10007;", "#b91c1c"
    return (
        f'<tr><td class="mark" style="color:{colour}">{mark}</td>'
        f"<td>{_esc(label)}</td>"
        f'<td class="detail">{_esc(detail)}</td></tr>'
    )


def build_html(run: dict[str, Any]) -> str:
    sb = run.get("score_breakdown") or {}
    grade = run.get("grade") or "critical"
    colour, label, letter = GRADE_STYLE.get(grade, GRADE_STYLE["critical"])
    score = run.get("health_score")
    forms = run.get("form_results") or []
    router = run.get("router_result") or {}
    rerender = router.get("rerender") or {}
    reach = run.get("reachability") or {}
    tls = reach.get("tls") or {}
    console_errors = run.get("console_errors") or []
    critical_errors = [c for c in console_errors if c.get("severity") == "critical"]
    assets = run.get("asset_issues") or []

    rows: list[str] = []
    if forms:
        for f in forms:
            v = f.get("verdict")
            rows.append(
                _check_row(
                    f"Form: {f.get('heading') or f.get('submit_text') or 'untitled'}",
                    v == "pass" if not f.get("skipped") else None,
                    VERDICT_LABEL.get(v, v or ""),
                )
            )
    else:
        rows.append(_check_row("Forms", None, "No forms found on this page"))

    rows.append(
        _check_row(
            "No redirect loops",
            not router.get("has_navigation_loop"),
            f"{router.get('total_navigations', 0)} navigation(s) observed",
        )
    )
    rows.append(
        _check_row(
            "Rendering settles",
            not rerender.get("suspected_infinite_rerender"),
            f"peak {rerender.get('peak_mutations_in_window', 0)} DOM changes per "
            f"{rerender.get('window_ms', 2000)}ms",
        )
    )
    broken = router.get("broken_routes_list") or []
    rows.append(
        _check_row(
            "Internal links resolve",
            not broken,
            f"{len(broken)} broken of {router.get('routes_crawled', 0)} checked"
            if router.get("routes_crawled")
            else "not checked",
        )
    )
    rows.append(
        _check_row(
            "No JavaScript errors",
            not critical_errors,
            f"{len(critical_errors)} error(s) logged",
        )
    )
    rows.append(
        _check_row("All assets load", not assets, f"{len(assets)} failed to load")
    )
    if reach:
        rows.append(
            _check_row(
                "DNS resolves", reach.get("dns_resolved"), ", ".join(reach.get("ip_addresses") or [])[:60]
            )
        )
        if tls.get("checked"):
            days = tls.get("days_remaining")
            rows.append(
                _check_row(
                    "TLS certificate valid",
                    tls.get("valid"),
                    f"expires in {days} days" if isinstance(days, int) else (tls.get("error") or ""),
                )
            )
        rows.append(
            _check_row(
                "Site reachable",
                reach.get("status_code") is not None and reach["status_code"] < 400,
                f"HTTP {reach.get('status_code')} in {reach.get('response_time_ms')}ms",
            )
        )

    bars = ""
    for key, name in (
        ("form", "Forms"), ("router", "Navigation &amp; console"),
        ("geo", "Reachability"), ("assets", "Assets"),
    ):
        b = (sb.get("breakdown") or {}).get(key) or {}
        if not b.get("measured"):
            continue
        val = b.get("score", 0)
        bar_colour = "#0a8f4d" if val >= 80 else "#b45309" if val >= 55 else "#b91c1c"
        bars += (
            f'<div class="bar-row"><span class="bar-label">{name} '
            f'<em>({b.get("weight")}%)</em></span>'
            f'<span class="bar-track"><span class="bar-fill" '
            f'style="width:{val}%;background:{bar_colour}"></span></span>'
            f'<span class="bar-val">{val}</span></div>'
        )

    generated = dt.datetime.now(dt.timezone.utc).strftime("%d %B %Y")
    summary = run.get("executive_summary") or ""

    # ---- pages actually visited ------------------------------------------
    routes = router.get("routes_map") or []
    page_scores = {p.get("url"): p for p in (run.get("pages") or [])}

    route_rows = ""
    if routes:
        entry_a11y = (run.get("accessibility") or {}).get("score")
        entry_perf = (run.get("performance") or {}).get("score")
        entry_forms = len([f for f in forms if not f.get("page_url")])
        route_rows += (
            '<tr><td class="p">/</td>'
            '<td class="c ok">200</td>'
            f'<td class="c">{entry_forms or "&ndash;"}</td>'
            f'<td class="c">{entry_a11y if entry_a11y is not None else "&ndash;"}</td>'
            f'<td class="c">{entry_perf if entry_perf is not None else "&ndash;"}</td>'
            '<td class="note">entry page</td></tr>'
        )
        for r in routes:
            pg = page_scores.get(r.get("url")) or {}
            ok = r.get("ok")
            status = r.get("status")
            status_txt = status if status is not None else "no reply"
            note = ""
            if r.get("soft_404"):
                note = "renders &ldquo;not found&rdquo;"
            elif r.get("redirect_target"):
                note = "redirected"
            elif r.get("error"):
                note = _esc(r["error"])[:48]
            elif r.get("title"):
                note = _esc(r["title"])[:48]
            a11y = (pg.get("a11y") or {}).get("score")
            perf = (pg.get("performance") or {}).get("score")
            route_rows += (
                f'<tr><td class="p">{_esc(r.get("path"))}</td>'
                f'<td class="c {"ok" if ok else "bad"}">{status_txt}</td>'
                f'<td class="c">{pg.get("forms_tested") if pg else "&ndash;"}</td>'
                f'<td class="c">{a11y if a11y is not None else "&ndash;"}</td>'
                f'<td class="c">{perf if perf is not None else "&ndash;"}</td>'
                f'<td class="note">{note}</td></tr>'
            )

    discovery_line = ""
    if router.get("discovery_sources"):
        found = router.get("links_discovered") or 0
        crawled = router.get("routes_crawled") or 0
        left = router.get("queue_remaining") or 0
        discovery_line = (
            f"Found {found} address(es) via "
            f"{', '.join(router['discovery_sources'])}; opened {crawled + 1}."
        )
        if left:
            discovery_line += f" {left} more were found but not opened."

    # ---- every finding, with what was observed ---------------------------
    detail_blocks = ""

    for f in forms:
        if f.get("verdict") in {"pass", "skipped"} and not f.get("skipped"):
            continue
        sev = f.get("severity") or "info"
        label = f.get("heading") or f.get("submit_text") or "Untitled form"
        where = f.get("page_url") or run.get("target_url")
        evidence = []
        for r in (f.get("submission_requests") or [])[:3]:
            evidence.append(
                f"{r.get('method')} {r.get('status') or r.get('failure') or 'pending'} "
                f"{(r.get('url') or '')[:80]}"
            )
        if not evidence and f.get("verdict") in {"silent_failure", "no_submission"}:
            evidence.append("No network request was made at all.")
        detail_blocks += _finding(
            sev,
            f"Form: {_esc(label)}",
            _esc(f.get("explanation") or ""),
            _esc(where),
            evidence,
        )

    if router.get("has_navigation_loop"):
        detail_blocks += _finding(
            "critical", "Redirect loop",
            "The page navigates to the same address repeatedly and never settles.",
            _esc(router.get("loop_url") or run.get("target_url")),
            [f"{router.get('loop_count')} navigations within "
             f"{router.get('window_seconds')} seconds"],
        )

    rr = router.get("rerender") or {}
    if rr.get("suspected_infinite_rerender"):
        detail_blocks += _finding(
            "critical", "Infinite re-render",
            "The page keeps changing its own content with no user input.",
            _esc(run.get("target_url")),
            [f"{rr.get('peak_mutations_in_window')} DOM changes per "
             f"{rr.get('window_ms')}ms (threshold {rr.get('threshold')})"],
        )

    if broken:
        detail_blocks += _finding(
            "warning", f"{len(broken)} link(s) lead nowhere",
            "Visitors clicking these reach a dead page.",
            _esc(run.get("target_url")),
            [_esc(b) for b in broken[:8]],
        )

    for c in critical_errors[:4]:
        loc = c.get("source_url") or ""
        if loc and c.get("line") is not None:
            loc = f"{loc}:{c['line']}"
        detail_blocks += _finding(
            "warning", "JavaScript error",
            _esc((c.get("message") or "")[:180]),
            _esc(loc or run.get("target_url")),
            [],
        )

    if assets:
        detail_blocks += _finding(
            "warning", f"{len(assets)} file(s) failed to load",
            "Images, styles or scripts the page asked for did not arrive.",
            _esc(run.get("target_url")),
            [f"{a.get('status') or a.get('failure')} &mdash; {_esc(a.get('url'))[:76]}"
             for a in assets[:6]],
        )

    for group in ((run.get("accessibility") or {}).get("groups") or [])[:4]:
        detail_blocks += _finding(
            "warning" if group.get("impact") != "critical" else "critical",
            f"Accessibility: {_esc(group.get('rule'))}",
            _esc(group.get("message") or ""),
            f"{group.get('count')} occurrence(s)",
            [_esc(e.get("selector")) for e in (group.get("examples") or [])[:3]
             if e.get("selector")],
        )

    for group in ((run.get("mobile") or {}).get("groups") or [])[:4]:
        detail_blocks += _finding(
            "warning" if group.get("impact") != "critical" else "critical",
            f"Mobile: {_esc(group.get('rule'))}",
            _esc(group.get("message") or ""),
            f"{group.get('count')} occurrence(s)",
            [_esc(e.get("selector")) for e in (group.get("examples") or [])[:3]
             if e.get("selector")],
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
          color: #111827; font-size: 11pt; margin: 0; }}
  .head {{ display:flex; justify-content:space-between; align-items:flex-start;
           border-bottom:3px solid #0055FF; padding-bottom:12px; }}
  .brand {{ font-size:20pt; font-weight:800; color:#0055FF; letter-spacing:-.5px; }}
  .sub {{ color:#6b7280; font-size:9pt; margin-top:2px; }}
  .meta {{ text-align:right; font-size:9pt; color:#6b7280; }}
  .hero {{ display:flex; gap:24px; align-items:center; margin:22px 0 6px; }}
  .score {{ width:110px; height:110px; border-radius:50%; border:9px solid {colour};
            display:flex; align-items:center; justify-content:center;
            font-size:34pt; font-weight:800; color:{colour}; }}
  .grade {{ font-size:30pt; font-weight:800; color:{colour}; line-height:1; }}
  .glabel {{ font-size:12pt; font-weight:600; margin-top:4px; }}
  .url {{ font-size:11pt; color:#374151; margin-top:6px; word-break:break-all; }}
  h2 {{ font-size:10pt; text-transform:uppercase; letter-spacing:.08em;
        color:#6b7280; margin:22px 0 8px; }}
  .summary {{ background:#f3f4f6; border-radius:8px; padding:12px 14px;
              font-size:10.5pt; line-height:1.55; }}
  .bar-row {{ display:flex; align-items:center; gap:10px; margin-bottom:7px;
              font-size:9.5pt; }}
  .bar-label {{ width:170px; color:#374151; }}
  .bar-label em {{ color:#9ca3af; font-style:normal; }}
  .bar-track {{ flex:1; height:7px; background:#e5e7eb; border-radius:4px; }}
  .bar-fill {{ display:block; height:7px; border-radius:4px; }}
  .bar-val {{ width:28px; text-align:right; font-weight:600; color:#4b5563; }}
  table {{ width:100%; border-collapse:collapse; font-size:10pt; }}
  td {{ padding:6px 4px; border-bottom:1px solid #f0f1f3; vertical-align:top; }}
  td.mark {{ width:20px; font-weight:800; }}
  td.detail {{ color:#6b7280; text-align:right; font-size:9pt; }}
  .note {{ margin-top:8px; font-size:8.5pt; color:#9ca3af; line-height:1.5; }}
  table.routes {{ width:100%; border-collapse:collapse; font-size:8.5pt;
                 margin-top:4px; }}
  table.routes th {{ text-align:left; padding:4px 6px; background:#f3f4f6;
                    color:#6b7280; font-size:7.5pt; text-transform:uppercase;
                    letter-spacing:.06em; border-bottom:1px solid #e5e7eb; }}
  table.routes td {{ padding:4px 6px; border-bottom:1px solid #f3f4f6;
                    vertical-align:top; }}
  table.routes td.p {{ font-family:ui-monospace,monospace; color:#111827; }}
  table.routes td.c {{ text-align:center; width:52px; }}
  table.routes td.c.ok {{ color:#0a6b3d; }}
  table.routes td.c.bad {{ color:#b91c1c; font-weight:600; }}
  table.routes td.note {{ color:#6b7280; font-size:8pt; }}
  .disc {{ font-size:8.5pt; color:#6b7280; margin-bottom:2px; }}

  .finding {{ border-left:3px solid #9ca3af; background:#fafafa;
             padding:7px 10px; margin-bottom:6px; page-break-inside:avoid; }}
  .f-head {{ display:flex; gap:8px; align-items:baseline; }}
  .f-sev {{ font-size:7.5pt; text-transform:uppercase; font-weight:700;
           letter-spacing:.06em; }}
  .f-title {{ font-weight:600; font-size:9.5pt; color:#111827; }}
  .f-body {{ font-size:9pt; color:#374151; margin-top:2px; }}
  .f-where {{ font-family:ui-monospace,monospace; font-size:7.5pt;
             color:#9ca3af; margin-top:3px; word-break:break-all; }}
  .ev {{ font-family:ui-monospace,monospace; font-size:7.5pt; color:#4b5563;
        background:#f3f4f6; padding:4px 6px; margin-top:4px; border-radius:3px;
        word-break:break-all; }}

  /* Static, not fixed: the certificate now runs to several pages, and a fixed
     footer sits on top of whatever flows underneath it. */
  footer {{ margin-top:18px; font-size:8pt; color:#9ca3af;
            border-top:1px solid #e5e7eb; padding-top:6px; }}
</style></head><body>
  <div class="head">
    <div><div class="brand">FixGuard AI</div>
      <div class="sub">Site Health Verification Certificate</div></div>
    <div class="meta">Issued {generated}<br>Report {_esc(run.get('id', ''))[:8]}</div>
  </div>

  <div class="hero">
    <div class="score">{score if score is not None else '--'}</div>
    <div>
      <div class="grade">{letter}</div>
      <div class="glabel" style="color:{colour}">{label}</div>
      <div class="url">{_esc(run.get('target_url'))}</div>
    </div>
  </div>

  {'<h2>Summary</h2><div class="summary">' + _esc(summary) + '</div>' if summary else ''}

  <h2>Score breakdown</h2>
  {bars}

  <h2>Checks performed</h2>
  <table>{''.join(rows)}</table>

  {f'<h2>Pages audited ({len(routes) + 1})</h2>'
   f'<p class="disc">{discovery_line}</p>'
   '<table class="routes"><thead><tr><th>Path</th><th>Status</th>'
   '<th>Forms</th><th>A11y</th><th>Speed</th><th></th></tr></thead>'
   f'<tbody>{route_rows}</tbody></table>' if route_rows else ''}

  {f'<h2>Findings in detail</h2>{detail_blocks}' if detail_blocks else ''}

  <p class="note">
    Form checks confirm that a submission leaves the browser and is accepted by
    the receiving server. Delivery to a specific mailbox is not verified.
    Reachability was measured from {_esc(reach.get('regions_measured', 1))} region;
    cross-region blocking is not covered by this report.
  </p>

  <footer>Generated by FixGuard AI &middot; {_esc(config.PUBLIC_BASE_URL)}</footer>
</body></html>"""


async def render_pdf(run: dict[str, Any]) -> bytes:
    """Render the certificate. Uses the Chromium that is already installed."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        try:
            page = await browser.new_page()
            await page.set_content(build_html(run), wait_until="load")
            return await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            await browser.close()


# --------------------------------------------------------------------------
# FR-4.4 badge widget
# --------------------------------------------------------------------------
def badge_svg(score: int | None, grade: str) -> str:
    colour, label, letter = GRADE_STYLE.get(grade, GRADE_STYLE["critical"])
    shown = str(score) if score is not None else "--"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="188" height="40" role="img"
     aria-label="FixGuard AI verified: {shown} out of 100, {label}">
  <rect width="188" height="40" rx="8" fill="#0d1117"/>
  <text x="12" y="17" font-family="system-ui,sans-serif" font-size="9"
        fill="#8b949e" letter-spacing="1.2">VERIFIED BY</text>
  <text x="12" y="31" font-family="system-ui,sans-serif" font-size="13"
        font-weight="700" fill="#ffffff">FixGuard AI</text>
  <rect x="126" y="6" width="54" height="28" rx="6" fill="{colour}"/>
  <text x="153" y="25" font-family="system-ui,sans-serif" font-size="14"
        font-weight="800" fill="#ffffff" text-anchor="middle">{shown}</text>
</svg>"""


def badge_script(token: str) -> str:
    """A single <script src> tag the user pastes into their site footer.

    The badge fetches the latest score on load, so re-running an audit updates
    every embedded badge without the user touching their site again (FR-4.4).
    """
    api = f"{config.PUBLIC_BASE_URL}"
    return f"""(function () {{
  var TOKEN = {json.dumps(token)};
  var REPORT = {json.dumps(api)} + "/r/" + TOKEN;
  var API = {json.dumps(config.API_PUBLIC_URL)} + "/api/v1/public/badge/" + TOKEN + ".json";

  var script = document.currentScript;
  var host = document.createElement("a");
  host.href = REPORT;
  host.target = "_blank";
  host.rel = "noopener";
  host.style.cssText = "display:inline-block;line-height:0;text-decoration:none";
  host.setAttribute("aria-label", "View this site's FixGuard AI health report");

  if (script && script.parentNode) {{
    script.parentNode.insertBefore(host, script);
  }} else {{
    document.body.appendChild(host);
  }}

  fetch(API, {{ cache: "no-store" }})
    .then(function (r) {{ return r.ok ? r.json() : null; }})
    .then(function (d) {{ if (d && d.svg) host.innerHTML = d.svg; }})
    .catch(function () {{ /* leave the badge absent rather than broken */ }});
}})();"""
