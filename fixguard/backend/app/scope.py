"""Module 1 scoping engine: intent -> (target, property, value, frozen scope).

Entirely deterministic. A model is an optional accuracy upgrade layered on top
(see ``agents.parse_intent``), never a dependency. The reason is practical: this
runs during a live demo, and a rate limit must not break the core feature.

The engine answers three questions:

1. **What property** does the user want changed?  Phrase matching.
2. **What element** do they mean?  Scored against real DOM candidates.
3. **What must not move?**  Global tokens, fonts, parent layout - and any
   selector shared with other elements, because changing ``.btn`` when twelve
   elements use it is exactly how AI Builder users lose their styling.
"""
from __future__ import annotations

import re
from typing import Any

# --------------------------------------------------------------------------
# Colour vocabulary
# --------------------------------------------------------------------------
NAMED_COLORS = {
    "black": "#000000", "white": "#ffffff", "red": "#e02424", "blue": "#0055ff",
    "green": "#0a8f4d", "yellow": "#f5c518", "orange": "#f97316",
    "purple": "#7c3aed", "pink": "#ec4899", "grey": "#6b7280", "gray": "#6b7280",
    "brown": "#92400e", "navy": "#1e3a8a", "teal": "#0d9488", "cyan": "#06b6d4",
    "magenta": "#d946ef", "lime": "#65a30d", "gold": "#d4af37",
    "silver": "#c0c0c0", "beige": "#f5f5dc", "maroon": "#7f1d1d",
    "turquoise": "#40e0d0", "violet": "#8b5cf6", "indigo": "#4f46e5",
    "coral": "#ff7f50", "salmon": "#fa8072", "mint": "#3eb489",
    "transparent": "transparent",
}

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_RE = re.compile(r"rgba?\([^)]+\)", re.I)
LENGTH_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(px|rem|em|%|pt|vh|vw)\b", re.I)

# --------------------------------------------------------------------------
# Property vocabulary. Order matters: earlier patterns win.
# --------------------------------------------------------------------------
PROPERTY_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"background|bg\b|fill\b", re.I), "background-color"),
    (re.compile(r"text\s*colou?r|font\s*colou?r|colou?r\s+of\s+the\s+text", re.I), "color"),
    (re.compile(r"border[-\s]*radius|rounded|corner", re.I), "border-radius"),
    (re.compile(r"font\s*size|text\s*size|bigger|smaller|larger|tiny|huge", re.I), "font-size"),
    (re.compile(r"\bbold\b|font\s*weight|thinner|lighter\s+text", re.I), "font-weight"),
    (re.compile(r"font\s*family|typeface|\bfont\b", re.I), "font-family"),
    (re.compile(r"padding|inner\s*spacing", re.I), "padding"),
    (re.compile(r"margin|outer\s*spacing|gap\s+around", re.I), "margin"),
    (re.compile(r"\bhide\b|\bremove\b|make.*invisible|don'?t show", re.I), "display"),
    (re.compile(r"\bshow\b|make.*visible|unhide", re.I), "display"),
    (re.compile(r"box\s*shadow|drop\s*shadow|\bshadow\b", re.I), "box-shadow"),
    (re.compile(r"\bborder\b", re.I), "border"),
    (re.compile(r"\bwidth\b|wider|narrower", re.I), "width"),
    (re.compile(r"\bheight\b|taller|shorter", re.I), "height"),
    (re.compile(r"align|centre|center|left\s*align|right\s*align", re.I), "text-align"),
    (re.compile(r"uppercase|lowercase|capitali[sz]e", re.I), "text-transform"),
    (re.compile(r"opacity|transparen|fade", re.I), "opacity"),
    (re.compile(r"colou?r", re.I), "color"),   # bare "colour", lowest priority
]

# Elements whose "colour" almost always means their background.
BACKGROUND_FIRST_TAGS = {"button", "nav", "header", "footer", "section", "form"}

# --------------------------------------------------------------------------
# Target vocabulary
# --------------------------------------------------------------------------
TAG_SYNONYMS: dict[str, list[str]] = {
    "button": ["button", "btn", "cta", "call to action"],
    "a": ["link", "anchor"],
    "h1": ["title", "main heading", "headline", "heading", "h1"],
    "h2": ["heading", "subheading", "subtitle", "h2"],
    "h3": ["heading", "h3"],
    # "text" is deliberately absent: it appears in "text colour", "text size"
    # and similar phrases far more often than it names a paragraph.
    "p": ["paragraph", "copy", "body text"],
    "img": ["image", "picture", "photo", "logo", "icon"],
    "nav": ["nav", "navigation", "menu", "navbar"],
    "header": ["header", "top bar", "masthead"],
    "footer": ["footer", "bottom"],
    "form": ["form", "contact form"],
    "input": ["field", "input", "textbox", "box"],
    "textarea": ["textarea", "message box"],
    "select": ["dropdown", "select", "picker"],
    "section": ["section", "block", "panel", "card", "banner", "hero"],
    "li": ["list item", "menu item"],
    "label": ["label"],
}

