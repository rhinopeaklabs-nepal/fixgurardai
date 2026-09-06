"""SQLite persistence. Plain sqlite3 - one writer, tiny row counts, no ORM needed."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from .config import DB_PATH

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS audit_runs (
    id                TEXT PRIMARY KEY,
    target_url        TEXT NOT NULL,
    status            TEXT NOT NULL,          -- queued|running|complete|failed
    stage             TEXT,                   -- human-readable current step
    progress_percent  INTEGER DEFAULT 0,
    modules_selected  TEXT,                   -- json list: form|router|assets
    modules_complete  TEXT,                   -- json list
    error_code        TEXT,
    error_detail      TEXT,
    retryable         INTEGER DEFAULT 0,
    retry_of          TEXT,                   -- id of the run this retries
    health_score      INTEGER,
    grade             TEXT,
    score_breakdown   TEXT,                   -- json
    console_errors    TEXT,                   -- json list
    router_result     TEXT,                   -- json object
    form_results      TEXT,                   -- json list
    asset_issues      TEXT,                   -- json list
    duration_ms       INTEGER,
    created_at        TEXT NOT NULL,
    completed_at      TEXT
);

CREATE TABLE IF NOT EXISTS rate_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash    TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rate_key ON rate_events(key_hash, occurred_at);

CREATE TABLE IF NOT EXISTS share_links (
    token       TEXT PRIMARY KEY,
    audit_id    TEXT NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS surgical_prompts (
    id                    TEXT PRIMARY KEY,
    original_intent       TEXT NOT NULL,
    guarded_prompt        TEXT NOT NULL,
    scope_boundary        TEXT,               -- json
    target_selector       TEXT,
    css_property          TEXT,
    css_value             TEXT,
    source_url            TEXT,
    confidence            REAL,
    tokens_saved_estimate INTEGER,
    engine                TEXT,               -- rules | model
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    provider    TEXT,
    model_id    TEXT,
    input_text  TEXT,
    output_text TEXT,
    latency_ms  INTEGER,
    ok          INTEGER,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_ping_results (
    id               TEXT PRIMARY KEY,
    audit_id         TEXT NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    region_code      TEXT NOT NULL,
    status_code      INTEGER,
    response_time_ms INTEGER,
    ip_blocked       INTEGER DEFAULT 0,
    ssl_valid        INTEGER,
    dns_resolved     INTEGER,
    detail           TEXT,                    -- json
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_share_audit ON share_links(audit_id);
CREATE INDEX IF NOT EXISTS idx_prompts_created ON surgical_prompts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_calls ON agent_calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_geo_audit ON geo_ping_results(audit_id);
CREATE INDEX IF NOT EXISTS idx_runs_created ON audit_runs(created_at DESC);
"""

JSON_COLUMNS = {
    "score_breakdown",
    "console_errors",
    "router_result",
    "form_results",
    "asset_issues",
    "modules_selected",
    "modules_complete",
    "reachability",
    "parsed_errors",
    "modules_failed",
    "accessibility",
    "performance",
    "mobile",
    "pages",
    "site_map",
    "auth_info",
}

