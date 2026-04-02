import json
import os
import sqlite3
import requests
from datetime import datetime, timezone

_turso_url = os.getenv("TURSO_DATABASE_URL", "")
_turso_token = os.getenv("TURSO_AUTH_TOKEN", "")
USE_TURSO = bool(_turso_url and _turso_token)

if USE_TURSO:
    _api_url = _turso_url.replace("libsql://", "https://") + "/v2/pipeline"
    _auth_headers = {
        "Authorization": f"Bearer {_turso_token}",
        "Content-Type": "application/json",
    }
else:
    _db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "charts.db"))

_CREATE_TRANSIT_CACHE = """
CREATE TABLE IF NOT EXISTS transit_analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id INTEGER NOT NULL,
    transit_key TEXT NOT NULL,
    analysis TEXT NOT NULL,
    tone TEXT NOT NULL,
    themes TEXT NOT NULL,
    end_date TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(chart_id, transit_key)
)
"""

_CREATE_TRANSIT_OVERALL = """
CREATE TABLE IF NOT EXISTS transit_overall_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id INTEGER NOT NULL,
    transit_set_hash TEXT NOT NULL,
    overall TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(chart_id, transit_set_hash)
)
"""


_CREATE_PLANET_CACHE = """
CREATE TABLE IF NOT EXISTS planet_analysis_cache (
    chart_id INTEGER PRIMARY KEY,
    chart_hash TEXT NOT NULL,
    analyses TEXT NOT NULL,
    model_used TEXT DEFAULT '',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_CREATE_SYNASTRY_CACHE = """
