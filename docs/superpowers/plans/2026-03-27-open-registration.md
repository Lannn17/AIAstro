# Open Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add open user registration with per-user chart isolation, keeping the env-var admin as the only account with global visibility.

**Architecture:** New `users` table stores registered accounts with bcrypt-hashed passwords. `saved_charts` gains a `user_id` FK. `security.py` returns a `UserInfo` TypedDict instead of a plain string, giving every endpoint access to `user_id` and `is_admin`. All chart endpoints enforce ownership; admin bypasses isolation.

**Tech Stack:** Python/FastAPI, bcrypt (new), PyJWT (existing), SQLite/Turso (existing), React/Vite (existing)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `astrology_api/requirements.txt` | Modify | Add `bcrypt` dependency |
| `astrology_api/app/security.py` | Modify | `UserInfo` TypedDict, hash/verify helpers, updated auth deps |
| `astrology_api/app/db.py` | Modify | `users` table DDL, user CRUD, updated chart queries, migration |
| `astrology_api/app/api/auth_router.py` | Modify | `POST /api/auth/register`, updated login + `/me` |
| `astrology_api/app/api/charts_router.py` | Modify | Ownership checks, `is_admin` branching on all chart endpoints |
| `astrology_api/tests/test_auth_registration.py` | Create | Auth + registration tests |
| `frontend/src/contexts/AuthContext.jsx` | Modify | `register()` method, `isAdmin` state |
| `frontend/src/components/LoginModal.jsx` | Modify | Register tab/toggle UI |

**Not touched:** `admin_router.py`, `interpret_router.py`, and other routers — they use `require_auth` as a gate only (return value discarded), no runtime impact from TypedDict change.

---

## Task 1: Add bcrypt dependency

**Files:**
- Modify: `astrology_api/requirements.txt`

- [ ] **Step 1: Add bcrypt to requirements**

In `astrology_api/requirements.txt`, add after the `# Auth` comment:
```
bcrypt>=4.0.0
```

- [ ] **Step 2: Install it**

```bash
cd astrology_api
pip install bcrypt>=4.0.0
```

Expected: installs without error.

- [ ] **Step 3: Verify import works**

```bash
python -c "import bcrypt; print(bcrypt.__version__)"
```

Expected: prints a version number.

- [ ] **Step 4: Commit**

```bash
git add astrology_api/requirements.txt
git commit -m "chore(deps): add bcrypt for password hashing"
git push origin main && git push hf main
```

---

## Task 2: Update security.py — UserInfo + password helpers

**Files:**
- Modify: `astrology_api/app/security.py`
- Create: `astrology_api/tests/test_auth_registration.py`

- [ ] **Step 1: Write failing tests**

Create `astrology_api/tests/test_auth_registration.py`:

```python
"""Tests for open registration and UserInfo auth."""
import os
import pytest

os.environ.setdefault("AUTH_USERNAME", "admin")
os.environ.setdefault("AUTH_PASSWORD", "adminpass")

from app.security import (
    hash_password, verify_password,
    create_access_token, require_auth, get_optional_user,
    UserInfo,
)
from fastapi import HTTPException


# ── Password helpers ─────────────────────────────────────────────

def test_hash_password_returns_string():
    h = hash_password("secret123")
    assert isinstance(h, str)
    assert h != "secret123"


def test_verify_password_correct():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True


def test_verify_password_wrong():
    h = hash_password("secret123")
    assert verify_password("wrongpass", h) is False


def test_password_max_length_enforced():
    """Passwords > 128 chars should be rejected (raise ValueError)."""
    with pytest.raises(ValueError):
        hash_password("x" * 129)


# ── require_auth / get_optional_user ────────────────────────────

def _make_token(username: str, user_id):
    return create_access_token({"sub": username, "uid": user_id})


@pytest.mark.anyio
async def test_require_auth_returns_userinfo():
    token = _make_token("alice", 5)
    result = await require_auth(token)
    assert result["username"] == "alice"
    assert result["user_id"] == 5
    assert result["is_admin"] is False


@pytest.mark.anyio
async def test_require_auth_admin():
    token = _make_token("admin", None)
    result = await require_auth(token)
    assert result["username"] == "admin"
    assert result["user_id"] is None
    assert result["is_admin"] is True


@pytest.mark.anyio
async def test_require_auth_no_token_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        await require_auth(None)
    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_get_optional_user_no_token_returns_none():
    result = await get_optional_user(None)
    assert result is None


@pytest.mark.anyio
async def test_get_optional_user_valid_token():
    token = _make_token("bob", 7)
    result = await get_optional_user(token)
    assert result["username"] == "bob"
    assert result["user_id"] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd astrology_api
python -m pytest tests/test_auth_registration.py -v 2>&1 | head -40
```

