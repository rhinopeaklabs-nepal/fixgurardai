"""Compare two audits of the same site.

This is what turns a report into evidence. A score on its own says "your site
has problems"; a comparison says "you fixed the contact form and the score went
from 39 to 92", which is the only claim that proves the tool did anything.

Findings are reduced to stable keys so the same problem seen twice matches even
though its wording, counts or ordering changed.
"""
from __future__ import annotations

from typing import Any

CATEGORY_LABELS = {
    "form": "Forms",
    "router": "Navigation & console",
    "geo": "Reachability",
    "assets": "Assets",
    "a11y": "Accessibility",
    "perf": "Performance",
    "mobile": "Mobile layout",
}

SEVERITY_RANK = {"critical": 0, "serious": 1, "warning": 1, "moderate": 2, "minor": 3, "info": 4}


def _finding_keys(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every problem in an audit, keyed so it can be matched across runs."""
    out: dict[str, dict[str, Any]] = {}

    def put(key: str, severity: str, label: str, detail: str = "") -> None:
        out[key] = {"key": key, "severity": severity, "label": label, "detail": detail}

    for f in run.get("form_results") or []:
        verdict = f.get("verdict")
        if not verdict or verdict in {"pass", "skipped"}:
            continue
        name = f.get("heading") or f.get("submit_text") or f"form {f.get('form_index')}"
        put(
            f"form:{verdict}:{name}",
            f.get("severity") or "warning",
            f'Form "{name}": {verdict.replace("_", " ")}',
            f.get("explanation") or "",
        )

    router = run.get("router_result") or {}
    if router.get("has_navigation_loop"):
        put("router:navigation_loop", "critical", "Redirect loop",
            f"{router.get('loop_count')} navigations to the same URL")
    if (router.get("rerender") or {}).get("suspected_infinite_rerender"):
        put("router:rerender", "critical", "Infinite re-render",
            f"{router['rerender'].get('peak_mutations_in_window')} DOM changes per window")
    for path in router.get("broken_routes_list") or []:
        put(f"route:{path}", "warning", f"Broken link {path}")

    for c in run.get("console_errors") or []:
        if c.get("severity") != "critical":
            continue
        msg = (c.get("message") or "")[:90]
        put(f"console:{msg}", "warning", "JavaScript error", msg)

    for a in run.get("asset_issues") or []:
        url = (a.get("url") or "")[-70:]
        put(f"asset:{url}", "warning", f"Asset fails to load: {url}")

    for key, prefix in (("accessibility", "a11y"), ("mobile", "mobile")):
        for g in (run.get(key) or {}).get("groups") or []:
            put(
                f"{prefix}:{g.get('rule')}",
                g.get("impact") or "moderate",
                f"{CATEGORY_LABELS.get(prefix, prefix)}: {g.get('rule')}",
                f"{g.get('count')}x - {g.get('message', '')}",
            )

    reach = run.get("reachability") or {}
    for issue in reach.get("issues") or []:
        put(f"reach:{issue[:70]}", "warning", "Reachability", issue)

    perf = run.get("performance") or {}
    for metric, band in (perf.get("bands") or {}).items():
        if band in {"needs_improvement", "poor"}:
            put(f"perf:{metric}", "moderate" if band == "needs_improvement" else "serious",
                f"Performance: {metric.replace('_ms', '').upper()} is {band.replace('_', ' ')}",
                str((perf.get("metrics") or {}).get(metric)))

    return out


def _delta(after: int | None, before: int | None) -> int | None:
    if after is None or before is None:
        return None
    return after - before


def build(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Diff two completed audits, oldest first."""
    b_keys = _finding_keys(before)
    a_keys = _finding_keys(after)

    resolved = [b_keys[k] for k in b_keys.keys() - a_keys.keys()]
    introduced = [a_keys[k] for k in a_keys.keys() - b_keys.keys()]
    remaining = [a_keys[k] for k in a_keys.keys() & b_keys.keys()]

    for group in (resolved, introduced, remaining):
        group.sort(key=lambda f: SEVERITY_RANK.get(f["severity"], 5))

    b_sb = before.get("score_breakdown") or {}
    a_sb = after.get("score_breakdown") or {}
    b_bd = b_sb.get("breakdown") or {}
    a_bd = a_sb.get("breakdown") or {}

    categories = []
    for cat, label in CATEGORY_LABELS.items():
        bb, ab = b_bd.get(cat) or {}, a_bd.get(cat) or {}
        if not bb.get("measured") and not ab.get("measured"):
            continue
        categories.append(
            {
                "category": cat,
                "label": label,
                "before": bb.get("score"),
                "after": ab.get("score"),
                "delta": _delta(ab.get("score"), bb.get("score")),
            }
        )

    b_score = before.get("health_score")
    a_score = after.get("health_score")
    delta = _delta(a_score, b_score)

    if delta is None:
        verdict, headline = "unknown", "These audits cannot be compared."
    elif delta > 0 and not introduced:
        verdict = "improved"
        headline = (
            f"The score rose {delta} points, from {b_score} to {a_score}, "
            f"and {len(resolved)} issue(s) were fixed with none introduced."
        )
    elif delta > 0:
        verdict = "improved"
        headline = (
            f"The score rose {delta} points to {a_score}. "
            f"{len(resolved)} issue(s) fixed, but {len(introduced)} new one(s) appeared."
        )
    elif delta < 0:
        verdict = "regressed"
        headline = (
            f"The score fell {abs(delta)} points to {a_score}. "
            f"{len(introduced)} new issue(s) appeared."
        )
    elif resolved or introduced:
        verdict = "changed"
        headline = (
            f"The score is unchanged at {a_score}, but the findings differ: "
            f"{len(resolved)} fixed, {len(introduced)} new."
        )
    else:
        verdict = "unchanged"
        headline = f"Nothing changed. The score is still {a_score}."

    return {
        "verdict": verdict,
        "headline": headline,
        "target_url": after.get("target_url"),
        "before": {
            "audit_id": before.get("id"),
            "score": b_score,
            "grade": before.get("grade"),
            "at": before.get("completed_at") or before.get("created_at"),
        },
        "after": {
            "audit_id": after.get("id"),
            "score": a_score,
            "grade": after.get("grade"),
            "at": after.get("completed_at") or after.get("created_at"),
        },
        "score_delta": delta,
        "categories": categories,
        "resolved": resolved,
        "introduced": introduced,
        "remaining": remaining,
        "counts": {
            "resolved": len(resolved),
            "introduced": len(introduced),
            "remaining": len(remaining),
        },
    }