CREATE TABLE IF NOT EXISTS synastry_cache (
    aspects_hash TEXT PRIMARY KEY,
    answer       TEXT NOT NULL,
    sources      TEXT NOT NULL,
    created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_CREATE_QUERY_ANALYTICS = """
CREATE TABLE IF NOT EXISTS query_analytics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash    TEXT    NOT NULL,
    label         TEXT    NOT NULL,
    max_rag_score REAL    NOT NULL,
    any_cited     INTEGER NOT NULL,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_CREATE_LIFE_EVENTS = """
CREATE TABLE IF NOT EXISTS life_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chart_id INTEGER NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER,
  day INTEGER,
  event_type TEXT NOT NULL DEFAULT 'other',
  weight REAL DEFAULT 1.0,
  is_turning_point INTEGER DEFAULT 0,
  domain_id TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (chart_id) REFERENCES saved_charts(id) ON DELETE CASCADE
)
"""

_CREATE_SR_CACHE = """
CREATE TABLE IF NOT EXISTS solar_return_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id      INTEGER NOT NULL,
    return_year   INTEGER NOT NULL,
    location_hash TEXT    NOT NULL,
    result_json   TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(chart_id, return_year, location_hash)
)
"""

_CREATE_PROMPT_VERSIONS = """
CREATE TABLE IF NOT EXISTS prompt_versions (
    id TEXT PRIMARY KEY,
    caller TEXT NOT NULL,
    version_tag TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    system_instruction TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    deployed_at TEXT,
    UNIQUE(caller, version_tag)
)
"""

_CREATE_PROMPT_LOGS = """
CREATE TABLE IF NOT EXISTS prompt_logs (
    id TEXT PRIMARY KEY,
    version_id TEXT,
    source TEXT NOT NULL,
    input_data TEXT,
    rag_query TEXT,
    rag_chunks TEXT,
    response_text TEXT,
    latency_ms INTEGER,
    model_used TEXT,
    temperature REAL,
    finish_reason TEXT,
    prompt_tokens_est INTEGER,
    response_tokens_est INTEGER,
    user_id TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_PROMPT_EVALUATIONS = """
CREATE TABLE IF NOT EXISTS prompt_evaluations (
    id TEXT PRIMARY KEY,
    log_id TEXT NOT NULL,
    version_id TEXT,
    compared_to_log_id TEXT,
    evaluator_type TEXT NOT NULL,
    score_overall REAL,
    dimensions TEXT,
    notes TEXT,
    suggestions TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_CONFIRMED_BIRTH_TIMES = """
CREATE TABLE IF NOT EXISTS confirmed_birth_times (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_year   INTEGER NOT NULL,
    birth_month  INTEGER NOT NULL,
    birth_day    INTEGER NOT NULL,
    birth_hour   INTEGER NOT NULL,
    birth_minute INTEGER NOT NULL,
    latitude     REAL    NOT NULL,
    longitude    REAL    NOT NULL,
    tz_str       TEXT    NOT NULL,
    location_name TEXT,
    created_at   TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_CREATE_USER_FEEDBACK = """
CREATE TABLE IF NOT EXISTS user_feedback (
    id TEXT PRIMARY KEY,
    caller TEXT,
    content TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS saved_charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    name TEXT,
    birth_year INTEGER NOT NULL,
    birth_month INTEGER NOT NULL,
    birth_day INTEGER NOT NULL,
    birth_hour INTEGER NOT NULL,
    birth_minute INTEGER NOT NULL,
    location_name TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    tz_str TEXT NOT NULL,
    house_system TEXT NOT NULL,
    language TEXT NOT NULL,
    chart_data TEXT,
    svg_data TEXT,
    is_guest INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

# Migration: add is_guest to tables that predate this column
_MIGRATE_IS_GUEST = "ALTER TABLE saved_charts ADD COLUMN is_guest INTEGER DEFAULT 0"

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_MIGRATE_USER_ID = "ALTER TABLE saved_charts ADD COLUMN user_id INTEGER"
_MIGRATE_PLANET_CACHE_MODEL = "ALTER TABLE planet_analysis_cache ADD COLUMN model_used TEXT DEFAULT ''"


# ── Turso HTTP helpers ───────────────────────────────────────────

def _turso_args(values: list) -> list:
    result = []
    for v in values:
        if v is None:
            result.append({"type": "null"})
        elif isinstance(v, bool):
            result.append({"type": "integer", "value": "1" if v else "0"})
        elif isinstance(v, int):
            result.append({"type": "integer", "value": str(v)})
        elif isinstance(v, float):
            result.append({"type": "float", "value": v})
        else:
            result.append({"type": "text", "value": str(v)})
    return result


def _turso_exec(sql: str, params: list = None) -> dict:
    stmt = {"sql": sql}
    if params:
        stmt["args"] = _turso_args(params)
    payload = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
    r = requests.post(_api_url, headers=_auth_headers, json=payload, timeout=15)
    r.raise_for_status()
    result = r.json()["results"][0]
    if result["type"] != "ok":
        raise RuntimeError(f"Turso error: {result}")
    return result["response"]["result"]


def _to_dicts(result: dict) -> list[dict]:
    cols = [c["name"] for c in result["cols"]]
    rows = []
    for row in result["rows"]:
        d = {}
        for col, cell in zip(cols, row):
            t, v = cell["type"], cell.get("value")
            if t == "null":
                v = None
            elif t == "integer":
                v = int(v)
            elif t == "float":
                v = float(v)
            d[col] = v
        rows.append(d)
    return rows

def _turso_query(sql: str, params: list = None) -> list[dict]:
    """SELECT helper: execute sql and return rows as list[dict]."""
    return _to_dicts(_turso_exec(sql, params or []))

# ── SQLite helpers ───────────────────────────────────────────────

def _sqlite_fetchall(sql: str, params: list = None) -> list[dict]:
    with sqlite3.connect(_db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params or []).fetchall()
        return [dict(r) for r in rows]


def _sqlite_fetchone(sql: str, params: list = None) -> dict | None:
    with sqlite3.connect(_db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, params or []).fetchone()
        return dict(row) if row else None


def _sqlite_write(sql: str, params: list = None) -> int:
    with sqlite3.connect(_db_path) as conn:
        cur = conn.execute(sql, params or [])
        return cur.lastrowid or cur.rowcount


# ── Public API ───────────────────────────────────────────────────

def _has_column(table: str, column: str) -> bool:
    """Check whether a column exists in a table."""
    sql = f"PRAGMA table_info({table})"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql))
        return any(r.get("name") == column for r in rows)
    with sqlite3.connect(_db_path) as conn:
        rows = conn.execute(sql).fetchall()
        return any(r[1] == column for r in rows)


def create_tables():
    for ddl in [_CREATE_TABLE, _CREATE_TRANSIT_CACHE, _CREATE_TRANSIT_OVERALL,
                _CREATE_PLANET_CACHE, _CREATE_SYNASTRY_CACHE, _CREATE_QUERY_ANALYTICS,
                _CREATE_LIFE_EVENTS, _CREATE_SR_CACHE,
                _CREATE_PROMPT_VERSIONS, _CREATE_PROMPT_LOGS,
                _CREATE_PROMPT_EVALUATIONS, _CREATE_USER_FEEDBACK,
                _CREATE_CONFIRMED_BIRTH_TIMES]:
        if USE_TURSO:
            _turso_exec(ddl)
        else:
            with sqlite3.connect(_db_path) as conn:
                conn.execute(ddl)
    # Migrate: add is_guest column only if it doesn't already exist
    if not _has_column("saved_charts", "is_guest"):
        print("[DB] Adding is_guest column to saved_charts")
        if USE_TURSO:
            _turso_exec(_MIGRATE_IS_GUEST)
        else:
            with sqlite3.connect(_db_path) as conn:
                conn.execute(_MIGRATE_IS_GUEST)

    # Create users table
    if USE_TURSO:
        _turso_exec(_CREATE_USERS)
    else:
        with sqlite3.connect(_db_path) as conn:
            conn.execute(_CREATE_USERS)

    # Migrate: add user_id column only if it doesn't already exist
    if not _has_column("saved_charts", "user_id"):
        print("[DB] Adding user_id column to saved_charts")
        if USE_TURSO:
            _turso_exec(_MIGRATE_USER_ID)
        else:
            with sqlite3.connect(_db_path) as conn:
                conn.execute(_MIGRATE_USER_ID)
        # Migrate: add model_used column to planet_analysis_cache
    if not _has_column("planet_analysis_cache", "model_used"):
        print("[DB] Adding model_used column to planet_analysis_cache")
        if USE_TURSO:
            _turso_exec(_MIGRATE_PLANET_CACHE_MODEL)
        else:
            with sqlite3.connect(_db_path) as conn:
                conn.execute(_MIGRATE_PLANET_CACHE_MODEL)
        # Warm the deployed-version cache
    
        # Seed v1 from prompt_registry
    try:
        from .db_seed import seed_prompt_versions
        seed_prompt_versions()
    except Exception as e:
        print(f"[WARN] Seed failed: {e}")
    # Re-warm cache after seeding
    try:
        from .prompt_version_cache import warm_cache
        warm_cache(db_get_all_deployed_versions())
    except Exception as e:
        print(f"[WARN] Re-warm after seed failed: {e}")
        
    try:
        from .prompt_version_cache import warm_cache
        warm_cache(db_get_all_deployed_versions())
        print("[DB] prompt_version_cache warmed")
    except Exception as e:
        print(f"[WARN] Failed to warm prompt_version_cache: {e}")

def db_list_charts() -> list[dict]:
    sql = (
        "SELECT id, label, name, birth_year, birth_month, birth_day, "
        "location_name, created_at FROM saved_charts WHERE is_guest = 0 ORDER BY created_at DESC"
    )
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql))
    return _sqlite_fetchall(sql)


def db_list_user_charts(user_id: int) -> list[dict]:
    """Returns non-guest charts belonging to a specific registered user."""
    sql = (
        "SELECT id, label, name, birth_year, birth_month, birth_day, "
        "location_name, created_at FROM saved_charts "
        "WHERE user_id = ? AND is_guest = 0 ORDER BY created_at DESC"
    )
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql, [user_id]))
    return _sqlite_fetchall(sql, [user_id])


def db_list_all_charts() -> list[dict]:
    """Admin use only — returns all non-guest charts regardless of user_id."""
    sql = (
        "SELECT id, label, name, birth_year, birth_month, birth_day, "
        "location_name, created_at FROM saved_charts "
        "WHERE is_guest = 0 ORDER BY created_at DESC"
    )
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql))
    return _sqlite_fetchall(sql)


def db_list_pending_charts() -> list[dict]:
    sql = (
        "SELECT id, label, name, birth_year, birth_month, birth_day, "
        "location_name, created_at FROM saved_charts WHERE is_guest = 1 ORDER BY created_at DESC"
    )
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql))
    return _sqlite_fetchall(sql)


def db_approve_chart(chart_id: int):
    sql = "UPDATE saved_charts SET is_guest = 0 WHERE id = ?"
    if USE_TURSO:
        _turso_exec(sql, [chart_id])
    else:
        _sqlite_write(sql, [chart_id])


def db_save_chart(data: dict) -> dict:
    sql = """
        INSERT INTO saved_charts
            (label, name, birth_year, birth_month, birth_day, birth_hour, birth_minute,
             location_name, latitude, longitude, tz_str, house_system, language,
             chart_data, svg_data, is_guest, user_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    from datetime import datetime, timezone
    params = [
        data["label"], data.get("name"),
        data["birth_year"], data["birth_month"], data["birth_day"],
        data["birth_hour"], data["birth_minute"],
        data.get("location_name"),
        data["latitude"], data["longitude"],
        data["tz_str"], data["house_system"], data["language"],
        data.get("chart_data"), data.get("svg_data"),
        1 if data.get("is_guest") else 0,
        data.get("user_id"),  # None for guests and admin
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    if USE_TURSO:
        result = _turso_exec(sql, params)
        new_id = int(result["last_insert_rowid"])
    else:
        new_id = _sqlite_write(sql, params)
    return db_get_chart(new_id)


def db_get_chart(chart_id: int) -> dict | None:
    sql = "SELECT * FROM saved_charts WHERE id = ?"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id]))
        return rows[0] if rows else None
    return _sqlite_fetchone(sql, [chart_id])


def db_update_chart(chart_id: int, data: dict) -> dict:
    sql = """
        UPDATE saved_charts SET
            label=?, name=?, birth_year=?, birth_month=?, birth_day=?,
            birth_hour=?, birth_minute=?, location_name=?, latitude=?,
            longitude=?, tz_str=?, house_system=?, language=?,
            chart_data=?, svg_data=?
        WHERE id=?
    """
    params = [
        data["label"], data.get("name"),
        data["birth_year"], data["birth_month"], data["birth_day"],
        data["birth_hour"], data["birth_minute"],
        data.get("location_name"),
        data["latitude"], data["longitude"],
        data["tz_str"], data["house_system"], data["language"],
        data.get("chart_data"), data.get("svg_data"),
        chart_id,
    ]
    if USE_TURSO:
        _turso_exec(sql, params)
    else:
        _sqlite_write(sql, params)
    return db_get_chart(chart_id)


def db_delete_chart(chart_id: int):
    sql = "DELETE FROM saved_charts WHERE id = ?"
    if USE_TURSO:
        _turso_exec(sql, [chart_id])
    else:
        _sqlite_write(sql, [chart_id])


# ── Transit analysis cache ────────────────────────────────────────

def db_get_transit_cache(chart_id: int, transit_key: str, today: str) -> dict | None:
    """Returns {analysis, tone, themes} if cached and end_date >= today."""
    sql = (
        "SELECT analysis, tone, themes FROM transit_analysis_cache "
        "WHERE chart_id=? AND transit_key=? AND end_date >= ?"
    )
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id, transit_key, today]))
        return rows[0] if rows else None
    return _sqlite_fetchone(sql, [chart_id, transit_key, today])