Expected: ImportError or AttributeError — `hash_password`, `UserInfo` don't exist yet.

- [ ] **Step 3: Update security.py**

Replace the entire content of `astrology_api/app/security.py` with:

```python
"""
JWT-based authentication for AstroAPI.

Credentials are set via env vars AUTH_USERNAME and AUTH_PASSWORD.
JWT_SECRET should be a strong random string in production.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "changeme")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


class UserInfo(TypedDict):
    username: str
    user_id: Optional[int]   # None for the env-var admin
    is_admin: bool            # True only when username == AUTH_USERNAME


# ── Password helpers ─────────────────────────────────────────────

def hash_password(plain: str) -> str:
    if len(plain) > 128:
        raise ValueError("密码过长（最多128位）")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Token helpers ────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> UserInfo:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username = payload.get("sub")
    if not username:
        raise ValueError("no sub")
    user_id = payload.get("uid")  # None for admin, int for registered users
    return UserInfo(
        username=username,
        user_id=user_id,
        is_admin=(username == AUTH_USERNAME),
    )


# ── FastAPI dependencies ─────────────────────────────────────────

async def get_optional_user(token: str = Depends(oauth2_scheme)) -> Optional[UserInfo]:
    """Returns UserInfo if token is valid, None otherwise (guest mode)."""
    if not token:
        return None
    try:
        return _decode_token(token)
    except (jwt.PyJWTError, ValueError):
        return None


async def require_auth(token: str = Depends(oauth2_scheme)) -> UserInfo:
    """Raises 401 if not authenticated. Use as a FastAPI dependency."""
    if not token:
        raise HTTPException(status_code=401, detail="需要登录才能访问")
    try:
        return _decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="令牌已失效，请重新登录")
    except ValueError:
        raise HTTPException(status_code=401, detail="无效的令牌")
```

- [ ] **Step 4: Run tests**

```bash
cd astrology_api
python -m pytest tests/test_auth_registration.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/security.py astrology_api/tests/test_auth_registration.py
git commit -m "feat(auth): add UserInfo TypedDict, bcrypt password helpers, update require_auth"
git push origin main && git push hf main
```

---

## Task 3: Update db.py — users table + migration

**Files:**
- Modify: `astrology_api/app/db.py`

- [ ] **Step 1: Add `_CREATE_USERS` DDL constant**

At the top of `astrology_api/app/db.py`, after the existing `_CREATE_TABLE` block, add:

```python
_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

_MIGRATE_USER_ID = "ALTER TABLE saved_charts ADD COLUMN user_id INTEGER"
```

- [ ] **Step 2: Update `create_tables()`**

In `create_tables()`, add users table creation and `user_id` migration, right after the existing `is_guest` migration block:

```python
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
```

- [ ] **Step 3: Add user CRUD functions**

At the end of `astrology_api/app/db.py`, add:

```python
# ── Users ─────────────────────────────────────────────────────────

def db_create_user(username: str, password_hash: str) -> dict:
    sql = """
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
    """
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
```

- [ ] **Step 4: Add `db_list_all_charts()` and update `db_list_charts()`**

Replace the existing `db_list_charts()` function:

```python
def db_list_charts(user_id: int) -> list[dict]:
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
```

- [ ] **Step 5: Update `db_save_chart()` to include `user_id`**

In `db_save_chart()`, update the INSERT SQL and params to include `user_id`:

```python
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
```

- [ ] **Step 6: Verify app starts and migration runs**

```bash
cd astrology_api
python -c "from app.db import create_tables; create_tables(); print('OK')"
```

Expected: `[DB] Adding user_id column to saved_charts` (first run), then `OK`.

- [ ] **Step 7: Commit**

