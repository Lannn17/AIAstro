# Open Registration + User Isolation + Admin Design

**Date:** 2026-03-27
**Status:** Approved (v2 — post spec review)

---

## Overview

Add open user registration so any visitor can create an account with username + password. Registered users can save charts to their own account and only see their own charts. The existing env-var admin account retains full visibility over all users' data.

---

## Requirements

- Any visitor can register with username + password (no email required)
- Registered users can save charts to their own account
- Each user only sees their own saved charts (full isolation)
- Admin (env var `AUTH_USERNAME` / `AUTH_PASSWORD`) can see all users' charts
- Guest mode (unauthenticated) continues to work as before

---

## Database Changes

### New table: `users`

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
```

### Migration: `saved_charts`

```sql
ALTER TABLE saved_charts ADD COLUMN user_id INTEGER REFERENCES users(id)
```

Applied in `create_tables()` using the existing `_has_column` / `PRAGMA table_info` pattern (same as the `is_guest` migration). Will not fail if column already exists.

**Column semantics after migration:**

| Scenario | `user_id` | `is_guest` | Visible to |
|---|---|---|---|
| Guest (unauthenticated) | NULL | 1 | Admin only (pending review) |
| Pre-migration existing chart | NULL | 0 | Admin only (orphan) |
| Registered user chart | `<user_id>` | 0 | Owner + admin |
| Approved guest chart (legacy) | NULL | 0 | Admin only |

> **Note on guest approval:** `POST /api/charts/pending/{id}/approve` sets `is_guest = 0` only. `user_id` remains NULL; the chart becomes an admin-visible "orphan". This is acceptable behaviour; adopting orphan charts is out of scope.

---

## Backend Changes

### `security.py`

**New helpers:**
- `hash_password(plain: str) -> str` — bcrypt
- `verify_password(plain: str, hashed: str) -> bool` — bcrypt

**New type:**
```python
from typing import TypedDict

class UserInfo(TypedDict):
    username: str
    user_id: int | None   # None for the env-var admin
    is_admin: bool        # True only when username == AUTH_USERNAME
```

**Updated return types:**
- `require_auth(token) -> UserInfo` — raises 401 if no/invalid token
- `get_optional_user(token) -> UserInfo | None` — returns None for guests

**JWT payload schema:**
```json
{ "sub": "<username>", "uid": <user_id_or_null>, "exp": <timestamp> }
```
- `create_access_token(data: dict)` is unchanged in signature; callers must pass `{"sub": username, "uid": user_id}`.
- `is_admin` is NOT stored in the token — it is derived at decode time: `username == AUTH_USERNAME`.

### `auth_router.py`

**New endpoint: `POST /api/auth/register`**

Request:
```json
{ "username": "...", "password": "..." }
```

Validation (server-side):
- `username` not empty, max 50 chars
- `password` length 6–128 chars
- `username != AUTH_USERNAME` (block collision with env-var admin)
- `username` not already in `users` table → 409 "用户名已存在"

On success:
- Insert into `users` with bcrypt-hashed password
- Return JWT: `create_access_token({"sub": username, "uid": new_user_id})`

**Updated: `POST /api/auth/login`**

```
1. if username == AUTH_USERNAME and password == AUTH_PASSWORD:
       return JWT with {"sub": username, "uid": None}
2. else: look up users table, bcrypt verify
       return JWT with {"sub": username, "uid": user.id}
3. else: 401
```

**Updated: `GET /api/auth/me`**

Return `{"username": user["username"]}` (extract from `UserInfo` dict instead of plain string).

### `db.py`

**New functions:**
- `db_create_user(username: str, password_hash: str) -> dict`
- `db_get_user_by_username(username: str) -> dict | None`
- `db_list_all_charts() -> list[dict]` — no `user_id` filter; admin use only

**Updated functions:**
- `db_list_charts(user_id: int) -> list[dict]` — `WHERE user_id = ?`
- `db_save_chart(data: dict)` — `data` now includes optional `user_id` key

**`create_tables()` additions:**
```python
# users table
_turso_exec / conn.execute(_CREATE_USERS)

# migration: user_id column
if not _has_column("saved_charts", "user_id"):
    _turso_exec / conn.execute("ALTER TABLE saved_charts ADD COLUMN user_id INTEGER")
```

### `charts_router.py`

All endpoints that use `require_auth` now receive `UserInfo` instead of `str`. The following callers are affected:

| Endpoint | Old usage | New usage |
|---|---|---|
| `GET /api/charts` | `_user` (ignored) | `user: UserInfo` — branch on `is_admin` |
| `POST /api/charts` | `user` (for `is_guest`) | `user: UserInfo` — write `user_id` |
| `GET /api/charts/pending` | `_user` (ignored) | check `is_admin`, else 403 |
| `POST /api/charts/pending/{id}/approve` | `_user` (ignored) | check `is_admin`, else 403 |
| `GET /api/charts/{id}` | `_user` (ignored) | ownership check |
| `PATCH /api/charts/{id}` | `_user` (ignored) | ownership check |
| `DELETE /api/charts/{id}` | `_user` (ignored) | ownership check |
| `GET /api/charts/{id}/events` | `_user` (ignored) | ownership check |
| `PUT /api/charts/{id}/events` | `_user` (ignored) | ownership check |

**Ownership check pattern** (applied to all `/{id}` endpoints):

```python
if not user["is_admin"] and row.get("user_id") != user["user_id"]:
    raise HTTPException(status_code=403, detail="无权访问此星盘")
```

> Note: `is_admin` check comes first to short-circuit before comparing `user_id`. When both `row.user_id` and `user["user_id"]` are `None` (e.g., admin accessing an orphan chart), the `is_admin` branch handles it correctly.

**`GET /api/charts` branching:**
```python
if user["is_admin"]:
    return db_list_all_charts()
return db_list_charts(user["user_id"])
```

**`POST /api/charts` — `save_chart`:**
```python
data["user_id"] = user["user_id"] if user else None
data["is_guest"] = user is None
```

### Other routers (`admin_router.py`, etc.)

These use `_user: str = Depends(require_auth)` as an auth guard (value unused). Python does not enforce type annotations at runtime, so changing `require_auth`'s return type to `UserInfo` will not break these callers — the `_user` value is discarded. No code changes needed in `admin_router.py`, `interpret_router.py`, or other routers that only use `require_auth` as a gate.

---

## Frontend Changes

### `LoginModal`

- Add toggle between **登录** and **注册** (tab or link beneath the form)
- Register form fields: username, password, confirm password
- Client-side validation: passwords match, length 6–128
- On register success: store JWT, close modal (same flow as login)
- On register error: display server message (e.g. "用户名已存在")
- Registration calls `POST /api/auth/register`

### `AuthContext`

- Add `register(username: string, password: string)` method calling `POST /api/auth/register`
- On success: store token and set user state (reuse existing login path)
- No other changes — token storage and user state are identical to login

---

## Security Notes

- Passwords stored as bcrypt hashes (never plaintext)
- Max password length 128 chars enforced server-side (bcrypt silently truncates at 72 bytes)
- Admin credentials remain outside the database (env vars only)
- Registration blocked for usernames matching `AUTH_USERNAME`
- Ownership checks on all chart detail endpoints prevent cross-user access
- JWT expiry unchanged (30 days, no refresh/revocation — pre-existing limitation)
- Username enumeration on register is accepted as a known trade-off for UX clarity

---

## Out of Scope

- Email verification or password reset
- Rate limiting on auth endpoints
- Admin promoting regular users to admin
- Public/shared charts
- Adopting orphan (pre-migration / approved guest) charts to a user
