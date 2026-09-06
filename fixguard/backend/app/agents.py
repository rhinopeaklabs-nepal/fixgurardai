"""The three agents from SRS FR-X.2.

Agent 1  Log Parser        raw console output -> plain English
Agent 2  Prompt Generator  intent + DOM scope -> guarded surgical prompt
Agent 3  Summary Agent     audit JSON -> client-facing executive summary

Each one runs deterministically first and only calls a model to improve on
that. The fallback is the product, not a degraded mode: it must produce
something a user would accept, because it is what runs with no key.

Every call is logged with input, output and latency, per FR-X.2.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from typing import Any

from . import config, db, llm, scope

# --------------------------------------------------------------------------
# Agent 1 - Log Parser
# --------------------------------------------------------------------------
# Deterministic explanations for the console errors that actually recur on
# AI-built sites. Ordered: first match wins.
ERROR_EXPLANATIONS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"cannot read propert(?:y|ies) of null", re.I),
        "A script tried to use a page element that does not exist.",
        "Usually the script runs before the element is on the page, or the "
        "element was renamed or deleted. Wrap the code in a DOMContentLoaded "
        "listener, or check the element exists before using it.",
    ),
    (
        re.compile(r"cannot read propert(?:y|ies) of undefined", re.I),
        "A script tried to read a value that was never set.",
        "Something the code expected - usually data from an API or a variable "
        "defined elsewhere - was missing at that moment.",
    ),
    (
        re.compile(r"is not a function", re.I),
        "A script called something that is not a function.",
        "Typically a library failed to load, or its name is misspelled.",
    ),
    (
        re.compile(r"failed to load resource.*40[34]", re.I),
        "A file the page asked for is missing.",
        "The image, stylesheet or script at that address returns 404. Either "
        "the file was deleted or the path is wrong.",
    ),
    (
        re.compile(r"failed to load resource.*5\d\d", re.I),
        "A file the page asked for returned a server error.",
        "The server responded with a 5xx. This is a hosting or backend problem, "
        "not a problem with the page itself.",
    ),
    (
        re.compile(r"cors|cross-origin|access-control-allow", re.I),
        "The browser blocked a request to another domain.",
        "The other server did not send permission headers. It has to allow this "
        "site's origin, or the request has to go through your own backend.",
    ),
    (
        re.compile(r"throttling navigation", re.I),
        "The browser stopped the page from redirecting endlessly.",
        "Chromium halts a page that navigates to itself repeatedly. Something "
        "is redirecting on every render - usually a useEffect with no guard.",
    ),
    (
        re.compile(r"maximum call stack|too much recursion", re.I),
        "A function called itself until the browser gave up.",
        "There is a loop with no exit condition.",
    ),
    (
        re.compile(r"unexpected token|syntaxerror", re.I),
        "A script has a syntax error and did not run at all.",
        "Everything after the error in that file is dead. This usually breaks "
        "more than it appears to.",
    ),
    (
        re.compile(r"mixed content|blocked.*https", re.I),
        "The page loaded an insecure file over HTTPS.",
        "Browsers block http:// resources on an https:// page. Update the URL.",
    ),
    (
        re.compile(r"hydration|did not match|text content does not match", re.I),
        "The server-rendered HTML did not match what the browser rendered.",
        "A React hydration mismatch. It causes flicker and can wipe interactivity.",
    ),
    (
        re.compile(r"deprecat", re.I),
        "The page uses a browser feature that is being retired.",
        "It still works today but will break in a future browser version.",
    ),
]

AGENT1_SYSTEM = (
    "You explain browser console errors to non-technical website owners. "
    "For each error give one sentence on what it means and one on what to do. "
    "No jargon, no code, no preamble. Reply with JSON: "
    '{"items":[{"index":0,"meaning":"...","action":"..."}]}'
)


def _explain_one(message: str) -> dict[str, str]:
    for pattern, meaning, action in ERROR_EXPLANATIONS:
        if pattern.search(message):
            return {"meaning": meaning, "action": action, "source": "rules"}
    return {
        "meaning": "The page logged an error the browser could not recover from.",
        "action": "Share this message with whoever maintains the site; it names "
                  "the file and line where the problem is.",
        "source": "rules",
    }


async def parse_logs(console_errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agent 1. Rules first, model only for what the rules did not recognise."""
    if not console_errors:
        return []

    items = [dict(e, **_explain_one(e.get("message", ""))) for e in console_errors[:25]]

    unknown = [
        (i, e) for i, e in enumerate(items)
        if e["meaning"].startswith("The page logged an error the browser")
    ]
    if not unknown or not llm.is_configured():
        return items

    payload = [{"index": i, "error": e.get("message", "")[:300]} for i, e in unknown]
    try:
        result = await llm.complete(
            AGENT1_SYSTEM,
            json.dumps(payload),
            max_tokens=700,
        )
        _log_call("agent1_log_parser", payload, result.text, result.latency_ms, True)
        parsed = llm.extract_json(result.text) or {}
        for entry in parsed.get("items", []):
            idx = entry.get("index")
            if isinstance(idx, int) and 0 <= idx < len(items):
                if entry.get("meaning"):
                    items[idx]["meaning"] = str(entry["meaning"])[:300]
                if entry.get("action"):
                    items[idx]["action"] = str(entry["action"])[:300]
                items[idx]["source"] = "model"
    except llm.LLMUnavailable as exc:
        _log_call("agent1_log_parser", payload, f"unavailable: {exc}", 0, False)

    return items