```bash
git add astrology_api/app/db.py
git commit -m "feat(db): add users table, user_id migration, user CRUD functions"
git push origin main && git push hf main
```

---

## Task 4: Update auth_router.py — register endpoint + login update

**Files:**
- Modify: `astrology_api/app/api/auth_router.py`
- Modify: `astrology_api/tests/test_auth_registration.py`

- [ ] **Step 1: Write failing tests for registration + login**

Add to `astrology_api/tests/test_auth_registration.py`:

```python
# ── Integration tests (registration + login) ────────────────────

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use in-memory SQLite for tests
os.environ["TURSO_DATABASE_URL"] = ""
os.environ["TURSO_AUTH_TOKEN"] = ""
os.environ["AUTH_USERNAME"] = "admin"
os.environ["AUTH_PASSWORD"] = "adminpass"

from fastapi.testclient import TestClient

# Patch DB path to in-memory for test isolation
import app.db as _db_module
_db_module._db_path = ":memory:"

from main import app
from app.db import create_tables
create_tables()

client = TestClient(app)


def test_register_new_user():
    res = client.post("/api/auth/register", json={"username": "alice", "password": "pass123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_register_duplicate_username():
    client.post("/api/auth/register", json={"username": "bob", "password": "pass123"})
    res = client.post("/api/auth/register", json={"username": "bob", "password": "other"})
    assert res.status_code == 409


def test_register_admin_username_blocked():
    res = client.post("/api/auth/register", json={"username": "admin", "password": "pass123"})
    assert res.status_code == 400


def test_register_password_too_short():
    res = client.post("/api/auth/register", json={"username": "carol", "password": "abc"})
    assert res.status_code == 422


def test_register_password_too_long():
    res = client.post("/api/auth/register", json={"username": "dave", "password": "x" * 129})
    assert res.status_code == 422


def test_login_registered_user():
    client.post("/api/auth/register", json={"username": "eve", "password": "eve_pass"})
    res = client.post("/api/auth/login", json={"username": "eve", "password": "eve_pass"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_admin_still_works():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    assert res.status_code == 200


def test_login_wrong_password():
    client.post("/api/auth/register", json={"username": "frank", "password": "frankpass"})
    res = client.post("/api/auth/login", json={"username": "frank", "password": "wrong"})
    assert res.status_code == 401


def test_me_returns_is_admin_false():
    r = client.post("/api/auth/register", json={"username": "grace", "password": "gracepass"})
    token = r.json()["access_token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["is_admin"] is False


def test_me_returns_is_admin_true():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = r.json()["access_token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["is_admin"] is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd astrology_api
python -m pytest tests/test_auth_registration.py -k "register or login or me" -v 2>&1 | head -40
```

Expected: 404 or ImportError for register endpoint.

- [ ] **Step 3: Rewrite auth_router.py**

Replace entire `astrology_api/app/api/auth_router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import (
    create_access_token,
    require_auth,
    verify_password,
    hash_password,
    AUTH_USERNAME,
    AUTH_PASSWORD,
    UserInfo,
)
from app.db import db_get_user_by_username, db_create_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest):
    if body.username == AUTH_USERNAME:
        raise HTTPException(status_code=400, detail="该用户名不可用")
    existing = db_get_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = db_create_user(body.username, hash_password(body.password))
    token = create_access_token({"sub": user["username"], "uid": user["id"]})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    # Admin: checked against env vars
    if body.username == AUTH_USERNAME:
        if body.password != AUTH_PASSWORD:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = create_access_token({"sub": body.username, "uid": None})
        return TokenResponse(access_token=token)
    # Registered user
    user = db_get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({"sub": user["username"], "uid": user["id"]})
    return TokenResponse(access_token=token)


@router.get("/me")
def get_me(user: UserInfo = Depends(require_auth)):
    return {"username": user["username"], "is_admin": user["is_admin"]}
```

- [ ] **Step 4: Run tests**

```bash
cd astrology_api
python -m pytest tests/test_auth_registration.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/api/auth_router.py astrology_api/tests/test_auth_registration.py
git commit -m "feat(auth): add POST /api/auth/register, update login + /me"
git push origin main && git push hf main
```

---

## Task 5: Update charts_router.py — ownership + admin isolation

