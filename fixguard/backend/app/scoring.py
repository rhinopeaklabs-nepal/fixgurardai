"""Health Score, per SRS FR-4.1.

Spec weights are used exactly as written: Form/SMTP 30, Router/Console 30,
Geo-Health 20, Asset 20.

Geo-Health is measured from a single host, so it covers DNS, TLS validity and
expiry, the redirect chain, status and latency - but not the cross-region
comparison the spec envisages, because that needs probes in three regions. The
breakdown states ``regions_measured`` so the coverage is never overstated. A
module the user did not select is excluded and the remaining weights are
renormalised, rather than being scored as a silent 100.

Grade bands are the spec's:
    >= 90 verified_healthy | 70-89 minor_issues | 50-69 needs_attention | < 50 critical

One extra rule keeps the number honest: a critical finding caps the composite
below the passing band (``CRITICAL_CEILING``). A site that silently drops
customer enquiries must never show a healthy score because its console is quiet.
"""
from __future__ import annotations

from typing import Any

# SRS FR-4.1 weights, used as written.
SPEC_WEIGHTS = {"form": 30, "router": 30, "geo": 20, "assets": 20}

# Categories added beyond the SRS. They are scored alongside the spec four and
# the whole set is renormalised, so the spec categories keep their relative
# weighting (30:30:20:20) whether or not these are selected.
EXTRA_WEIGHTS = {"a11y": 15, "perf": 15, "mobile": 15}

MEASURED = ("form", "router", "geo", "assets", "a11y", "perf", "mobile")
WEIGHTS = {**SPEC_WEIGHTS, **EXTRA_WEIGHTS}

# Any critical finding lands the site in the spec's "critical" band.
CRITICAL_CEILING = 49

# Categories that actually say something about a site's health. Reachability
# alone cannot certify anything: a login page resolves, serves 200 and has a
# valid certificate while telling you nothing about the site behind it.
SUBSTANTIVE = ("form", "router", "assets", "a11y", "perf", "mobile")

GRADE_BANDS = [
    (90, "verified_healthy", "Verified Healthy", "A"),
    (70, "minor_issues", "Minor Issues", "B"),
    (50, "needs_attention", "Needs Attention", "C"),
    (0, "critical", "Critical", "F"),
]

# Penalty per form verdict. The worst form dominates: one dead contact form is
# the story, however many other forms happen to work.
FORM_PENALTY = {
    "silent_failure": 100,
    "no_submission": 100,
    "js_crash": 90,
    "endpoint_error": 85,
    # Could not be tested rather than known broken, so it cannot be the
    # thing that caps a site at "critical".
    "blocked_by_protection": 25,
    "error_shown": 50,
    "no_submit_control": 40,
    "no_feedback": 20,
    "submit_click_failed": 20,
    "probe_error": 10,
    "skipped": 0,
    "pass": 0,
}


def _forms_score(form_results: list[dict[str, Any]]) -> tuple[int, list[str]]:
    notes: list[str] = []
    tested = [f for f in form_results if not f.get("skipped")]
    if not tested:
        notes.append(
            "Forms found but none could be safely tested."
            if form_results
            else "No forms found on this page."
        )
        return 100, notes

    worst = 0
    for f in tested:
        p = FORM_PENALTY.get(f.get("verdict") or "", 15)
        worst = max(worst, p)
        if p >= 85:
            notes.append(
                f"Form {f.get('form_index', 0) + 1}: {f.get('verdict')} "
                f"({f.get('heading') or 'untitled'})"
            )
    return max(0, 100 - worst), notes