STOPWORDS = {
    "the", "a", "an", "my", "our", "this", "that", "to", "of", "on", "in",
    "make", "change", "set", "update", "please", "can", "you", "i", "want",
    "would", "like", "it", "its", "and", "for", "with", "into", "be", "is",
    "colour", "color", "background", "bigger", "smaller", "text", "size",
}

QUOTED_RE = re.compile(r"[\"'“‘]([^\"'”’]{2,60})[\"'”’]")

# A request is broad when no single element and one property could satisfy it.
#
# The earlier pattern required the literal word "it": "make it modern" was
# caught, "make the landing page more modern" was not. So the commonest
# phrasing of the commonest broad request walked straight through and came
# back as a confident instruction to recolour a logo.
#
# Coverage is chosen over precision here. A broad request wrongly refused
# costs the user one rephrase. A broad request wrongly accepted produces a
# plausible, copyable prompt aimed at the wrong element - which is the exact
# failure this module exists to prevent.
BROAD_INTENT_RE = re.compile(
    # "the whole site", "all the pages"
    r"(?:whole|entire|complete(?:ly)?|full|all)\s+(?:the\s+)?"
    r"(?:site|page|pages|website|thing|layout|design|app)"
    # verbs that are projects on their own
    r"|redesign|re-design|rebuild|rewrite|revamp|overhaul|from scratch"
    r"|modernis|moderniz|refresh the (?:look|design|site|page)"
    # "make <anything> modern / better / professional"
    r"|make\s+(?:it|this|the|my)\b[^.]{0,40}?\b"
    r"(?:modern|better|nicer?|pretty|beautiful|professional|premium|"
    r"cleaner?|attractive|appealing|stunning|impressive)"
    # "more modern", "more professional", with no target named
    r"|more\s+(?:modern|professional|beautiful|attractive|premium)"
    # quality asks that name no element
    r"|best\s+(?:ui|ux|design|seo|practices)|ui\s*/?\s*ux\s+design"
    r"|\bseo\b|accessib|responsive design|mobile[- ]friendly"
    # capability rather than styling
    r"|fully?\s+functional|make it work|fix everything|improve everything"
    # "add a new pricing page" - the noun can be qualified, so allow words
    # between the article and the thing being added.
    r"|add\s+(?:a|an|another)?[^.]{0,30}?\b(?:page|section|feature|form|blog|shop|component)\b",
    re.I,
)

MIN_CONFIDENCE = 0.5

RELATIVE_SIZE = {
    "bigger": 1.25, "larger": 1.25, "huge": 1.6, "smaller": 0.8,
    "tiny": 0.7, "shorter": 0.85, "taller": 1.2,
}


# --------------------------------------------------------------------------
# Step 1: property
# --------------------------------------------------------------------------
def detect_property(intent: str, target_tag: str | None = None) -> str:
    for pattern, prop in PROPERTY_RULES:
        if pattern.search(intent):
            # "make the button blue" means its background, not its label.
            if prop == "color" and target_tag in BACKGROUND_FIRST_TAGS:
                return "background-color"
            return prop

    # No property word at all, but a colour was named: infer from the element.
    if detect_color(intent):
        return "background-color" if target_tag in BACKGROUND_FIRST_TAGS else "color"
    return "color"


def detect_color(intent: str) -> str | None:
    m = HEX_RE.search(intent)
    if m:
        return m.group(0)
    m = RGB_RE.search(intent)
    if m:
        return m.group(0)
    for word in re.findall(r"[a-zA-Z]+", intent.lower()):
        if word in NAMED_COLORS:
            return NAMED_COLORS[word]
    return None