# --------------------------------------------------------------------------
# Agent 2 - Prompt Generator
# --------------------------------------------------------------------------
AGENT2_SYSTEM = (
    "You extract a precise CSS edit from a website owner's plain-English "
    "request. You are given the request and a list of real elements from their "
    "page. Choose the element they mean and the single CSS property to change.\n"
    "Reply with JSON only:\n"
    '{"selector":"<css selector copied exactly from the candidates>",'
    '"property":"<one css property>","value":"<the new value, or null>",'
    '"element_label":"<the element\'s visible text>","confidence":0.0-1.0,'
    '"reason":"<one short sentence>"}\n'
    "Copy the selector verbatim from the candidate list. Never invent one."
)


async def refine_scope(
    intent: str, candidates: list[dict[str, Any]], deterministic: dict[str, Any]
) -> dict[str, Any]:
    """Agent 2. Let a model second-guess the deterministic match.

    The model may only pick from selectors that actually exist on the page, so
    a hallucinated selector is rejected rather than shipped to the user.
    """
    if not llm.is_configured() or not candidates:
        return deterministic

    slim = [
        {
            "selector": c["selector"],
            "tag": c["tag"],
            "text": c.get("text", "")[:60],
            "id": c.get("id", ""),
            "classes": (c.get("classes") or [])[:4],
        }
        for c in candidates[:40]
    ]
    user = json.dumps({"request": intent, "candidates": slim})

    try:
        result = await llm.complete(AGENT2_SYSTEM, user, max_tokens=400)
        _log_call("agent2_prompt_generator", user[:2000], result.text, result.latency_ms, True)
    except llm.LLMUnavailable as exc:
        _log_call("agent2_prompt_generator", user[:2000], f"unavailable: {exc}", 0, False)
        return deterministic

    parsed = llm.extract_json(result.text)
    if not parsed:
        return deterministic

    valid = {c["selector"] for c in candidates}
    selector = parsed.get("selector")
    if selector not in valid:
        # Hallucinated selector. Keep the deterministic answer.
        deterministic["model_note"] = (
            "The model proposed a selector that is not on the page, so the "
            "deterministic match was kept."
        )
        return deterministic

    match = next(c for c in candidates if c["selector"] == selector)
    prop = parsed.get("property") or deterministic.get("property")
    return {
        **deterministic,
        "target": match,
        "selector": selector,
        "property": prop,
        "value": parsed.get("value") or deterministic.get("value"),
        "element_label": parsed.get("element_label") or match.get("text", ""),
        "confidence": float(parsed.get("confidence") or 0.8),
        "match_reasons": [parsed.get("reason", "chosen by model")],
        "source": "model",
    }


# --------------------------------------------------------------------------
# Agent 3 - Summary Agent
# --------------------------------------------------------------------------
AGENT3_SYSTEM = (
    "You write a short status note for a website owner who is not technical. "
    "Two or three sentences. Say plainly what is wrong and what it costs them "
    "in business terms. No jargon, no bullet points, no greeting."
)