def db_save_transit_cache(
    chart_id: int, transit_key: str,
    analysis: str, tone: str, themes_json: str, end_date: str,
):
    sql = """
        INSERT OR REPLACE INTO transit_analysis_cache
            (chart_id, transit_key, analysis, tone, themes, end_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = [chart_id, transit_key, analysis, tone, themes_json, end_date]
    if USE_TURSO:
        _turso_exec(sql, params)
    else:
        _sqlite_write(sql, params)


def db_delete_expired_transit_cache(chart_id: int, today: str):
    """Delete per-transit cache rows whose end_date has passed."""
    sql = "DELETE FROM transit_analysis_cache WHERE chart_id=? AND end_date < ?"
    if USE_TURSO:
        _turso_exec(sql, [chart_id, today])
    else:
        _sqlite_write(sql, [chart_id, today])


def db_get_overall_cache(chart_id: int, transit_set_hash: str) -> str | None:
    sql = (
        "SELECT overall FROM transit_overall_cache "
        "WHERE chart_id=? AND transit_set_hash=?"
    )
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id, transit_set_hash]))
        return rows[0]["overall"] if rows else None
    row = _sqlite_fetchone(sql, [chart_id, transit_set_hash])
    return row["overall"] if row else None


def db_save_overall_cache(chart_id: int, transit_set_hash: str, overall: str):
    sql = """
        INSERT OR REPLACE INTO transit_overall_cache
            (chart_id, transit_set_hash, overall)
        VALUES (?, ?, ?)
    """
    if USE_TURSO:
        _turso_exec(sql, [chart_id, transit_set_hash, overall])
    else:
        _sqlite_write(sql, [chart_id, transit_set_hash, overall])


# ── Planet analysis cache ─────────────────────────────────────────

def db_get_planet_cache(chart_id: int, chart_hash: str) -> dict | None:
    """Returns cached analyses JSON and model_used if chart_hash matches, else None."""
    sql = "SELECT analyses, model_used FROM planet_analysis_cache WHERE chart_id = ? AND chart_hash = ?"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id, chart_hash]))
        return rows[0] if rows else None
    row = _sqlite_fetchone(sql, [chart_id, chart_hash])
    return row if row else None


def db_save_planet_cache(chart_id: int, chart_hash: str, analyses_json: str, model_used: str = ""):
    sql = """
        INSERT OR REPLACE INTO planet_analysis_cache
            (chart_id, chart_hash, analyses, model_used)
        VALUES (?, ?, ?, ?)
    """
    if USE_TURSO:
        _turso_exec(sql, [chart_id, chart_hash, analyses_json, model_used])
    else:
        _sqlite_write(sql, [chart_id, chart_hash, analyses_json, model_used])


# ── Query analytics ───────────────────────────────────────────────

def db_get_analytics_summary() -> list[dict]:
    """按 label 聚合：count、avg_score、cite_rate。"""
    sql = """
        SELECT
            label,
            COUNT(*)                     AS count,
            ROUND(AVG(max_rag_score), 3) AS avg_score,
            ROUND(AVG(any_cited), 3)     AS cite_rate
        FROM query_analytics
        GROUP BY label
        ORDER BY count DESC
    """
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql))
    return _sqlite_fetchall(sql)


def db_get_analytics_records(limit: int = 200) -> list[dict]:
    """最近 N 条原始记录（不含原始 query 文本）。"""
    sql = """
        SELECT id, label, max_rag_score, any_cited, created_at
        FROM query_analytics
        ORDER BY created_at DESC
        LIMIT ?
    """
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql, [limit]))
    return _sqlite_fetchall(sql, [limit])


def db_log_query_analytics(query_hash: str, label: str,
                           max_rag_score: float, any_cited: bool):
    sql = """
        INSERT INTO query_analytics (query_hash, label, max_rag_score, any_cited)
        VALUES (?, ?, ?, ?)
    """
    params = [query_hash, label, round(max_rag_score, 4), 1 if any_cited else 0]
    try:
        if USE_TURSO:
            _turso_exec(sql, params)
        else:
            _sqlite_write(sql, params)
    except Exception as e:
        print(f"[Analytics] log failed (non-fatal): {e}", flush=True)


# ── Synastry cache ─────────────────────────────────────────────────

def db_get_synastry_cache(aspects_hash: str) -> dict | None:
    sql = "SELECT answer, sources FROM synastry_cache WHERE aspects_hash = ?"
    try:
        if USE_TURSO:
            rows = _to_dicts(_turso_exec(sql, [aspects_hash]))
        else:
            with sqlite3.connect(_db_path) as conn:
                rows = [{"answer": r[0], "sources": r[1]}
                        for r in conn.execute(sql, [aspects_hash]).fetchall()]
        if rows:
            row = rows[0]
            return {"answer": row["answer"], "sources": json.loads(row["sources"])}
    except Exception as e:
        print(f"[DB] synastry cache get failed: {e}", flush=True)
    return None


def db_save_synastry_cache(aspects_hash: str, answer: str, sources: list):
    sql = """
        INSERT OR REPLACE INTO synastry_cache (aspects_hash, answer, sources)
        VALUES (?, ?, ?)
    """
    params = [aspects_hash, answer, json.dumps(sources, ensure_ascii=False)]
    try:
        if USE_TURSO:
            _turso_exec(sql, params)
        else:
            _sqlite_write(sql, params)
    except Exception as e:
        print(f"[DB] synastry cache save failed: {e}", flush=True)


# ── Solar Return cache ─────────────────────────────────────────────

def db_get_sr_cache(chart_id: int, return_year: int, location_hash: str) -> dict | None:
    """Return cached solar return result (json.loads'd), or None on miss."""
    sql = "SELECT result_json FROM solar_return_cache WHERE chart_id=? AND return_year=? AND location_hash=?"
    try:
        rows = _to_dicts(_turso_exec(sql, [chart_id, return_year, location_hash]))
        if not rows:
            return None
        return json.loads(rows[0]["result_json"])
    except Exception as e:
        print(f"[DB] sr cache get failed: {e}", flush=True)
    return None


def db_save_sr_cache(chart_id: int, return_year: int, location_hash: str, result_json: str) -> None:
    """INSERT OR REPLACE solar return cache row."""
    sql = """
    INSERT OR REPLACE INTO solar_return_cache (chart_id, return_year, location_hash, result_json)
    VALUES (?, ?, ?, ?)
    """
    try:
        _turso_exec(sql, [chart_id, return_year, location_hash, result_json])
    except Exception as e:
        print(f"[DB] sr cache save failed (non-fatal): {e}", flush=True)


# ── Life events ────────────────────────────────────────────────────

def db_get_events(chart_id: int) -> list[dict]:
    """Return all life events for a chart."""
    sql = "SELECT * FROM life_events WHERE chart_id = ? ORDER BY year, month, day"
    cols = ["id", "chart_id", "year", "month", "day", "event_type", "weight", "is_turning_point", "domain_id", "created_at"]
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id]))
        return rows
    return _sqlite_fetchall(sql, [chart_id])