# --------------------------------------------------------------------------
# Step 2: value
# --------------------------------------------------------------------------
def detect_value(intent: str, prop: str, current: str | None) -> tuple[str | None, str]:
    """Return (value, note). ``note`` explains an inference to the user."""
    low = intent.lower()

    if prop in {"color", "background-color", "border"}:
        c = detect_color(intent)
        if c:
            return c, ""
        return None, "No colour was named, so the prompt asks for one explicitly."

    if prop in {"font-size", "width", "height", "padding", "margin", "border-radius"}:
        m = LENGTH_RE.search(intent)
        if m:
            return f"{m.group(1)}{m.group(2).lower()}", ""
        for word, factor in RELATIVE_SIZE.items():
            if word in low:
                if current:
                    num = re.match(r"([\d.]+)([a-z%]*)", current.strip())
                    if num:
                        scaled = round(float(num.group(1)) * factor, 1)
                        unit = num.group(2) or "px"
                        clean = int(scaled) if scaled == int(scaled) else scaled
                        return (
                            f"{clean}{unit}",
                            f"'{word}' interpreted as {factor:g}x the current {current}.",
                        )
                return None, f"'{word}' is relative; the prompt states the direction."
        return None, "No size was given, so the prompt asks for an explicit value."

    if prop == "font-weight":
        if re.search(r"\bbold\b", low):
            return "700", ""
        if re.search(r"thin|light", low):
            return "300", ""
        return None, ""

    if prop == "display":
        if re.search(r"hide|remove|invisible|don'?t show", low):
            return "none", ""
        return "block", ""

    if prop == "text-align":
        for word in ("center", "centre", "left", "right", "justify"):
            if word in low:
                return "center" if word == "centre" else word, ""
        return None, ""

    if prop == "text-transform":
        for word in ("uppercase", "lowercase", "capitalize"):
            if word in low:
                return word, ""
        return None, ""

    if prop == "font-family":
        q = QUOTED_RE.search(intent)
        if q:
            return q.group(1), ""
        return None, "No typeface was named, so the prompt asks for one."

    if prop == "opacity":
        m = re.search(r"(\d{1,3})\s*%", intent)
        if m:
            return str(round(int(m.group(1)) / 100, 2)), ""
        return None, ""

    if prop == "box-shadow":
        if re.search(r"no shadow|remove shadow|without shadow", low):
            return "none", ""
        return "0 2px 8px rgba(0,0,0,0.15)", "A conventional subtle shadow was assumed."

    return None, ""


# --------------------------------------------------------------------------
# Step 3: target
# --------------------------------------------------------------------------
def is_broad_request(intent: str) -> bool:
    """True when the request is a project, not a property change."""
    return bool(BROAD_INTENT_RE.search(intent))


def extract_target_hints(intent: str) -> dict[str, Any]:
    """Pull the quoted label, element type, and descriptive words out of intent."""
    quoted = [m.group(1) for m in QUOTED_RE.finditer(intent)]

    wanted_tags: list[str] = []
    low = intent.lower()
    for tag, words in TAG_SYNONYMS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", low):
                wanted_tags.append(tag)
                break

    words = [
        w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{1,}", low)
        if w not in STOPWORDS and w not in NAMED_COLORS
    ]
    # Drop words that are only there to name the element type.
    synonym_words = {w for words_ in TAG_SYNONYMS.values() for w in words_}
    descriptors = [w for w in words if w not in synonym_words]

    return {"quoted": quoted, "tags": wanted_tags, "descriptors": descriptors}


def score_candidate(cand: dict[str, Any], hints: dict[str, Any]) -> tuple[int, list[str]]:
    """Higher is better. Reasons are surfaced so the match is explainable."""
    score, reasons = 0, []
    text = (cand.get("text") or "").lower()
    tag = cand.get("tag", "")
    # An <input> carries its identity in name/placeholder/label, not innerText.
    haystack = " ".join(
        [
            text,
            cand.get("id", ""),
            cand.get("name", ""),
            cand.get("placeholder", ""),
            cand.get("aria_label", ""),
            cand.get("label_text", ""),
            " ".join(cand.get("classes") or []),
        ]
    ).lower()

    for q in hints["quoted"]:
        if q.lower() in text:
            score += 60
            reasons.append(f'text matches "{q}"')

    if tag in hints["tags"]:
        # Earlier in the hint list means the user named it more specifically.
        score += 25 - hints["tags"].index(tag) * 3
        reasons.append(f"element is a <{tag}>")
    elif hints["tags"] and tag not in hints["tags"]:
        # A submit input is a button in everything but tag name.
        if "button" in hints["tags"] and (
            cand.get("role") == "button" or cand.get("type") == "submit"
        ):
            score += 20
            reasons.append("element behaves as a button")
        else:
            score -= 8

    for d in hints["descriptors"]:
        if len(d) < 3:
            continue
        if d in haystack:
            score += 18
            reasons.append(f"'{d}' appears in its text or class")

    if cand.get("id"):
        score += 6
    if text:
        score += 2
    # Prefer the specific control over the container that wraps it. A form's
    # innerText contains every label inside it, so it matches almost anything.
    if tag in {"form", "section", "nav", "header", "footer", "div"} and len(text) > 60:
        score -= 12
    return score, reasons


