"""Scoring and interpretation for the quality detectors.

The browser collects raw numbers; this decides what they mean. Thresholds come
from published guidance rather than invented ones:

* Core Web Vitals: Google's "good" thresholds (LCP 2.5s, CLS 0.1, TBT 200ms).
* Contrast and tap targets: WCAG 2.2 AA.
"""
from __future__ import annotations

from typing import Any

# Google's Core Web Vitals thresholds: (good, needs-improvement) upper bounds.
VITAL_BANDS = {
    "lcp_ms": (2500, 4000),
    "cls": (0.1, 0.25),
    "tbt_ms": (200, 600),
    "fcp_ms": (1800, 3000),
}

IMPACT_WEIGHT = {"critical": 25, "serious": 12, "moderate": 5, "minor": 2}


def _band(metric: str, value: float | None) -> str:
    if value is None:
        return "unknown"
    good, poor = VITAL_BANDS[metric]
    if value <= good:
        return "good"
    return "needs_improvement" if value <= poor else "poor"


def assess_vitals(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Interpret the raw timings, and score them."""
    if not raw:
        return {"measured": False}

    bands = {m: _band(m, raw.get(m)) for m in VITAL_BANDS}
    notes: list[str] = []
    score = 100

    for metric, band in bands.items():
        if band == "needs_improvement":
            score -= 12
        elif band == "poor":
            score -= 25

    if bands["lcp_ms"] != "good" and raw.get("lcp_ms"):
        notes.append(
            f"Largest content took {raw['lcp_ms'] / 1000:.1f}s to appear "
            "(2.5s or less is considered good)."
        )
    if bands["cls"] != "good":
        notes.append(
            f"Layout shifted by {raw.get('cls')} while loading, so content moves "
            "under the reader (0.1 or less is good)."
        )
    if bands["tbt_ms"] != "good" and raw.get("tbt_ms"):
        notes.append(
            f"Scripts blocked the page for {raw['tbt_ms']}ms, during which taps "
            "do nothing (200ms or less is good)."
        )
    nodes = raw.get("dom_nodes") or 0
    if nodes > 1500:
        score -= 5
        notes.append(f"The page has {nodes} DOM nodes, which slows rendering.")

    return {
        "measured": True,
        "metrics": raw,
        "bands": bands,
        "score": max(0, min(100, score)),
        "notes": notes,
    }


def _score_issues(issues: list[dict[str, Any]]) -> int:
    penalty = 0
    for i in issues:
        penalty += IMPACT_WEIGHT.get(i.get("impact", "minor"), 2)
    return max(0, 100 - min(100, penalty))


def _group(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeats of the same rule so the report stays readable."""
    buckets: dict[str, dict[str, Any]] = {}
    for i in issues:
        rule = i.get("rule", "other")
        b = buckets.setdefault(
            rule,
            {
                "rule": rule,
                "impact": i.get("impact", "minor"),
                "message": i.get("message", ""),
                "count": 0,
                "examples": [],
            },
        )
        b["count"] += 1
        if len(b["examples"]) < 4:
            b["examples"].append(
                {
                    "selector": i.get("selector"),
                    "snippet": i.get("snippet"),
                    "message": i.get("message"),
                }
            )
        # Keep the worst impact seen for this rule.
        if IMPACT_WEIGHT.get(i.get("impact"), 0) > IMPACT_WEIGHT.get(b["impact"], 0):
            b["impact"] = i["impact"]
    out = list(buckets.values())
    out.sort(key=lambda b: -IMPACT_WEIGHT.get(b["impact"], 0))
    return out


def assess_a11y(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {"measured": False}
    issues = raw.get("issues") or []
    groups = _group(issues)
    return {
        "measured": True,
        "score": _score_issues(issues),
        "issue_count": len(issues),
        "groups": groups,
        "contrast_samples": raw.get("contrast_samples", 0),
        "notes": [
            f"{g['count']}x {g['rule']}: {g['message']}"
            for g in groups[:4]
        ],
    }


def assess_mobile(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {"measured": False}
    issues = raw.get("issues") or []
    groups = _group(issues)
    return {
        "measured": True,
        "score": _score_issues(issues),
        "issue_count": len(issues),
        "groups": groups,
        "viewport_width": raw.get("viewport_width"),
        "page_width": raw.get("page_width"),
        "notes": [f"{g['count']}x {g['rule']}: {g['message']}" for g in groups[:4]],
    }