def _router_score(
    router: dict[str, Any], console_errors: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    """SRS bundles routing and console health into one 30% category."""
    notes: list[str] = []
    score = 100

    if router.get("throttling_warning_detected"):
        score -= 70
        notes.append("Browser emitted a navigation throttling warning.")
    if router.get("loop_count", 0) >= 5:
        score -= 60
        notes.append(
            f"{router['loop_count']} navigations to {router.get('loop_url')} "
            f"within {router.get('window_seconds')}s."
        )

    rerender = router.get("rerender") or {}
    if rerender.get("suspected_infinite_rerender"):
        score -= 40
        notes.append(
            f"{rerender.get('peak_mutations_in_window')} DOM mutations in "
            f"{rerender.get('window_ms')}ms suggests a re-render loop."
        )

    broken = router.get("broken_routes_list") or []
    if broken:
        score -= min(30, len(broken) * 10)
        notes.append(f"{len(broken)} broken route(s): {', '.join(broken[:4])}")

    critical = [c for c in console_errors if c.get("severity") == "critical"]
    warnings = [c for c in console_errors if c.get("severity") == "warning"]
    score -= min(50, len(critical) * 10)
    score -= min(15, len(warnings) * 3)
    if critical:
        notes.append(f"{len(critical)} critical console error(s).")
    if warnings:
        notes.append(f"{len(warnings)} console warning(s).")

    return max(0, score), notes


def _assets_score(asset_issues: list[dict[str, Any]]) -> tuple[int, list[str]]:
    if not asset_issues:
        return 100, []
    return (
        max(0, 100 - min(80, len(asset_issues) * 15)),
        [f"{len(asset_issues)} asset(s) failed to load."],
    )


def has_critical(result: dict[str, Any]) -> bool:
    reach = result.get("reachability") or {}
    if reach.get("dns_resolved") is False or reach.get("ip_blocked"):
        return True
    if (reach.get("tls") or {}).get("valid") is False:
        return True
    if any(f.get("severity") == "critical" for f in result.get("form_results") or []):
        return True
    router = result.get("router_result") or {}
    if router.get("has_navigation_loop"):
        return True
    if (router.get("rerender") or {}).get("suspected_infinite_rerender"):
        return True
    for key in ("mobile", "accessibility"):
        for g in (result.get(key) or {}).get("groups") or []:
            if g.get("impact") == "critical":
                return True
    return False


def compute(result: dict[str, Any]) -> dict[str, Any]:
    from . import reachability

    console_errors = result.get("console_errors") or []
    router_result = result.get("router_result") or {}
    reach = result.get("reachability") or {}

    EXTRA = {"a11y": "accessibility", "perf": "performance", "mobile": "mobile"}

    form, n_form = _forms_score(result.get("form_results") or [])
    router, n_router = _router_score(router_result, console_errors)
    geo, n_geo = reachability.score(reach) if reach else (100, [])
    assets, n_assets = _assets_score(result.get("asset_issues") or [])

    a11y_r = result.get("accessibility") or {}
    perf_r = result.get("performance") or {}
    mob_r = result.get("mobile") or {}

    scores = {
        "form": form, "router": router, "geo": geo, "assets": assets,
        "a11y": a11y_r.get("score", 100),
        "perf": perf_r.get("score", 100),
        "mobile": mob_r.get("score", 100),
    }

    # A module that was deselected or could not run is excluded rather than
    # scored as a silent 100; the remaining weights are renormalised.
    selected = set(result.get("modules_selected") or MEASURED)
    failed = set(result.get("modules_failed") or ())
    module_for = {
        "form": "form", "router": "router", "assets": "assets", "geo": "reach",
        "a11y": "a11y", "perf": "perf", "mobile": "mobile",
    }

    def _measured(cat: str) -> tuple[bool, str | None]:
        mod = module_for[cat]
        if mod in failed:
            return False, f"The {mod} module could not run on this target."
        if mod not in selected:
            return False, f"The {mod} module was not selected."
        if cat == "geo" and not reach:
            return False, "The reachability module produced no result."
        if cat in EXTRA and not (result.get(EXTRA[cat]) or {}).get("measured"):
            return False, f"The {mod} module produced no result."
        return True, None

    breakdown = {}
    for k in MEASURED:
        ok, why = _measured(k)
        breakdown[k] = {
            "score": scores[k] if ok else None,
            "weight": WEIGHTS[k],
            # Only the four SRS categories carry a spec weight; the rest are
            # additions and are labelled as such rather than implying the spec
            # asked for them.
            "spec_weight": SPEC_WEIGHTS.get(k),
            "in_spec": k in SPEC_WEIGHTS,
            "measured": ok,
        }
        if why:
            breakdown[k]["reason"] = why
    if reach and breakdown["geo"]["measured"]:
        # Honest about coverage: one region, not the three the spec asks for.
        breakdown["geo"]["regions_measured"] = reach.get("regions_measured", 1)
        breakdown["geo"]["regions_requested"] = reach.get("regions_requested", 3)
        breakdown["geo"]["note"] = reach.get("multi_region_note")

    active = [k for k in MEASURED if breakdown[k]["measured"]]
    substantive = [k for k in active if k in SUBSTANTIVE]

    # Nothing that describes the site itself could be measured. Emitting a
    # number here would be the worst failure this tool can have: a site nobody
    # could even open, certified healthy because its DNS resolved.
    if not substantive:
        return {
            "form_score": None,
            "router_score": None,
            "geo_score": geo if breakdown["geo"]["measured"] else None,
            "asset_score": None,
            "a11y_score": None,
            "perf_score": None,
            "mobile_score": None,
            "composite_score": None,
            "grade": "not_assessed",
            "letter": "?",
            "label": "Not assessed",
            "breakdown": breakdown,
            "notes": n_geo,
            "capped_by_critical": False,
            "partial": True,
            "partial_reason": result.get("partial_reason"),
            "not_assessed_reason": (
                "The page itself could not be opened, so nothing about the "
                "site's health was measured. Only its address was checked."
            ),
        }

    weight_total = sum(WEIGHTS[k] for k in active) or 1
    composite = round(sum(scores[k] * WEIGHTS[k] for k in active) / weight_total)

    capped = False
    if has_critical(result) and composite > CRITICAL_CEILING:
        composite = CRITICAL_CEILING
        capped = True
    composite = max(0, min(100, composite))

    grade, label, letter = "critical", "Critical", "F"
    for threshold, g, l, ltr in GRADE_BANDS:
        if composite >= threshold:
            grade, label, letter = g, l, ltr
            break

    return {
        # SRS health_scores column names
        "form_score": form if breakdown["form"]["measured"] else None,
        "router_score": router if breakdown["router"]["measured"] else None,
        "geo_score": geo if breakdown["geo"]["measured"] else None,
        "asset_score": assets if breakdown["assets"]["measured"] else None,
        "a11y_score": scores["a11y"] if breakdown["a11y"]["measured"] else None,
        "perf_score": scores["perf"] if breakdown["perf"]["measured"] else None,
        "mobile_score": scores["mobile"] if breakdown["mobile"]["measured"] else None,
        "composite_score": composite,
        "grade": grade,
        # presentation extras
        "letter": letter,
        "label": label,
        "breakdown": breakdown,
        "notes": (
            n_form + n_router + n_geo + n_assets
            + (a11y_r.get("notes") or [])
            + (perf_r.get("notes") or [])
            + (mob_r.get("notes") or [])
        ),
        "capped_by_critical": capped,
        "partial": bool(result.get("modules_failed")),
        "partial_reason": result.get("partial_reason"),
    }