def resolve_target(
    candidates: list[dict[str, Any]], hints: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    """Return (best, alternatives, reasons)."""
    if not candidates:
        return None, [], []

    scored = []
    for c in candidates:
        s, why = score_candidate(c, hints)
        scored.append((s, why, c))
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best_why, best = scored[0]
    if best_score <= 0:
        return None, [c for _, _, c in scored[:3]], []

    alternatives = [c for s, _, c in scored[1:4] if s > 0]
    return best, alternatives, best_why


# --------------------------------------------------------------------------
# Step 4: what must not change
# --------------------------------------------------------------------------
def build_frozen_scope(
    target: dict[str, Any] | None, context: dict[str, Any]
) -> dict[str, Any]:
    tokens = list((context.get("tokens") or {}).keys())[:12]
    globals_ = context.get("globals") or {}

    frozen: dict[str, Any] = {
        "global_tokens": tokens,
        "global_font_family": globals_.get("font-family"),
        "body_background": globals_.get("body-background"),
        "parent_layout": None,
        "shared_selectors": [],
        "warnings": [],
    }

    if not target:
        return frozen

    parent = target.get("parent")
    if parent:
        frozen["parent_layout"] = {
            "selector": parent.get("selector"),
            "display": parent.get("display"),
            "flex-direction": parent.get("flex-direction"),
            "justify-content": parent.get("justify-content"),
            "align-items": parent.get("align-items"),
            "gap": parent.get("gap"),
        }

    shared = target.get("shared_classes") or []
    if shared:
        frozen["shared_selectors"] = shared
        worst = max(shared, key=lambda s: s["used_by"])
        if not target.get("id"):
            frozen["warnings"].append(
                f"This element has no id. Its class '.{worst['name']}' is used by "
                f"{worst['used_by']} elements, so editing that class would change "
                f"all of them. The prompt targets a single element instead."
            )
    return frozen


# --------------------------------------------------------------------------
# Step 5: assemble the surgical prompt
# --------------------------------------------------------------------------
def build_prompt(
    intent: str,
    selector: str | None,
    prop: str,
    value: str | None,
    current: str | None,
    frozen: dict[str, Any],
    element_label: str = "",
) -> str:
    target = selector or "the element described below"
    lines: list[str] = []

    if value:
        lines.append(
            f"Change ONLY the CSS `{prop}` of `{target}` to `{value}`."
        )
    else:
        lines.append(
            f"Change ONLY the CSS `{prop}` of `{target}`. "
            f"Requested change: {intent.strip()}"
        )

    if element_label:
        lines.append(f'That element is the one labelled "{element_label}".')
    if current:
        lines.append(f"Its current `{prop}` is `{current}`.")

    lines.append("")
    lines.append("DO NOT:")
    lines.append(f"- change any property of `{target}` other than `{prop}`")

    if frozen.get("parent_layout") and frozen["parent_layout"].get("selector"):
        p = frozen["parent_layout"]
        lines.append(
            f"- change the parent container `{p['selector']}` or its layout "
            f"(display: {p.get('display')}, flex-direction: {p.get('flex-direction')}, "
            f"justify-content: {p.get('justify-content')}, gap: {p.get('gap')})"
        )
    if frozen.get("global_tokens"):
        lines.append(
            "- change global design tokens: "
            + ", ".join(f"`{t}`" for t in frozen["global_tokens"])
        )
    if frozen.get("global_font_family"):
        lines.append(
            f"- change the site font family (`{frozen['global_font_family'][:60]}`)"
        )
    if frozen.get("shared_selectors"):
        names = ", ".join(
            f"`.{s['name']}` (used by {s['used_by']} elements)"
            for s in frozen["shared_selectors"][:3]
        )
        lines.append(f"- edit shared classes {names}; scope the change to this element only")

    lines.append("- restructure the HTML, rename classes, or reorder elements")
    lines.append("- modify any other page, component, or section")
    lines.append("")
    lines.append("Return only the single changed CSS rule. Do not rewrite the file.")

    return "\n".join(lines)


NAIVE_MULTIPLIER = 14  # a vague prompt makes the builder regenerate whole sections


def estimate_savings(prompt: str, intent: str) -> dict[str, Any]:
    """Rough token accounting, labelled as an estimate everywhere it is shown."""
    surgical_tokens = max(1, len(prompt) // 4)
    naive_tokens = max(surgical_tokens, (len(intent) // 4) * NAIVE_MULTIPLIER + 900)
    saved = max(0, naive_tokens - surgical_tokens)
    return {
        "surgical_tokens": surgical_tokens,
        "naive_tokens_estimate": naive_tokens,
        "tokens_saved_estimate": saved,
        "retries_avoided_estimate": 2 if saved > 800 else 1,
        "basis": (
            "Compares this scoped prompt against an unscoped one that typically "
            "makes the builder regenerate a whole section and get retried."
        ),
    }