def db_save_events(chart_id: int, events: list[dict]) -> None:
    """Replace all events for a chart (bulk upsert)."""
    delete_sql = "DELETE FROM life_events WHERE chart_id = ?"
    insert_sql = (
        "INSERT INTO life_events (chart_id, year, month, day, event_type, weight, is_turning_point, domain_id) "
        "VALUES (?,?,?,?,?,?,?,?)"
    )
    if USE_TURSO:
        _turso_exec(delete_sql, [chart_id])
        for ev in events:
            _turso_exec(insert_sql, [
                chart_id,
                ev.get("year"),
                ev.get("month") or None,
                ev.get("day") or None,
                ev.get("event_type", "other"),
                ev.get("weight", 1.0),
                1 if ev.get("is_turning_point") else 0,
                ev.get("domainId") or ev.get("domain_id") or None,
            ])
    else:
        _sqlite_write(delete_sql, [chart_id])
        for ev in events:
            _sqlite_write(insert_sql, [
                chart_id,
                ev.get("year"),
                ev.get("month") or None,
                ev.get("day") or None,
                ev.get("event_type", "other"),
                ev.get("weight", 1.0),
                1 if ev.get("is_turning_point") else 0,
                ev.get("domainId") or ev.get("domain_id") or None,
            ])


# ── Users ─────────────────────────────────────────────────────────