**Files:**
- Modify: `astrology_api/app/api/charts_router.py`

- [ ] **Step 1: Write failing tests**

Add to `astrology_api/tests/test_auth_registration.py`:

```python
# ── Chart isolation tests ─────────────────────────────────────────

CHART_BODY = {
    "label": "Test Chart",
    "name": "Test",
    "birth_year": 1990, "birth_month": 1, "birth_day": 1,
    "birth_hour": 12, "birth_minute": 0,
    "location_name": "Tokyo",
    "latitude": 35.68, "longitude": 139.69,
    "tz_str": "Asia/Tokyo",
    "house_system": "Placidus",
    "language": "zh",
}


def _reg_token(username, password="pass123"):
    """Register and return token."""
    client.post("/api/auth/register", json={"username": username, "password": password})
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def _admin_token():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def test_user_can_save_and_list_own_chart():
    token = _reg_token("hiro")
    res = client.post("/api/charts", json=CHART_BODY, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    charts = client.get("/api/charts", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(charts) >= 1


def test_user_cannot_see_other_users_charts():
    token_a = _reg_token("userA")
    token_b = _reg_token("userB")
    res = client.post("/api/charts", json=CHART_BODY, headers={"Authorization": f"Bearer {token_a}"})
    chart_id = res.json()["id"]
    # userB tries to access userA's chart
    res2 = client.get(f"/api/charts/{chart_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res2.status_code == 403


def test_admin_can_see_all_charts():
    token_u = _reg_token("userC")
    res = client.post("/api/charts", json=CHART_BODY, headers={"Authorization": f"Bearer {token_u}"})
    chart_id = res.json()["id"]
    admin = _admin_token()
    res2 = client.get(f"/api/charts/{chart_id}", headers={"Authorization": f"Bearer {admin}"})
    assert res2.status_code == 200


def test_admin_list_includes_all_users():
    token_u = _reg_token("userD")
    client.post("/api/charts", json=CHART_BODY, headers={"Authorization": f"Bearer {token_u}"})
    admin = _admin_token()
    charts = client.get("/api/charts", headers={"Authorization": f"Bearer {admin}"}).json()
    assert len(charts) >= 1


def test_pending_requires_admin():
    token_u = _reg_token("userE")
    res = client.get("/api/charts/pending", headers={"Authorization": f"Bearer {token_u}"})
    assert res.status_code == 403
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd astrology_api
python -m pytest tests/test_auth_registration.py -k "chart" -v 2>&1 | head -30
```

Expected: failures (403s not enforced yet, list returns all charts).

- [ ] **Step 3: Rewrite charts_router.py**

Replace the entire content of `astrology_api/app/api/charts_router.py`:

