"""Turn audit findings into fix prompts.

Module 3 finds what is broken. Module 1 scopes a change. This joins them: feed
in an audit and get back one guarded prompt per finding, ready to paste into AI
Builder.

These prompts differ from the CSS ones. A silent form failure is not a property
change, so the prompt states the observed evidence, names the fix, and then
fences off everything AI Builder must leave alone - because "fix my contact
form" is exactly the vague instruction that makes it regenerate the page.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from urllib.parse import urlparse

COMMON_GUARDRAILS = [
    "Do not restructure the page, rename classes, or reorder elements.",
    "Do not change any styling: colours, fonts, spacing and layout stay exactly as they are.",
    "Do not modify any other page, section, or component.",
    "Change only what is described above, and return only the changed code.",
]


def _fence(lines: list[str], extra: list[str] | None = None) -> str:
    out = list(lines)
    out.append("")
    out.append("DO NOT:")
    for g in (extra or []) + COMMON_GUARDRAILS:
        out.append(f"- {g.rstrip('.')}" if not g.startswith("-") else g)
    return "\n".join(out)


def _form_label(f: dict[str, Any]) -> str:
    return (
        f.get("heading")
        or f.get("submit_text")
        or f"form {(f.get('form_index') or 0) + 1}"
    )


# --------------------------------------------------------------------------
def _form_fixes(run: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in run.get("form_results") or []:
        verdict = f.get("verdict")
        label = _form_label(f)
        reqs = f.get("submission_requests") or []

        if verdict in {"silent_failure", "no_submission"}:
            evidence = (
                "FixGuard filled this form, clicked submit, and recorded every "
                "network request the browser made. There were none."
                + (
                    " The page still displayed a success message."
                    if f.get("success_text_shown")
                    else ""
                )
            )
            prompt = _fence(
                [
                    f'The "{label}" form does not send anything when it is submitted.',
                    "",
                    "Wire its submit handler to actually deliver the submission:",
                    "1. Send the form's field values to a real endpoint on submit.",
                    "2. Show the success message ONLY after that request succeeds.",
                    "3. Show a visible error message if the request fails.",
                    "",
                    "Keep the same fields, labels, and visual design.",
                ],
                ["- change the form's fields, labels, placeholder text, or layout"],
            )
            out.append(
                {
                    "category": "form",
                    "severity": "critical",
                    "title": f'"{label}" never sends anything',
                    "problem": f.get("explanation") or "",
                    "evidence": evidence,
                    "prompt": prompt,
                }
            )

        elif verdict == "endpoint_error":
            codes = ", ".join(
                str(r.get("status") or r.get("failure")) for r in reqs[:3]
            )
            out.append(
                {
                    "category": "form",
                    "severity": "critical",
                    "title": f'"{label}" submissions are rejected by the server',
                    "problem": f.get("explanation") or "",
                    "evidence": f"The submission was sent but returned {codes}.",
                    "prompt": _fence(
                        [
                            f'The "{label}" form sends its data but the server rejects it '
                            f"({codes}).",
                            "",
                            "Fix the submission so the server accepts it:",
                            "1. Check the endpoint URL and HTTP method are correct.",
                            "2. Check the request body matches the format the endpoint expects.",
                            "3. Surface a visible error to the visitor when a submission fails, "
                            "instead of showing success.",
                        ]
                    ),
                }
            )

        elif verdict == "blocked_by_protection":
            out.append(
                {
                    "category": "form",
                    "severity": "warning",
                    "title": f'"{label}" could not be tested',
                    "problem": f.get("explanation") or "",
                    "evidence": "The rejection came from a protection layer, "
                                "not from the application.",
                    "prompt": None,
                    "advisory": (
                        "There is nothing to change in your site here. Submit "
                        "the form yourself once to confirm it works. To have "
                        "FixGuard test it automatically, allow its requests "
                        "through your firewall or bot-protection rules."
                    ),
                }
            )

        elif verdict == "js_crash":
            errs = "; ".join((f.get("js_errors_on_submit") or [])[:2])
            out.append(
                {
                    "category": "form",
                    "severity": "critical",
                    "title": f'"{label}" crashes when submitted',
                    "problem": f.get("explanation") or "",
                    "evidence": f"JavaScript error on submit: {errs}",
                    "prompt": _fence(
                        [
                            f'Submitting the "{label}" form throws a JavaScript error, so the '
                            "submission never completes.",
                            "",
                            f"The error is: {errs}",
                            "",
                            "Fix the submit handler so it runs without throwing, and make sure "
                            "the success message only appears after the submission succeeds.",
                        ]
                    ),
                }
            )

        elif verdict == "no_feedback":
            out.append(
                {
                    "category": "form",
                    "severity": "warning",
                    "title": f'"{label}" gives the visitor no confirmation',
                    "problem": f.get("explanation") or "",
                    "evidence": "The submission was accepted, but nothing on the page changed.",
                    "prompt": _fence(
                        [
                            f'The "{label}" form submits successfully but shows the visitor '
                            "nothing afterwards, so people submit it twice.",
                            "",
                            "Add a visible confirmation message that appears after a successful "
                            "submission, and a visible error message if it fails. Match the "
                            "existing typography and colours.",
                        ],
                        ["- change the form's fields, labels, or layout"],
                    ),
                }
            )

        elif verdict == "no_submit_control":
            out.append(
                {
                    "category": "form",
                    "severity": "warning",
                    "title": f'"{label}" has no submit button',
                    "problem": f.get("explanation") or "",
                    "evidence": "No submit control was found inside the form.",
                    "prompt": _fence(
                        [
                            f'The "{label}" form has no submit button, so a visitor cannot send it.',
                            "",
                            "Add a submit button inside the form, styled to match the other "
                            "buttons on this page, and wire it to submit the form.",
                        ]
                    ),
                }
            )
    return out


def _router_fixes(run: dict[str, Any]) -> list[dict[str, Any]]:
    router = run.get("router_result") or {}
    out: list[dict[str, Any]] = []

    if router.get("has_navigation_loop"):
        url = router.get("loop_url") or run.get("target_url")
        out.append(
            {
                "category": "router",
                "severity": "critical",
                "title": "The page redirects to itself endlessly",
                "problem": "Visitors see a frozen or flickering page that never loads.",
                "evidence": (
                    f"{router.get('loop_count')} navigations to {url} within "
                    f"{router.get('window_seconds')} seconds."
                    + (
                        " The page never finished loading."
                        if router.get("page_load_blocked_by_loop")
                        else ""
                    )
                ),
                "prompt": _fence(
                    [
                        f"The page at {url} redirects to itself repeatedly and never "
                        "finishes loading.",
                        "",
                        "Find the code that triggers navigation on this route and add a "
                        "guard so it runs at most once:",
                        "1. If a useEffect calls navigate() or redirects, give it a correct "
                        "dependency array so it does not run on every render.",
                        "2. Before redirecting, check whether the app is already at the "
                        "destination route, and skip the redirect if it is.",
                        "",
                        "Keep the routing structure and every existing route path unchanged.",
                    ],
                    ["- add, remove, or rename any route"],
                ),
            }
        )

    rerender = router.get("rerender") or {}
    if rerender.get("suspected_infinite_rerender"):
        out.append(
            {
                "category": "router",
                "severity": "critical",
                "title": "The page re-renders continuously",
                "problem": (
                    "The page never settles after loading. It drains battery and "
                    "makes the site feel slow, and it logs no error, so it is easy "
                    "to miss."
                ),
                "evidence": (
                    f"{rerender.get('peak_mutations_in_window')} DOM changes in "
                    f"{rerender.get('window_ms')}ms with no user input "
                    f"(threshold {rerender.get('threshold')})."
                ),
                "prompt": _fence(
                    [
                        "This page updates its own content in a loop and never settles.",
                        "",
                        "Find the component that re-renders continuously and stop the loop:",
                        "1. A useEffect that sets state must have a dependency array, and "
                        "must not depend on a value it updates itself.",
                        "2. Objects, arrays and functions recreated on every render should "
                        "be memoised before being used as dependencies.",
                        "3. A requestAnimationFrame or setInterval that redraws the page "
                        "should be removed unless it is genuinely an animation.",
                        "",
                        "Keep the rendered output identical.",
                    ]
                ),
            }
        )

    broken = router.get("broken_routes_list") or []
    if broken:
        listed = ", ".join(broken[:6])
        out.append(
            {
                "category": "router",
                "severity": "warning",
                "title": (
                    "1 internal link leads nowhere" if len(broken) == 1
                    else f"{len(broken)} internal links lead nowhere"
                ),
                "problem": "Visitors clicking these links reach a dead page.",
                "evidence": f"Checked {router.get('routes_crawled')} links. Broken: {listed}",
                "prompt": _fence(
                    [
                        f"These internal links on this site do not load: {listed}",
                        "",
                        "For each one, either point the link at the correct existing page, "
                        "or remove the link if the page no longer exists.",
                        "",
                        "Do not create new pages to satisfy these links unless the page is "
                        "genuinely meant to exist.",
                    ]
                ),
            }
        )
    return out


def _console_fixes(run: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = {p.get("message"): p for p in (run.get("parsed_errors") or [])}

    # A failed resource logs both a console error and an asset issue. The asset
    # fix already lists every one of them with its URL, so emitting a console
    # fix per 404 would repeat the same work under a vaguer title.
    covered_by_assets = bool(run.get("asset_issues"))

    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in run.get("console_errors") or []:
        if c.get("severity") != "critical":
            continue
        msg = (c.get("message") or "").strip()
        if not msg or msg in seen:
            continue
        if covered_by_assets and msg.lower().startswith("failed to load resource"):
            continue
        seen.add(msg)
        errors.append(c)
        if len(errors) >= 5:
            break

    out: list[dict[str, Any]] = []
    for c in errors:
        msg = c.get("message") or ""
        info = parsed.get(msg) or {}
        where = c.get("source_url") or ""
        line = c.get("line")
        location = f"{where}{f':{line}' if line is not None else ''}" if where else ""
        out.append(
            {
                "category": "console",
                "severity": "warning",
                "title": info.get("meaning") or "JavaScript error on this page",
                "problem": info.get("action") or "",
                "evidence": f"{msg}" + (f"\n{location}" if location else ""),
                "prompt": _fence(
                    [
                        "This page logs a JavaScript error when it loads:",
                        "",
                        f"    {msg}",
                        *( [f"    at {location}"] if location else [] ),
                        "",
                        (info.get("action") or "Fix the cause of this error.").strip(),
                        "",
                        "Fix only the cause of this error.",
                    ]
                ),
            }
        )
    return out


def _asset_fixes(run: dict[str, Any]) -> list[dict[str, Any]]:
    assets = run.get("asset_issues") or []
    if not assets:
        return []
    listed = "\n".join(
        f"    {a.get('url')} ({a.get('resource_type')} - {a.get('status') or a.get('failure')})"
        for a in assets[:6]
    )
    return [
        {
            "category": "assets",
            "severity": "warning",
            "title": (
                "1 file fails to load" if len(assets) == 1
                else f"{len(assets)} files fail to load"
            ),
            "problem": "Images, styles or scripts the page asks for are missing.",
            "evidence": listed,
            "prompt": _fence(
                [
                    "These files fail to load on this page:",
                    "",
                    listed,
                    "",
                    "For each one, correct the path if the file exists elsewhere, replace it "
                    "if it was deleted, or remove the reference if it is no longer needed.",
                ]
            ),
        }
    ]


def _reach_advisories(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Infrastructure problems. Flagged, but not as AI Builder prompts."""
    reach = run.get("reachability") or {}
    out: list[dict[str, Any]] = []
    tls = reach.get("tls") or {}
    days = tls.get("days_remaining")

    if tls.get("valid") is False:
        out.append(
            {
                "category": "infrastructure",
                "severity": "critical",
                "title": "The TLS certificate is not valid",
                "problem": "Browsers will warn visitors before they can reach the site.",
                "evidence": tls.get("error") or "",
                "prompt": None,
                "advisory": (
                    "This is a hosting setting, not a page change. Reissue the "
                    "certificate in hPanel; there is no prompt to paste into AI Builder."
                ),
            }
        )
    elif isinstance(days, int) and days <= 21:
        out.append(
            {
                "category": "infrastructure",
                "severity": "warning",
                "title": f"The TLS certificate expires in {days} days",
                "problem": "Visitors will see a security warning once it lapses.",
                "evidence": f"Expires {tls.get('expires_at')}",
                "prompt": None,
                "advisory": "Renew it in hPanel. Not something AI Builder can change.",
            }
        )

    if reach.get("dns_resolved") is False:
        out.append(
            {
                "category": "infrastructure",
                "severity": "critical",
                "title": "The domain does not resolve",
                "problem": "Nobody can reach this site at all.",
                "evidence": reach.get("dns_error") or "",
                "prompt": None,
                "advisory": "Check the domain's DNS records in hPanel.",
            }
        )
    elif reach.get("ip_blocked"):
        out.append(
            {
                "category": "infrastructure",
                "severity": "critical",
                "title": f"The server answered {reach.get('status_code')}",
                "problem": "Requests appear to be blocked before reaching the site.",
                "evidence": "\n".join(reach.get("issues") or []),
                "prompt": None,
                "advisory": (
                    "Check firewall or region rules in hPanel. FixGuard measured this "
                    "from one location only."
                ),
            }
        )
    return out


# --------------------------------------------------------------------------
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def build(run: dict[str, Any]) -> dict[str, Any]:
    """Every actionable finding in an audit, as a ready-to-paste fix prompt."""
    items = (
        _form_fixes(run)
        + _router_fixes(run)
        + _console_fixes(run)
        + _asset_fixes(run)
        + _reach_advisories(run)
    )
    items.sort(key=lambda i: SEVERITY_ORDER.get(i.get("severity", "info"), 3))

    host = urlparse(run.get("target_url") or "").netloc
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for i in items:
        i["id"] = str(uuid.uuid4())
        i["created_at"] = now
        if i.get("prompt"):
            # Name the page so a pasted prompt is unambiguous in the builder.
            i["prompt"] = f"On {run.get('target_url')}:\n\n{i['prompt']}"

    fixable = [i for i in items if i.get("prompt")]
    return {
        "audit_id": run.get("id"),
        "target_url": run.get("target_url"),
        "host": host,
        "health_score": run.get("health_score"),
        "grade": run.get("grade"),
        "generated_at": now,
        "total_findings": len(items),
        "fixable_count": len(fixable),
        "advisory_count": len(items) - len(fixable),
        "fixes": items,
    }
