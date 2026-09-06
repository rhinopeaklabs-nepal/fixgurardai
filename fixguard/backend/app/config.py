"""Runtime configuration, loaded from environment with safe local defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("FIXGUARD_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "fixguard.db"

# Comma-separated origins allowed to call the API (the Web Hosting dashboard).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

# Public base URL of the dashboard, used to build shareable report links.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")

# Public base URL of this API, used by the embeddable badge script.
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")

# Single shared demo key for the hackathon build. Rotate before any public use.
API_KEY = os.getenv("FIXGUARD_API_KEY", "fixguard-dev-key")

# Set when the dashboard and the API are served from different subdomains of
# one site - ".example.com" makes the session cookie valid for both. Left
# empty the cookie is host-only, which is correct and safer for a same-origin
# deployment, so this is opt-in rather than derived.
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "").strip()

# --- Audit engine limits -------------------------------------------------
# Tuned for a 1 vCPU / 4 GB VPS: one browser at a time, hard ceilings on time.
MAX_CONCURRENT_AUDITS = int(os.getenv("MAX_CONCURRENT_AUDITS", "1"))
PAGE_LOAD_TIMEOUT_MS = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "20000"))
SETTLE_MS = int(os.getenv("SETTLE_MS", "4000"))          # watch window after load
POST_SUBMIT_WAIT_MS = int(os.getenv("POST_SUBMIT_WAIT_MS", "6000"))
MAX_FORMS_PER_AUDIT = int(os.getenv("MAX_FORMS_PER_AUDIT", "3"))
AUDIT_HARD_TIMEOUT_S = int(os.getenv("AUDIT_HARD_TIMEOUT_S", "90"))

# Navigation-loop heuristic: N navigations to the same URL inside W seconds.
LOOP_NAV_THRESHOLD = int(os.getenv("LOOP_NAV_THRESHOLD", "5"))
LOOP_NAV_WINDOW_S = float(os.getenv("LOOP_NAV_WINDOW_S", "3.0"))

SHARE_LINK_TTL_DAYS = int(os.getenv("SHARE_LINK_TTL_DAYS", "30"))

# Dev-only escape hatch so the local testbed can be audited. Never enable in prod.
ALLOW_PRIVATE_TARGETS = os.getenv("ALLOW_PRIVATE_TARGETS", "0") == "1"

# --- FR-3.1 route crawl / FR-3.2 re-render detection ---------------------
MAX_ROUTES_CRAWL = int(os.getenv("MAX_ROUTES_CRAWL", "5"))
ROUTE_TIMEOUT_MS = int(os.getenv("ROUTE_TIMEOUT_MS", "12000"))
MUTATION_THRESHOLD = int(os.getenv("MUTATION_THRESHOLD", "50"))   # per 2s window
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))
RENDER_SETTLE_MS = int(os.getenv("RENDER_SETTLE_MS", "1500"))

# --- Module 1: LLM (optional accuracy upgrade, never required) -----------
# FixGuard's scoping engine is deterministic and runs with no key at all.
# A model only improves intent parsing on unusual phrasing.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()   # anthropic|openai|none
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "20"))

# Auto-enable when a key is present but the provider was left unset.
if LLM_PROVIDER == "none" and LLM_API_KEY:
    LLM_PROVIDER = "anthropic" if LLM_API_KEY.startswith("sk-ant") else "openai"

# --- Reachability & TLS (FR-3.4, single-region) --------------------------
REACHABILITY_TIMEOUT_S = int(os.getenv("REACHABILITY_TIMEOUT_S", "10"))
REGION_LABEL = os.getenv("REGION_LABEL", "vps-primary")
TLS_EXPIRY_WARN_DAYS = int(os.getenv("TLS_EXPIRY_WARN_DAYS", "21"))

# --- Module 2: auto-reply capture (optional) -----------------------------
# Only works when MX for MAIL_DOMAIN points at this host's SMTP catcher.
MAILHOG_API = os.getenv("MAILHOG_API", "")          # e.g. http://mailhog:8025
MAIL_DOMAIN = os.getenv("MAIL_DOMAIN", "")          # e.g. inbox.fixguard.example
MAIL_POLL_SECONDS = int(os.getenv("MAIL_POLL_SECONDS", "30"))
