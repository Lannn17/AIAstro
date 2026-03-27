"""Tests for open registration, UserInfo auth, and chart isolation."""
import os
import tempfile
import pytest

# Set env vars BEFORE any app imports
os.environ["AUTH_USERNAME"] = "admin"
os.environ["AUTH_PASSWORD"] = "adminpass"
os.environ["TURSO_DATABASE_URL"] = ""
os.environ["TURSO_AUTH_TOKEN"] = ""

# Patch DB to a named temp file so all sqlite3.connect() calls share the same DB.
# NamedTemporaryFile with delete=False gives a real file path; we pass suffix=".db"
# so SQLite accepts it. The file persists for the test session (acceptable for CI).
import app.db as _db_module
_TEST_DB = tempfile.NamedTemporaryFile(delete=False, suffix=".db").name
_db_module._db_path = _TEST_DB
_db_module.USE_TURSO = False

from app.db import create_tables
create_tables()

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ── Password helper tests (sync, no HTTP) ───────────────────────

def test_hash_password_returns_string():
    from app.security import hash_password
    h = hash_password("secret123")
    assert isinstance(h, str)
    assert h != "secret123"


def test_verify_password_correct():
    from app.security import hash_password, verify_password
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True


def test_verify_password_wrong():
    from app.security import hash_password, verify_password
    h = hash_password("secret123")
    assert verify_password("wrongpass", h) is False


def test_password_max_length_enforced():
    from app.security import hash_password
    with pytest.raises(ValueError):
        hash_password("x" * 129)


# ── require_auth / get_optional_user via TestClient ─────────────

def _get_token(username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_require_auth_returns_userinfo_for_registered_user():
    client.post("/api/auth/register", json={"username": "tester_sec", "password": "pass1234"})
    token = _get_token("tester_sec", "pass1234")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "tester_sec"
    assert data["is_admin"] is False


def test_require_auth_admin_is_admin_true():
    token = _get_token("admin", "adminpass")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["is_admin"] is True


def test_require_auth_no_token_returns_401():
    res = client.get("/api/auth/me")
    assert res.status_code == 401


# ── DB user CRUD tests ────────────────────────────────────────────

def test_db_create_and_get_user():
    from app.db import db_create_user, db_get_user_by_username
    user = db_create_user("dbtest_alice", "hashed_pw_here")
    assert user["username"] == "dbtest_alice"
    assert user["id"] is not None
    fetched = db_get_user_by_username("dbtest_alice")
    assert fetched["id"] == user["id"]


def test_db_get_user_not_found():
    from app.db import db_get_user_by_username
    result = db_get_user_by_username("nonexistent_xyz")
    assert result is None


def test_db_list_user_charts_isolation():
    from app.db import db_save_chart, db_list_user_charts, db_list_all_charts
    chart_data = {
        "label": "IsolationTest", "name": "T", "birth_year": 1990, "birth_month": 1, "birth_day": 1,
        "birth_hour": 12, "birth_minute": 0, "location_name": "Tokyo",
        "latitude": 35.68, "longitude": 139.69, "tz_str": "Asia/Tokyo",
        "house_system": "Placidus", "language": "zh", "is_guest": False,
    }
    chart_data["user_id"] = 9001
    db_save_chart(chart_data)
    charts_9001 = db_list_user_charts(9001)
    charts_9002 = db_list_user_charts(9002)
    all_charts = db_list_all_charts()
    assert any(c.get("label") == "IsolationTest" for c in charts_9001)
    assert not any(c.get("label") == "IsolationTest" for c in charts_9002)
    assert any(c.get("label") == "IsolationTest" for c in all_charts)
