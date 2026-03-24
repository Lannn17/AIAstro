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
    analyses TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_CREATE_PLANET_CACHE = """
CREATE TABLE IF NOT EXISTS planet_analysis_cache (
    chart_id INTEGER PRIMARY KEY,
    chart_hash TEXT NOT NULL,
    analyses TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
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
            result.append({"type": "float", "value": str(v)})
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
    for ddl in [_CREATE_TABLE, _CREATE_TRANSIT_CACHE, _CREATE_TRANSIT_OVERALL, _CREATE_PLANET_CACHE]:
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


def db_list_charts() -> list[dict]:
    sql = (
        "SELECT id, label, name, birth_year, birth_month, birth_day, "
        "location_name, created_at FROM saved_charts WHERE is_guest = 0 ORDER BY created_at DESC"
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
             chart_data, svg_data, is_guest, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

def db_get_planet_cache(chart_id: int, chart_hash: str) -> str | None:
    """Returns cached analyses JSON if chart_hash matches, else None."""
    sql = "SELECT analyses FROM planet_analysis_cache WHERE chart_id = ? AND chart_hash = ?"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id, chart_hash]))
        return rows[0]["analyses"] if rows else None
    row = _sqlite_fetchone(sql, [chart_id, chart_hash])
    return row["analyses"] if row else None


def db_save_planet_cache(chart_id: int, chart_hash: str, analyses_json: str):
    sql = """
        INSERT OR REPLACE INTO planet_analysis_cache
            (chart_id, chart_hash, analyses)
        VALUES (?, ?, ?)
    """
    if USE_TURSO:
        _turso_exec(sql, [chart_id, chart_hash, analyses_json])
    else:
        _sqlite_write(sql, [chart_id, chart_hash, analyses_json])