```python
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.db import (
    db_list_charts, db_list_all_charts, db_save_chart, db_get_chart,
    db_delete_chart, db_list_pending_charts, db_approve_chart, db_update_chart,
    db_get_events, db_save_events,
)
from app.security import require_auth, get_optional_user, UserInfo

router = APIRouter(prefix="/api/charts", tags=["charts"])


class SaveChartRequest(BaseModel):
    label: str
    name: Optional[str] = None
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    location_name: Optional[str] = None
    latitude: float
    longitude: float
    tz_str: str
    house_system: str
    language: str
    chart_data: Optional[dict] = None
    svg_data: Optional[str] = None


class ChartSummary(BaseModel):
    id: int
    label: str
    name: Optional[str]
    birth_year: int
    birth_month: int
    birth_day: int
    location_name: Optional[str]
    created_at: Optional[datetime] = None


class ChartDetail(BaseModel):
    id: int
    label: str
    name: Optional[str]
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    location_name: Optional[str]
    latitude: float
    longitude: float
    tz_str: str
    house_system: str
    language: str
    chart_data: Optional[dict]
    svg_data: Optional[str]
    created_at: Optional[datetime] = None


def _parse(row: dict) -> dict:
    if row.get("chart_data") and isinstance(row["chart_data"], str):
        row["chart_data"] = json.loads(row["chart_data"])
    return row


def _check_ownership(row: dict, user: UserInfo):
    """Raises 403 if user does not own the chart and is not admin."""
    if not user["is_admin"] and row.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此星盘")


@router.get("", response_model=list[ChartSummary])
def list_charts(user: UserInfo = Depends(require_auth)):
    if user["is_admin"]:
        return db_list_all_charts()
    return db_list_charts(user["user_id"])


@router.post("", response_model=ChartDetail)
def save_chart(body: SaveChartRequest, user: Optional[UserInfo] = Depends(get_optional_user)):
    data = body.model_dump()
    if data.get("chart_data"):
        data["chart_data"] = json.dumps(data["chart_data"])
    data["is_guest"] = user is None
    data["user_id"] = user["user_id"] if user else None
    row = db_save_chart(data)
    return _parse(row)


@router.get("/pending", response_model=list[ChartSummary])
def list_pending(user: UserInfo = Depends(require_auth)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return db_list_pending_charts()


@router.post("/pending/{chart_id}/approve")
def approve_chart(chart_id: int, user: UserInfo = Depends(require_auth)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    db_approve_chart(chart_id)
    return {"ok": True}


@router.get("/{chart_id}", response_model=ChartDetail)
def get_chart(chart_id: int, user: UserInfo = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    _check_ownership(row, user)
    return _parse(row)


class UpdateChartRequest(BaseModel):
    label: Optional[str] = None
    name: Optional[str] = None
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    location_name: Optional[str] = None
    latitude: float
    longitude: float
    tz_str: str
    house_system: str
    language: str
    chart_data: Optional[dict] = None
    svg_data: Optional[str] = None


@router.patch("/{chart_id}", response_model=ChartDetail)
def update_chart(chart_id: int, body: UpdateChartRequest, user: UserInfo = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    _check_ownership(row, user)
    data = body.model_dump()
    if not data.get("label"):
        name = data.get("name") or ""
        if name:
            data["label"] = f"{name} · {data['birth_year']}/{data['birth_month']}/{data['birth_day']}"
        else:
            data["label"] = f"星盘 {data['birth_year']}/{data['birth_month']}/{data['birth_day']}"
    if data.get("chart_data"):
        data["chart_data"] = json.dumps(data["chart_data"])
    row = db_update_chart(chart_id, data)
    return _parse(row)


@router.delete("/{chart_id}")
def delete_chart(chart_id: int, user: UserInfo = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    _check_ownership(row, user)
    db_delete_chart(chart_id)
    return {"ok": True}


class EventItem(BaseModel):
    year: int
    month: Optional[int] = None
    day: Optional[int] = None
    event_type: str = "other"
    weight: float = 1.0
    is_turning_point: bool = False
    domainId: Optional[str] = None


@router.get("/{chart_id}/events")
def get_events(chart_id: int, user: UserInfo = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    _check_ownership(row, user)
    return {"events": db_get_events(chart_id)}


@router.put("/{chart_id}/events")
def save_events(chart_id: int, body: List[EventItem], user: UserInfo = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    _check_ownership(row, user)
    db_save_events(chart_id, [e.model_dump() for e in body])
    return {"saved": len(body)}
```

- [ ] **Step 4: Run all auth+chart tests**

```bash
cd astrology_api
python -m pytest tests/test_auth_registration.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/api/charts_router.py
git commit -m "feat(charts): enforce per-user isolation and admin override"
git push origin main && git push hf main
```

---

## Task 6: Update AuthContext — register() + isAdmin state

**Files:**
- Modify: `frontend/src/contexts/AuthContext.jsx`

- [ ] **Step 1: Update AuthContext.jsx**

Replace the entire content of `frontend/src/contexts/AuthContext.jsx`:

