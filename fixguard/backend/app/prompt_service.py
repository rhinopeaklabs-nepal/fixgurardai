"""Module 1 orchestration: intent in, surgical prompt out.

Three context sources, in order of quality:

1. ``page_url``      - Playwright reads the live DOM and computed styles. Best.
2. ``code_context``  - pasted HTML, parsed without a browser. No computed
                       styles, so relative sizes cannot be resolved.
3. ``target_selector`` - the user already knows the selector; scope only.
"""
from __future__ import annotations

import datetime as dt
import uuid
from html.parser import HTMLParser
from typing import Any

from . import agents, db, llm, scope
from .audit.probe import extract_style_context
from .errors import FixGuardError


# --------------------------------------------------------------------------
# Pasted-HTML fallback parser
# --------------------------------------------------------------------------
class _CandidateParser(HTMLParser):
    """Build scope candidates from pasted HTML, with no browser involved."""

    INTERESTING = {
        "a", "button", "h1", "h2", "h3", "h4", "h5", "h6", "p", "img", "nav",
        "header", "footer", "section", "form", "li", "label", "input", "div",
        "span",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []
        self._class_use: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        classes = [c for c in a.get("class", "").split() if c]
        for c in classes:
            self._class_use[c] = self._class_use.get(c, 0) + 1

        if tag not in self.INTERESTING:
            return

        entry = {
            "tag": tag,
            "role": a.get("role", ""),
            "type": a.get("type", ""),
            "id": a.get("id", ""),
            "classes": classes,
            "shared_classes": [],
            "text": "",
            "selector": "",
            "styles": {},
            "parent": (
                {"tag": self._stack[-1]["tag"], "selector": "", "display": ""}
                if self._stack
                else None
            ),
        }
        self._stack.append(entry)
        self.candidates.append(entry)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and self._stack:
            existing = self._stack[-1]["text"]
            self._stack[-1]["text"] = (existing + " " + text).strip()[:90]

    def finalise(self) -> list[dict[str, Any]]:
        for c in self.candidates:
            if c["id"]:
                c["selector"] = f"#{c['id']}"
            else:
                unique = next(
                    (cl for cl in c["classes"] if self._class_use.get(cl) == 1), None
                )
                c["selector"] = f".{unique}" if unique else c["tag"]
            c["shared_classes"] = [
                {"name": cl, "used_by": self._class_use[cl]}
                for cl in c["classes"]
                if self._class_use.get(cl, 0) > 1
            ]
        # Drop structural wrappers with no text of their own.
        return [
            c for c in self.candidates
            if c["text"] or c["id"] or c["tag"] not in {"div", "span", "section"}
        ]


def parse_html_context(html: str) -> dict[str, Any]:
    parser = _CandidateParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return {
        "candidates": parser.finalise()[:140],
        "tokens": {},
        "globals": {},
        "title": "",
        "element_count": len(parser.candidates),
        "source": "pasted_html",
    }


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------
async def generate(
    intent: str,
    page_url: str | None = None,
    code_context: str | None = None,
    target_selector: str | None = None,
    use_model: bool = True,
) -> dict[str, Any]:
    intent = (intent or "").strip()
    if not intent:
        raise FixGuardError("VALIDATION_ERROR", "intent is required")
    if len(intent) > 500:
        raise FixGuardError("VALIDATION_ERROR", "intent must be 500 characters or fewer")

    # ---- 1. context --------------------------------------------------------
    if page_url:
        try:
            context = await extract_style_context(page_url)
        except RuntimeError as exc:
            code, _, detail = str(exc).partition("::")
            raise FixGuardError(code or "WORKER_CRASH", detail or str(exc)) from exc
        context["source"] = "live_page"
    elif code_context:
        context = parse_html_context(code_context)
    elif target_selector:
        context = {
            "candidates": [],
            "tokens": {},
            "globals": {},
            "source": "selector_only",
        }
    else:
        raise FixGuardError(
            "VALIDATION_ERROR",
            "Provide a page_url, code_context, or target_selector so the change "
            "can be scoped to a specific element.",
        )

    candidates = context.get("candidates") or []

    # ---- 2. deterministic scoping -----------------------------------------
    # A request to "redesign the page" is a project, not a CSS change. Saying
    # so beats emitting a confident prompt for an element we guessed at.
    if scope.is_broad_request(intent):
        return _out_of_scope(intent, page_url, context)

    hints = scope.extract_target_hints(intent)
    target, alternatives, reasons = (None, [], [])

    if target_selector:
        target = next(
            (c for c in candidates if c["selector"] == target_selector),
            {"selector": target_selector, "tag": "", "text": "", "styles": {},
             "parent": None, "shared_classes": [], "classes": [], "id": ""},
        )
        reasons = ["selector supplied by the user"]
    elif candidates:
        target, alternatives, reasons = scope.resolve_target(candidates, hints)

    prop = scope.detect_property(intent, target.get("tag") if target else None)
    current = (target or {}).get("styles", {}).get(prop)
    value, value_note = scope.detect_value(intent, prop, current)

    result: dict[str, Any] = {
        "target": target,
        "selector": (target or {}).get("selector") if target else None,
        "property": prop,
        "value": value,
        "current_value": current,
        "element_label": (target or {}).get("text", "") if target else "",
        "confidence": 0.85 if target and reasons else (0.4 if target else 0.15),
        "match_reasons": reasons,
        "source": "rules",
    }

    # ---- 3. optional model refinement (Agent 2) ---------------------------
    if use_model and llm.is_configured() and not target_selector:
        result = await agents.refine_scope(intent, candidates, result)
        target = result.get("target") or target
        prop = result.get("property") or prop
        value = result.get("value") or value
        current = (target or {}).get("styles", {}).get(prop) or current

    # ---- 4. freeze scope and assemble -------------------------------------
    frozen = scope.build_frozen_scope(target, context)
    prompt = scope.build_prompt(
        intent=intent,
        selector=result.get("selector"),
        prop=prop,
        value=value,
        current=current,
        frozen=frozen,
        element_label=result.get("element_label") or "",
    )
    savings = scope.estimate_savings(prompt, intent)

    notes: list[str] = []
    if value_note:
        notes.append(value_note)
    notes.extend(frozen.get("warnings") or [])
    if result.get("model_note"):
        notes.append(result["model_note"])
    if not target:
        notes.append(
            "No element on the page clearly matched the request, so the prompt "
            "describes the change without a selector. Adding a selector, or "
            "quoting the element's visible text, will scope it properly."
        )
    if context.get("source") == "pasted_html":
        notes.append(
            "Scoped from pasted HTML, so computed styles were unavailable and "
            "relative sizes could not be resolved."
        )

    record_id = str(uuid.uuid4())
    created = dt.datetime.now(dt.timezone.utc).isoformat()

    diff = None
    if result.get("selector") and value:
        diff = {
            "selector": result["selector"],
            "property": prop,
            "before": current,
            "after": value,
            "frozen_count": (
                len(frozen.get("global_tokens") or [])
                + (1 if frozen.get("parent_layout") else 0)
                + (1 if frozen.get("global_font_family") else 0)
            ),
        }

    payload = {
        "id": record_id,
        "intent": intent,
        "prompt": prompt,
        "selector": result.get("selector"),
        "property": prop,
        "value": value,
        "current_value": current,
        "element_label": result.get("element_label"),
        "confidence": round(float(result.get("confidence") or 0.5), 2),
        "match_reasons": result.get("match_reasons") or [],
        "alternatives": [
            {"selector": a.get("selector"), "tag": a.get("tag"), "text": a.get("text")}
            for a in (alternatives or [])[:3]
        ],
        "frozen_scope": frozen,
        "diff_preview": diff,
        "savings": savings,
        "notes": notes,
        "engine": result.get("source", "rules"),
        "context_source": context.get("source"),
        "created_at": created,
    }

    db.insert_prompt(
        {
            "id": record_id,
            "original_intent": intent,
            "guarded_prompt": prompt,
            "scope_boundary": frozen,
            "target_selector": result.get("selector"),
            "css_property": prop,
            "css_value": value,
            "source_url": page_url,
            "confidence": payload["confidence"],
            "tokens_saved_estimate": savings["tokens_saved_estimate"],
            "engine": payload["engine"],
            "created_at": created,
        }
    )
    return payload


# --------------------------------------------------------------------------
def _out_of_scope(
    intent: str, page_url: str | None, context: dict[str, Any]
) -> dict[str, Any]:
    """Explain why this request cannot be scoped, and how to split it up."""
    candidates = context.get("candidates") or []
    examples: list[str] = []
    for c in candidates:
        label = (c.get("text") or "").strip().splitlines()[0][:40] if c.get("text") else ""
        if not label:
            continue
        if c.get("tag") == "button":
            examples.append(f'Make the "{label}" button background blue')
        elif c.get("tag") in {"h1", "h2"}:
            examples.append(f'Make the "{label}" heading bigger')
        if len(examples) >= 3:
            break
    if not examples:
        examples = [
            "Make the booking button background blue",
            "Make the main heading bigger",
            "Hide the phone field",
        ]

    return {
        "id": None,
        "intent": intent,
        "prompt": None,
        "out_of_scope": True,
        "selector": None,
        "property": None,
        "value": None,
        "confidence": 0.0,
        "match_reasons": [],
        "alternatives": [],
        "frozen_scope": {},
        "diff_preview": None,
        "savings": None,
        "notes": [
            "This asks for a redesign or a new capability, not a change to one "
            "element, so there is nothing specific to scope a prompt around.",
            "FixGuard protects credits by making each prompt change exactly one "
            "property on exactly one element. A broad prompt is precisely the "
            "kind that makes AI Builder regenerate whole sections and burn "
            "credits on retries.",
            "Break the work into single changes and generate a prompt for each.",
        ],
        "suggestions": examples,
        "engine": "rules",
        "context_source": context.get("source"),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
