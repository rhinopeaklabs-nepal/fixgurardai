"""Type-aware synthetic values for form fields.

Every value is self-identifying so that if a submission does reach a real
inbox, the recipient immediately understands it was an automated test.
"""
from __future__ import annotations

import datetime as _dt
import re

TEST_MARKER = "FixGuard AI automated site test - please ignore"

# Field-name hints checked against name/id/placeholder/label, in priority order.
_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"first[\s_-]*name|fname|given", re.I), "FixGuard"),
    (re.compile(r"last[\s_-]*name|lname|surname|family", re.I), "Test"),
    (re.compile(r"full[\s_-]*name|your[\s_-]*name|\bname\b", re.I), "FixGuard Test"),
    (re.compile(r"compan|business|organi[sz]ation|employer", re.I), "FixGuard AI"),
    (re.compile(r"subject|topic|regarding", re.I), TEST_MARKER),
    (re.compile(r"message|comment|enquiry|inquiry|details|question|body|note",
                re.I), TEST_MARKER),
    (re.compile(r"phone|mobile|tel\b|contact[\s_-]*number", re.I), "+15550100123"),
    (re.compile(r"e[-_\s]?mail", re.I), None),   # handled by type branch
    (re.compile(r"zip|postal|postcode", re.I), "10001"),
    (re.compile(r"city|town", re.I), "Testville"),
    (re.compile(r"address|street", re.I), "1 Test Street"),
    (re.compile(r"website|url|homepage", re.I), "https://example.com"),
    (re.compile(r"budget|amount|price|qty|quantity|number|age", re.I), "1"),
]

# Inputs that mean "this is not a contact form" - never auto-submit these.
SENSITIVE_TYPES = {"password"}
SENSITIVE_NAME = re.compile(
    r"password|passwd|\bpin\b|\bcvv\b|\bcvc\b|card[\s_-]*number|cardnum|"
    r"credit[\s_-]*card|\biban\b|routing|ssn|social[\s_-]*security|"
    r"account[\s_-]*number|secret|token|api[\s_-]*key",
    re.I,
)


def is_sensitive(field: dict) -> bool:
    """True if a field implies credentials or payment data."""
    if (field.get("type") or "").lower() in SENSITIVE_TYPES:
        return True
    haystack = " ".join(
        str(field.get(k) or "")
        for k in ("name", "id", "placeholder", "label", "autocomplete")
    )
    return bool(SENSITIVE_NAME.search(haystack))


def value_for(field: dict, test_email: str) -> str | bool | None:
    """Pick a synthetic value for one parsed field descriptor."""
    ftype = (field.get("type") or "text").lower()
    tag = (field.get("tag") or "input").lower()

    if ftype in {"checkbox", "radio"}:
        return True
    if ftype == "email":
        return test_email
    if ftype == "tel":
        return "+15550100123"
    if ftype == "number" or ftype == "range":
        return "1"
    if ftype == "date":
        return _dt.date.today().isoformat()
    if ftype == "datetime-local":
        return _dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
    if ftype == "time":
        return "12:00"
    if ftype == "url":
        return "https://example.com"
    if tag == "textarea":
        return TEST_MARKER

    haystack = " ".join(
        str(field.get(k) or "")
        for k in ("name", "id", "placeholder", "label", "autocomplete")
    )
    for pattern, value in _HINTS:
        if pattern.search(haystack):
            if value is None:          # an email-ish text input
                return test_email
            return value

    return "FixGuard test"