```jsx
import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token'))
  const [isGuest, setIsGuest] = useState(() => localStorage.getItem('guest_mode') === 'true')
  const [isAdmin, setIsAdmin] = useState(() => {
    const stored = localStorage.getItem('is_admin')
    return stored === 'true'
  })
  const [showLoginModal, setShowLoginModal] = useState(
    () => !localStorage.getItem('auth_token') && localStorage.getItem('guest_mode') !== 'true'
  )
  const [sessionKey, setSessionKey] = useState(0)

  function _applyToken(access_token, admin) {
    localStorage.setItem('auth_token', access_token)
    localStorage.setItem('is_admin', admin ? 'true' : 'false')
    localStorage.removeItem('guest_mode')
    setToken(access_token)
    setIsAdmin(!!admin)
    setIsGuest(false)
    setShowLoginModal(false)
    setSessionKey(k => k + 1)
  }

  async function login(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '登录失败')
    }
    const { access_token } = await res.json()
    // Fetch /me to get is_admin
    const meRes = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    })
    const me = meRes.ok ? await meRes.json() : {}
    _applyToken(access_token, me.is_admin ?? false)
  }

  async function register(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '注册失败')
    }
    const { access_token } = await res.json()
    // Registered users are never admin
    _applyToken(access_token, false)
  }

  function continueAsGuest() {
    localStorage.setItem('guest_mode', 'true')
    localStorage.removeItem('auth_token')
    localStorage.removeItem('is_admin')
    setIsGuest(true)
    setToken(null)
    setIsAdmin(false)
    setShowLoginModal(false)
    setSessionKey(k => k + 1)
  }

  function logout() {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('guest_mode')
    localStorage.removeItem('is_admin')
    setToken(null)
    setIsGuest(false)
    setIsAdmin(false)
    setShowLoginModal(true)
    setSessionKey(k => k + 1)
  }

  function authHeaders() {
    if (token) return { Authorization: `Bearer ${token}` }
    return {}
  }

  return (
    <AuthContext.Provider value={{
      token,
      isGuest,
      isAdmin,
      isAuthenticated: !!token,
      login,
      register,
      continueAsGuest,
      logout,
      authHeaders,
      showLoginModal,
      setShowLoginModal,
      sessionKey,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
```

- [ ] **Step 2: Verify frontend compiles**

```bash
cd frontend
npm run build 2>&1 | tail -10
```

Expected: build succeeds, no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/contexts/AuthContext.jsx
git commit -m "feat(frontend): add register() method and isAdmin state to AuthContext"
git push origin main && git push hf main
```

---

## Task 7: Update LoginModal — add register UI

**Files:**
- Modify: `frontend/src/components/LoginModal.jsx`

- [ ] **Step 1: Rewrite LoginModal.jsx with register tab**

Replace the entire content of `frontend/src/components/LoginModal.jsx`:

```jsx
import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

const inputStyle = {
  width: '100%', padding: '10px 12px',
  backgroundColor: '#1a1a3a', border: '1px solid #3a3a6a',
  borderRadius: '8px', color: '#e8e0f0', fontSize: '0.95rem',
  outline: 'none', boxSizing: 'border-box',
}

const btnPrimary = (disabled) => ({
  width: '100%', padding: '10px',
  backgroundColor: '#c9a84c', border: 'none',
  borderRadius: '8px', color: '#0a0a1a',
  fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer',
  opacity: disabled ? 0.5 : 1,
  marginTop: '4px',
})

