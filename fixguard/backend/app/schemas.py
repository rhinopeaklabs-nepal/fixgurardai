"""Request/response models, following the SRS section 8 contract."""
from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from .config import ALLOW_PRIVATE_TARGETS

PRIVATE_HOST_PREFIXES = (
    "localhost", "127.", "0.", "10.", "192.168.", "169.254.",
    "::1", "[::1]", "metadata.google.internal",
)

Module = Literal["form", "router", "assets", "reach", "a11y", "perf", "mobile"]
ALL_MODULES: list[str] = [
    "form", "router", "assets", "reach", "a11y", "perf", "mobile",
]


def validate_target_url(v: str, field: str = "domain_url") -> str:
    """Shared by every endpoint that accepts a target address."""
    v = (v or "").strip()
    if not v:
        raise ValueError(f"{field} is required")

    # Only add a scheme when there is genuinely none. Blindly prefixing turns
    # "ftp://x" into "https://ftp://x", which parses as valid.
    if "://" in v:
        scheme = v.split("://", 1)[0].lower()
        if scheme not in {"http", "https"}:
            raise ValueError(f"Only http and https URLs are supported, not {scheme}")
    else:
        v = "https://" + v

    p = urlparse(v)
    if p.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported")

    host = p.hostname
    if not host:
        raise ValueError(f"{field} has no host")
    if ":" in p.netloc.rsplit("]", 1)[-1].lstrip(":"):
        port = p.netloc.rsplit(":", 1)[-1]
        if not port.isdigit():
            raise ValueError(f"{field} is not a valid address")
    if not ALLOW_PRIVATE_TARGETS:
        if any(host.startswith(pfx) for pfx in PRIVATE_HOST_PREFIXES):
            raise ValueError("Private and loopback addresses are not auditable")
        if "." not in host:
            raise ValueError(f"{field} must be a fully qualified domain")
    return v


class StartAuditRequest(BaseModel):
    """SRS 8.2 POST /api/v1/audits/start."""

    domain_url: str = Field(..., max_length=2048)
    modules: list[Module] = Field(default_factory=lambda: list(ALL_MODULES))
    # FR-2.1. Matched against the forms found on the page; a selector that
    # matches nothing falls back to testing them all and says so in notes.
    form_selector: str | None = Field(default=None, max_length=200)
    test_email: str | None = Field(default=None, max_length=254)
    auth: AuthSpec | None = None
    max_pages: int = Field(
        default=1, ge=1, le=30,
        description="Audit this many pages, following internal links from the target.",
    )
    i_own_this_site: bool = Field(
        ...,
        description=(
            "Must be true. The audit fills and submits forms on the target, "
            "so the caller has to confirm they own it or have permission."
        ),
    )

    @field_validator("domain_url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        return validate_target_url(v, "domain_url")

    @field_validator("modules")
    @classmethod
    def _at_least_one(cls, v: list[str]) -> list[str]:
        return v or list(ALL_MODULES)

    @field_validator("i_own_this_site")
    @classmethod
    def _must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "You must confirm you own this site or have permission to test it"
            )
        return v