def db_create_user(username: str, password_hash: str) -> dict:
    sql = "INSERT INTO users (username, password_hash) VALUES (?, ?)"
    if USE_TURSO:
        result = _turso_exec(sql, [username, password_hash])
        new_id = int(result["last_insert_rowid"])
    else:
        new_id = _sqlite_write(sql, [username, password_hash])
    return db_get_user_by_id(new_id)


def db_get_user_by_id(user_id: int) -> dict | None:
    sql = "SELECT * FROM users WHERE id = ?"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [user_id]))
        return rows[0] if rows else None
    return _sqlite_fetchone(sql, [user_id])


def db_get_user_by_username(username: str) -> dict | None:
    sql = "SELECT * FROM users WHERE username = ?"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [username]))
        return rows[0] if rows else None
    return _sqlite_fetchone(sql, [username])

# ── Prompt versions helpers ────────────────────────────────────────

def db_insert_prompt_version(
    id_: str, caller: str, version_tag: str,
    prompt_text: str, system_instruction: str | None,
    status: str = "draft", deployed_at: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = """INSERT INTO prompt_versions
             (id, caller, version_tag, prompt_text, system_instruction,
              status, created_at, deployed_at)
             VALUES (?,?,?,?,?,?,?,?)"""
    args = [id_, caller, version_tag, prompt_text, system_instruction,
            status, now, deployed_at]
    if USE_TURSO:
        _turso_exec(sql, args)


def db_get_deployed_version(caller: str) -> dict | None:
    sql = "SELECT * FROM prompt_versions WHERE caller=? AND status='deployed' LIMIT 1"
    rows = _turso_query(sql, [caller])
    return rows[0] if rows else None


def db_list_prompt_versions(caller: str | None = None) -> list[dict]:
    if caller:
        sql = "SELECT * FROM prompt_versions WHERE caller=? ORDER BY created_at DESC"
        return _turso_query(sql, [caller])
    return _turso_query("SELECT * FROM prompt_versions ORDER BY created_at DESC", [])


def db_get_prompt_version(id_: str) -> dict | None:
    rows = _turso_query("SELECT * FROM prompt_versions WHERE id=?", [id_])
    return rows[0] if rows else None


def db_update_prompt_version(id_: str, **fields) -> None:
    allowed = {"status", "version_tag", "deployed_at", "prompt_text", "system_instruction"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    sql = f"UPDATE prompt_versions SET {set_clause} WHERE id=?"
    if USE_TURSO:
        _turso_exec(sql, list(updates.values()) + [id_])


def db_get_all_deployed_versions() -> list[dict]:
    return _turso_query(
        "SELECT id, caller FROM prompt_versions WHERE status='deployed'", []
    )

# ── Prompt logs helpers ────────────────────────────────────────────

def db_insert_prompt_log(
    id_: str, version_id: str | None, source: str,
    input_data: str | None, rag_query: str, rag_chunks: str,
    response_text: str, latency_ms: int, model_used: str,
    temperature: float, finish_reason: str,
    prompt_tokens_est: int, response_tokens_est: int,
    user_id: str | None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = """INSERT INTO prompt_logs
             (id, version_id, source, input_data, rag_query, rag_chunks,
              response_text, latency_ms, model_used, temperature, finish_reason,
              prompt_tokens_est, response_tokens_est, user_id, created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    args = [id_, version_id, source, input_data, rag_query, rag_chunks,
            response_text, latency_ms, model_used, temperature, finish_reason,
            prompt_tokens_est, response_tokens_est, user_id, now]
    if USE_TURSO:
        _turso_exec(sql, args)


def db_query_prompt_logs(
    version_id: str | None = None,
    caller: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions, args = [], []
    if version_id:
        conditions.append("pl.version_id=?"); args.append(version_id)
    if caller:
        conditions.append("pv.caller=?"); args.append(caller)
    if source:
        conditions.append("pl.source=?"); args.append(source)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""SELECT pl.* FROM prompt_logs pl
              LEFT JOIN prompt_versions pv ON pl.version_id=pv.id
              {where} ORDER BY pl.created_at DESC LIMIT ?"""
    args.append(limit)
    return _turso_query(sql, args)


def db_get_recent_log_for_version(version_id: str, source: str | None = None) -> dict | None:
    if source:
        rows = _turso_query(
            "SELECT * FROM prompt_logs WHERE version_id=? AND source=? ORDER BY created_at DESC LIMIT 1",
            [version_id, source]
        )
    else:
        rows = _turso_query(
            "SELECT * FROM prompt_logs WHERE version_id=? ORDER BY created_at DESC LIMIT 1",
            [version_id]
        )
    return rows[0] if rows else None


# ── Prompt evaluations helpers ─────────────────────────────────────

def db_insert_prompt_evaluation(
    id_: str, log_id: str, version_id: str | None,
    evaluator_type: str, score_overall: float | None,
    dimensions: str | None, notes: str | None,
    suggestions: str | None, compared_to_log_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = """INSERT INTO prompt_evaluations
             (id, log_id, version_id, compared_to_log_id, evaluator_type,
              score_overall, dimensions, notes, suggestions, created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?)"""
    args = [id_, log_id, version_id, compared_to_log_id, evaluator_type,
            score_overall, dimensions, notes, suggestions, now]
    if USE_TURSO:
        _turso_exec(sql, args)


def db_get_evaluations_for_log(log_id: str) -> list[dict]:
    return _turso_query(
        "SELECT * FROM prompt_evaluations WHERE log_id=? ORDER BY created_at DESC",
        [log_id]
    )


def db_get_evaluations_for_version(version_id: str) -> list[dict]:
    return _turso_query(
        "SELECT * FROM prompt_evaluations WHERE version_id=? ORDER BY created_at DESC",
        [version_id]
    )


# ── User feedback helpers ──────────────────────────────────────────

# ── Confirmed birth times helpers ──────────────────────────────────────────

def db_insert_confirmed_birth_time(
    birth_year: int, birth_month: int, birth_day: int,
    birth_hour: int, birth_minute: int,
    latitude: float, longitude: float,
    tz_str: str, location_name: str | None
) -> None:
    sql = """INSERT INTO confirmed_birth_times
             (birth_year, birth_month, birth_day, birth_hour, birth_minute,
              latitude, longitude, tz_str, location_name)
             VALUES (?,?,?,?,?,?,?,?,?)"""
    args = [birth_year, birth_month, birth_day, birth_hour, birth_minute,
            latitude, longitude, tz_str, location_name]
    if USE_TURSO:
        _turso_exec(sql, args)
    else:
        _sqlite_write(sql, args)


def db_insert_user_feedback(
    id_: str, caller: str | None, content: str, user_id: str | None
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = "INSERT INTO user_feedback (id, caller, content, user_id, created_at) VALUES (?,?,?,?,?)"
    if USE_TURSO:
        _turso_exec(sql, [id_, caller, content, user_id, now])