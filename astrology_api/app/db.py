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
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""


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

def create_tables():
    if USE_TURSO:
        _turso_exec(_CREATE_TABLE)
    else:
        with sqlite3.connect(_db_path) as conn:
            conn.execute(_CREATE_TABLE)


def db_list_charts() -> list[dict]:
    sql = (
        "SELECT id, label, name, birth_year, birth_month, birth_day, "
        "location_name, created_at FROM saved_charts ORDER BY created_at DESC"
    )
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql))
    return _sqlite_fetchall(sql)


def db_save_chart(data: dict) -> dict:
    sql = """
        INSERT INTO saved_charts
            (label, name, birth_year, birth_month, birth_day, birth_hour, birth_minute,
             location_name, latitude, longitude, tz_str, house_system, language,
             chart_data, svg_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