def _fallback_summary(run: dict[str, Any]) -> str:
    score = run.get("health_score")

    # Never describe checks that did not run. Saying "the forms submit
    # correctly" about a page that never loaded is worse than saying nothing.
    if score is None or (run.get("score_breakdown") or {}).get("grade") == "not_assessed":
        why = run.get("partial_reason") or "the page could not be opened"
        return (
            f"{run.get('target_url', 'The site')} could not be assessed: {why}. "
            "No health score is given, because nothing about the site itself "
            "was measured."
        )
    grade = (run.get("grade") or "").replace("_", " ")
    url = run.get("target_url", "the site")
    forms = run.get("form_results") or []
    router = run.get("router_result") or {}

    problems: list[str] = []
    for f in forms:
        if f.get("verdict") in {"silent_failure", "no_submission"}:
            problems.append(
                "a contact form that shows a success message but never sends "
                "anything, so enquiries submitted through it are lost"
            )
            break
        if f.get("verdict") == "endpoint_error":
            problems.append("a contact form whose submissions are rejected by the server")
            break
    if router.get("has_navigation_loop"):
        problems.append("a page that redirects endlessly and never finishes loading")
    if (router.get("rerender") or {}).get("suspected_infinite_rerender"):
        problems.append("a page that re-renders continuously, draining visitors' batteries")
    broken = router.get("broken_routes_list") or []
    if broken:
        problems.append(
            f"{len(broken)} internal link that leads nowhere" if len(broken) == 1
            else f"{len(broken)} internal links that lead nowhere"
        )
    n_console = len(run.get("console_errors") or [])
    if n_console and not problems:
        problems.append(
            f"{n_console} JavaScript error in the browser console" if n_console == 1
            else f"{n_console} JavaScript errors in the browser console"
        )

    if not problems:
        return (
            f"{url} scored {score} out of 100. The forms submit correctly, the "
            "pages load without redirect loops, and no errors were logged. "
            "Nothing needs attention right now."
        )

    joined = problems[0] if len(problems) == 1 else (
        ", ".join(problems[:-1]) + ", and " + problems[-1]
    )
    urgency = (
        "This needs fixing before the site takes any more traffic."
        if (score or 0) < 50
        else "Worth fixing soon."
    )
    return f"{url} scored {score} out of 100 ({grade}). The audit found {joined}. {urgency}"


async def summarise(run: dict[str, Any]) -> dict[str, Any]:
    """Agent 3. Template first; a model rewrites it more naturally if available."""
    text = _fallback_summary(run)
    source = "template"

    if llm.is_configured():
        facts = {
            "url": run.get("target_url"),
            "score": run.get("health_score"),
            "grade": run.get("grade"),
            "form_verdicts": [f.get("verdict") for f in (run.get("form_results") or [])],
            "navigation_loop": (run.get("router_result") or {}).get("has_navigation_loop"),
            "rerender_loop": ((run.get("router_result") or {}).get("rerender") or {})
                .get("suspected_infinite_rerender"),
            "broken_routes": (run.get("router_result") or {}).get("broken_routes_list"),
            "console_errors": len(run.get("console_errors") or []),
            "broken_assets": len(run.get("asset_issues") or []),
        }
        user = json.dumps(facts)
        try:
            result = await llm.complete(AGENT3_SYSTEM, user, max_tokens=300)
            _log_call("agent3_summary", user, result.text, result.latency_ms, True)
            if result.text:
                text, source = result.text.strip(), "model"
        except llm.LLMUnavailable as exc:
            _log_call("agent3_summary", user, f"unavailable: {exc}", 0, False)

    return {"summary": text, "source": source}


# --------------------------------------------------------------------------
# Call logging (FR-X.2)
# --------------------------------------------------------------------------
def _log_call(
    agent: str, payload: Any, output: str, latency_ms: int, ok: bool
) -> None:
    try:
        db.insert_agent_call(
            agent=agent,
            provider=llm.provider_name(),
            model_id=config.LLM_MODEL if llm.is_configured() else "",
            input_text=(payload if isinstance(payload, str) else json.dumps(payload))[:4000],
            output_text=(output or "")[:4000],
            latency_ms=latency_ms,
            ok=ok,
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
    except Exception:
        # Telemetry must never break the request it is describing.
        pass