class AuthSpec(BaseModel):
    """A session to audit with. Never a password.

    The user signs in themselves and hands over the resulting cookies, so
    nothing here can be reused to sign in again after it expires.
    """

    cookie_header: str | None = Field(
        default=None,
        max_length=8000,
        description="Paste the Cookie header from your signed-in browser.",
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description="Extra request headers, e.g. an Authorization bearer token.",
    )
    verify_text: str | None = Field(
        default=None,
        max_length=120,
        description="Text that only appears when signed in, e.g. your account name.",
    )
    submit_forms: bool = Field(
        default=False,
        description=(
            "Submit forms behind the login. Off by default: a signed-in form "
            "may change settings or delete data rather than send a message."
        ),
    )

    @field_validator("headers")
    @classmethod
    def _check_headers(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if not v:
            return v
        if len(v) > 10:
            raise ValueError("At most 10 extra headers")
        banned = {"host", "content-length", "cookie"}
        for k in v:
            if k.lower() in banned:
                raise ValueError(f"The {k} header cannot be set here")
        return v


class SurgifyRequest(BaseModel):
    """SRS FR-1.1: intent plus at least one form of context."""

    intent: str = Field(..., min_length=1, max_length=500)
    page_url: str | None = Field(default=None, max_length=2048)
    code_context: str | None = Field(default=None, max_length=200_000)
    target_selector: str | None = Field(default=None, max_length=200)
    use_model: bool = True

    @field_validator("page_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return validate_target_url(v, "page_url") if v else v


class FromAuditRequest(BaseModel):
    """Accepts an audit id or a share token, so a pasted link works."""

    audit_id: str = Field(..., min_length=8, max_length=200)

    @field_validator("audit_id")
    @classmethod
    def _strip_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        # Tolerate a full dashboard URL: /a/<id> or /r/<token>
        for marker in ("/a/", "/r/"):
            if marker in v:
                v = v.split(marker, 1)[1]
        return v.split("?")[0].split("#")[0]


class StartAuditResponse(BaseModel):
    audit_id: str
    status: str
    sse_url: str
    modules: list[str]
    rate_limit_remaining: int


class AuditStatusResponse(BaseModel):
    """SRS 8.2 GET /api/v1/audits/:id/status."""

    audit_id: str
    status: str
    current_step: str | None = None
    progress_percent: int = 0
    modules_complete: list[str] = Field(default_factory=list)
    modules_pending: list[str] = Field(default_factory=list)
    health_score: int | None = None
    grade: str | None = None
    retryable: bool = False
    error_code: str | None = None
    created_at: str
    completed_at: str | None = None


class ShareResponse(BaseModel):
    token: str
    share_url: str
    expires_at: str


def status_view(run: dict[str, Any]) -> dict[str, Any]:
    selected = run.get("modules_selected") or ALL_MODULES
    complete = run.get("modules_complete") or []
    return {
        "audit_id": run["id"],
        "status": run["status"],
        "current_step": run.get("stage"),
        "progress_percent": run.get("progress_percent") or 0,
        "modules_complete": complete,
        "modules_pending": [m for m in selected if m not in complete],
        "health_score": run.get("health_score"),
        "grade": run.get("grade"),
        "retryable": bool(run.get("retryable")),
        "error_code": run.get("error_code"),
        "created_at": run["created_at"],
        "completed_at": run.get("completed_at"),
    }


def public_view(run: dict[str, Any], mode: str = "client") -> dict[str, Any]:
    """Shared report projection.

    ``client`` is the simplified executive view; ``developer`` adds the
    technical detail (FR-4.3 toggle modes). Neither echoes the submitted
    payload back to an anonymous viewer.
    """
    forms = [
        {
            "form_index": f.get("form_index"),
            "heading": f.get("heading"),
            "verdict": f.get("verdict"),
            "severity": f.get("severity"),
            "explanation": f.get("explanation"),
            "skipped": f.get("skipped", False),
            **(
                {
                    "submission_requests": f.get("submission_requests"),
                    "success_text_shown": f.get("success_text_shown"),
                    "js_errors_on_submit": f.get("js_errors_on_submit"),
                    "field_count": f.get("field_count"),
                }
                if mode == "developer"
                else {}
            ),
        }
        for f in run.get("form_results") or []
    ]

    router = run.get("router_result") or {}
    out: dict[str, Any] = {
        "audit_id": run["id"],
        "target_url": run["target_url"],
        "status": run["status"],
        "mode": mode,
        "health_score": run.get("health_score"),
        "grade": run.get("grade"),
        "score_breakdown": run.get("score_breakdown"),
        "forms": forms,
        "router": {
            "has_navigation_loop": router.get("has_navigation_loop"),
            "loop_count": router.get("loop_count"),
            "page_load_blocked_by_loop": router.get("page_load_blocked_by_loop"),
            "rerender": router.get("rerender"),
            "broken_routes_list": router.get("broken_routes_list") or [],
            "routes_crawled": router.get("routes_crawled", 0),
        },
        "reachability": _reach_view(run.get("reachability"), mode),
        "site_map": run.get("site_map") if mode == "developer" else None,
        "accessibility": run.get("accessibility"),
        "performance": run.get("performance"),
        "mobile": run.get("mobile"),
        "pages_audited": run.get("pages_audited") or 1,
        "executive_summary": run.get("executive_summary"),
        "partial_reason": run.get("partial_reason"),
        "modules_failed": run.get("modules_failed") or [],
        "console_error_count": len(run.get("console_errors") or []),
        "asset_issue_count": len(run.get("asset_issues") or []),
        "created_at": run["created_at"],
        "completed_at": run.get("completed_at"),
    }

    if mode == "developer":
        out["parsed_errors"] = run.get("parsed_errors") or []
        out["console_errors"] = run.get("console_errors") or []
        out["asset_issues"] = run.get("asset_issues") or []
        out["routes_map"] = router.get("routes_map") or []
        out["throttling_messages"] = router.get("throttling_messages") or []

    return out


def _reach_view(reach: dict[str, Any] | None, mode: str) -> dict[str, Any] | None:
    """Reachability projection. IP addresses stay out of the client view."""
    if not reach:
        return None
    base = {
        "status_code": reach.get("status_code"),
        "response_time_ms": reach.get("response_time_ms"),
        "dns_resolved": reach.get("dns_resolved"),
        "ip_blocked": reach.get("ip_blocked"),
        "tls_valid": (reach.get("tls") or {}).get("valid"),
        "tls_days_remaining": (reach.get("tls") or {}).get("days_remaining"),
        "issues": reach.get("issues") or [],
        "regions_measured": reach.get("regions_measured"),
        "regions_requested": reach.get("regions_requested"),
        "multi_region_note": reach.get("multi_region_note"),
    }
    if mode == "developer":
        base["ip_addresses"] = reach.get("ip_addresses") or []
        base["redirect_chain"] = reach.get("redirect_chain") or []
        base["tls"] = reach.get("tls")
        base["region_code"] = reach.get("region_code")
    return base
