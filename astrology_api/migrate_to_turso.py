"""
One-time migration: local charts.db → Turso cloud.
Run from astrology_api/ with venv active:
    python migrate_to_turso.py
"""
import os, sqlite3, json, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

TURSO_URL   = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
DB_PATH     = Path(__file__).parent / "charts.db"

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit("TURSO_DATABASE_URL / TURSO_AUTH_TOKEN not set in .env")

api_url = TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline"
headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}


def turso_exec(sql, params=None):
    def encode(v):
        if v is None:            return {"type": "null"}
        if isinstance(v, bool):  return {"type": "integer", "value": "1" if v else "0"}
        if isinstance(v, int):   return {"type": "integer", "value": str(v)}
        if isinstance(v, float): return {"type": "float",   "value": float(v)}
        return {"type": "text", "value": str(v)}

    stmt = {"sql": sql}
    if params:
        stmt["args"] = [encode(p) for p in params]
    payload = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
    r = requests.post(api_url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    result = r.json()["results"][0]
    if result["type"] != "ok":
        raise RuntimeError(f"Turso error: {result}")
    return result["response"]["result"]


def migrate_table(conn, table, insert_sql, row_fn, skip_check_sql):
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    print(f"\n[{table}] {len(rows)} rows to migrate")
    ok = skip = err = 0
    for row in rows:
        d = dict(row)
        # skip if already exists
        exists_rows = turso_exec(skip_check_sql[0], skip_check_sql[1](d))
        cols = [c["name"] for c in exists_rows["cols"]]
        if exists_rows["rows"]:
            skip += 1
            continue
        try:
            turso_exec(insert_sql, row_fn(d))
            ok += 1
        except Exception as e:
            print(f"  ERROR row {d.get('id','?')}: {e}")
            err += 1
    print(f"  inserted={ok}  skipped={skip}  errors={err}")


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# ── saved_charts ─────────────────────────────────────────────────
migrate_table(
    conn,
    "saved_charts",
    """INSERT INTO saved_charts
        (label,name,birth_year,birth_month,birth_day,birth_hour,birth_minute,
         location_name,latitude,longitude,tz_str,house_system,language,
         chart_data,svg_data,created_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    lambda d: [
        d["label"], d.get("name"),
        d["birth_year"], d["birth_month"], d["birth_day"],
        d["birth_hour"], d["birth_minute"],
        d.get("location_name"), float(d["latitude"]), float(d["longitude"]),
        d["tz_str"], d["house_system"], d["language"],
        d.get("chart_data"), d.get("svg_data"), d["created_at"],
    ],
    (
        "SELECT id FROM saved_charts WHERE label=? AND created_at=?",
        lambda d: [d["label"], d["created_at"]],
    ),
)

# ── transit_analysis_cache ───────────────────────────────────────
migrate_table(
    conn,
    "transit_analysis_cache",
    """INSERT OR IGNORE INTO transit_analysis_cache
        (chart_id,transit_key,analysis,tone,themes,end_date,created_at)
       VALUES (?,?,?,?,?,?,?)""",
    lambda d: [
        d["chart_id"], d["transit_key"], d["analysis"],
        d["tone"], d["themes"], d["end_date"], d.get("created_at",""),
    ],
    (
        "SELECT id FROM transit_analysis_cache WHERE chart_id=? AND transit_key=?",
        lambda d: [d["chart_id"], d["transit_key"]],
    ),
)

# ── transit_overall_cache ────────────────────────────────────────
migrate_table(
    conn,
    "transit_overall_cache",
    """INSERT OR IGNORE INTO transit_overall_cache
        (chart_id,transit_set_hash,overall,created_at)
       VALUES (?,?,?,?)""",
    lambda d: [
        d["chart_id"], d["transit_set_hash"], d["overall"], d.get("created_at",""),
    ],
    (
        "SELECT id FROM transit_overall_cache WHERE chart_id=? AND transit_set_hash=?",
        lambda d: [d["chart_id"], d["transit_set_hash"]],
    ),
)

print("\nDone.")