# Columns added after the first release; applied to existing databases on boot.
MIGRATIONS = [
    ("audit_runs", "progress_percent", "INTEGER DEFAULT 0"),
    ("audit_runs", "modules_selected", "TEXT"),
    ("audit_runs", "modules_complete", "TEXT"),
    ("audit_runs", "retryable", "INTEGER DEFAULT 0"),
    ("audit_runs", "retry_of", "TEXT"),
    ("audit_runs", "reachability", "TEXT"),
    ("audit_runs", "executive_summary", "TEXT"),
    ("audit_runs", "parsed_errors", "TEXT"),
    ("audit_runs", "modules_failed", "TEXT"),
    ("audit_runs", "partial_reason", "TEXT"),
    ("audit_runs", "accessibility", "TEXT"),
    ("audit_runs", "performance", "TEXT"),
    ("audit_runs", "mobile", "TEXT"),
    ("audit_runs", "pages", "TEXT"),
    ("audit_runs", "pages_audited", "INTEGER DEFAULT 1"),
    ("audit_runs", "site_map", "TEXT"),
    ("audit_runs", "auth_info", "TEXT"),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """One connection per thread; FastAPI's threadpool reuses threads."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        for table, column, decl in MIGRATIONS:
            existing = {
                r["name"] for r in conn.execute(f"PRAGMA table_info({table})")
            }
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        conn.commit()


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for col in JSON_COLUMNS:
        if col in out and out[col]:
            try:
                out[col] = json.loads(out[col])
            except (TypeError, ValueError):
                out[col] = None
    return out


def insert_run(
    run_id: str,
    target_url: str,
    created_at: str,
    modules: list[str] | None = None,
    retry_of: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_runs "
            "(id, target_url, status, stage, progress_percent, "
            " modules_selected, modules_complete, created_at, retry_of) "
            "VALUES (?, ?, 'queued', 'Queued', 0, ?, '[]', ?, ?)",
            (
                run_id,
                target_url,
                json.dumps(modules or []),
                created_at,
                retry_of,
            ),
        )


def update_run(run_id: str, **fields: Any) -> None:
    if not fields:
        return
    encoded = {
        k: (json.dumps(v) if k in JSON_COLUMNS and v is not None else v)
        for k, v in fields.items()
    }
    assignments = ", ".join(f"{k} = ?" for k in encoded)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE audit_runs SET {assignments} WHERE id = ?",
            (*encoded.values(), run_id),
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _decode(row) if row else None


def list_runs(limit: int = 25) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, target_url, status, health_score, grade, created_at, "
            "completed_at, duration_ms, error_code FROM audit_runs "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_share_link(token: str, audit_id: str, created_at: str, expires_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO share_links (token, audit_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (token, audit_id, created_at, expires_at),
        )


def get_share_link(token: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE token = ?", (token,)
        ).fetchone()
    return dict(row) if row else None


def find_share_link_for_audit(audit_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE audit_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (audit_id,),
        ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------
# Module 1 + agent telemetry
# --------------------------------------------------------------------------
def insert_prompt(record: dict[str, Any]) -> None:
    cols = (
        "id", "original_intent", "guarded_prompt", "scope_boundary",
        "target_selector", "css_property", "css_value", "source_url",
        "confidence", "tokens_saved_estimate", "engine", "created_at",
    )
    values = []
    for c in cols:
        v = record.get(c)
        values.append(json.dumps(v) if c == "scope_boundary" and v is not None else v)
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO surgical_prompts ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            values,
        )


def list_prompts(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM surgical_prompts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("scope_boundary"):
            try:
                d["scope_boundary"] = json.loads(d["scope_boundary"])
            except ValueError:
                d["scope_boundary"] = None
        out.append(d)
    return out


def prompt_totals() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(tokens_saved_estimate), 0) AS saved "
            "FROM surgical_prompts"
        ).fetchone()
    return {"prompt_count": row["n"], "tokens_saved_estimate": row["saved"]}


def insert_agent_call(**kw: Any) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agent_calls "
            "(agent, provider, model_id, input_text, output_text, latency_ms, ok, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                kw.get("agent"), kw.get("provider"), kw.get("model_id"),
                kw.get("input_text"), kw.get("output_text"),
                kw.get("latency_ms"), 1 if kw.get("ok") else 0, kw.get("created_at"),
            ),
        )


def list_agent_calls(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT agent, provider, model_id, latency_ms, ok, created_at "
            "FROM agent_calls ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_geo_result(record: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO geo_ping_results "
            "(id, audit_id, region_code, status_code, response_time_ms, "
            " ip_blocked, ssl_valid, dns_resolved, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"], record["audit_id"], record["region_code"],
                record.get("status_code"), record.get("response_time_ms"),
                1 if record.get("ip_blocked") else 0,
                None if record.get("ssl_valid") is None else int(record["ssl_valid"]),
                None if record.get("dns_resolved") is None else int(record["dns_resolved"]),
                json.dumps(record.get("detail") or {}), record["created_at"],
            ),
        )


def previous_run_for(target_url: str, before_created_at: str, exclude_id: str):
    """The most recent completed audit of the same URL before this one."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_runs WHERE target_url = ? AND status = 'complete' "
            "AND created_at < ? AND id != ? ORDER BY created_at DESC LIMIT 1",
            (target_url, before_created_at, exclude_id),
        ).fetchone()
    return _decode(row) if row else None