export default function LoginModal() {
  const { showLoginModal, login, register, continueAsGuest } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'

  // Login state
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // Register state
  const [regUsername, setRegUsername] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm] = useState('')

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!showLoginModal) return null

  function switchMode(m) {
    setMode(m)
    setError('')
  }

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e) {
    e.preventDefault()
    setError('')
    if (regPassword !== regConfirm) {
      setError('两次输入的密码不一致')
      return
    }
    if (regPassword.length < 6) {
      setError('密码至少6位')
      return
    }
    if (regPassword.length > 128) {
      setError('密码最多128位')
      return
    }
    setLoading(true)
    try {
      await register(regUsername, regPassword)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      backgroundColor: 'rgba(10,10,26,0.92)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '16px',
    }}>
      <div style={{
        backgroundColor: '#0d0d22',
        border: '1px solid #2a2a5a',
        borderRadius: '12px',
        padding: '32px 28px',
        width: '100%',
        maxWidth: '360px',
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{ color: '#c9a84c', fontSize: '2rem', marginBottom: '8px' }}>✦</div>
          <div style={{ color: '#e8e0f0', fontSize: '1.2rem', fontWeight: 700, letterSpacing: '0.1em' }}>
            ASTRO
          </div>
        </div>

        {/* Tab switcher */}
        <div style={{ display: 'flex', marginBottom: '20px', borderRadius: '8px', overflow: 'hidden', border: '1px solid #2a2a5a' }}>
          {['login', 'register'].map(m => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              style={{
                flex: 1, padding: '8px',
                backgroundColor: mode === m ? '#1a1a4a' : 'transparent',
                border: 'none', color: mode === m ? '#e8e0f0' : '#5a5a8a',
                fontSize: '0.9rem', cursor: 'pointer', fontWeight: mode === m ? 600 : 400,
              }}
            >
              {m === 'login' ? '登录' : '注册'}
            </button>
          ))}
        </div>

        {/* Login form */}
        {mode === 'login' && (
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '14px' }}>
              <input
                type="text" placeholder="用户名" value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username" style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: '8px' }}>
              <input
                type="password" placeholder="密码" value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password" style={inputStyle}
              />
            </div>
            {error && (
              <div style={{ color: '#ff6b6b', fontSize: '0.82rem', marginBottom: '10px', textAlign: 'center' }}>
                {error}
              </div>
            )}
            <button type="submit" disabled={loading || !username || !password} style={btnPrimary(loading || !username || !password)}>
              {loading ? '登录中…' : '登录'}
            </button>
          </form>
        )}

        {/* Register form */}
        {mode === 'register' && (
          <form onSubmit={handleRegister}>
            <div style={{ marginBottom: '14px' }}>
              <input
                type="text" placeholder="用户名（最多50位）" value={regUsername}
                onChange={e => setRegUsername(e.target.value)}
                autoComplete="username" style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: '14px' }}>
              <input
                type="password" placeholder="密码（6-128位）" value={regPassword}
                onChange={e => setRegPassword(e.target.value)}
                autoComplete="new-password" style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: '8px' }}>
              <input
                type="password" placeholder="确认密码" value={regConfirm}
                onChange={e => setRegConfirm(e.target.value)}
                autoComplete="new-password" style={inputStyle}
              />
            </div>
            {error && (
              <div style={{ color: '#ff6b6b', fontSize: '0.82rem', marginBottom: '10px', textAlign: 'center' }}>
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading || !regUsername || !regPassword || !regConfirm}
              style={btnPrimary(loading || !regUsername || !regPassword || !regConfirm)}
            >
              {loading ? '注册中…' : '注册'}
            </button>
          </form>
        )}

        {/* Divider + Guest */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '18px 0' }}>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#2a2a5a' }} />
          <span style={{ color: '#5a5a8a', fontSize: '0.8rem' }}>或</span>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#2a2a5a' }} />
        </div>
        <button
          onClick={continueAsGuest}
          style={{
            width: '100%', padding: '10px',
            backgroundColor: 'transparent', border: '1px solid #3a3a6a',
            borderRadius: '8px', color: '#8888aa', fontSize: '0.9rem', cursor: 'pointer',
          }}
        >
          以访客身份使用
        </button>
        <div style={{ color: '#5a5a7a', fontSize: '0.75rem', textAlign: 'center', marginTop: '10px', lineHeight: 1.5 }}>
          访客可使用所有计算功能，但无法查看已保存的星盘
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Build frontend**

```bash
cd frontend
npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LoginModal.jsx
git commit -m "feat(frontend): add register tab to LoginModal"
git push origin main && git push hf main
```

---

## Task 8: Manual testing checklist

Run the backend and frontend, then verify:

```bash
# Backend
cd astrology_api && uvicorn main:app --host 127.0.0.1 --port 8001 --reload

# Frontend (separate terminal)
cd frontend && npm run dev
```

- [ ] 登录 modal 默认显示「登录」tab，点击「注册」切换到注册表单
- [ ] 注册新用户（用户名 + 密码）→ 成功登录，modal 关闭
- [ ] 注册同名用户 → 显示「用户名已存在」
- [ ] 注册密码少于6位 → 显示错误
- [ ] 用注册账号保存一张星盘 → 成功
- [ ] 登出，用另一个账号注册/登录 → 看不到上一个用户的星盘
- [ ] 用 `AUTH_USERNAME`/`AUTH_PASSWORD` 登录 → 能看到所有星盘
- [ ] 以访客身份使用 → 正常工作，无变化
- [ ] 用户确认测试全部通过后执行：

```bash
git add -A
git commit -m "test: confirm open registration manual tests pass"
git push origin main && git push hf main
```
