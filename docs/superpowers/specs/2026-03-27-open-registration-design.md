# Open Registration + User Isolation + Admin Design

**Date:** 2026-03-27
**Status:** Approved (v3 — post second spec review)

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

Applied in `create_tables()` using the existing `_has_column` / `PRAGMA table_info` pattern (same as the `is_guest` migration).

**Column semantics after migration:**

| Scenario | `user_id` | `is_guest` | Visible to |
|---|---|---|---|
| Guest (unauthenticated) | NULL | 1 | Admin only (pending review) |
| Pre-migration existing chart | NULL | 0 | Admin only (orphan) |
| Registered user chart | `<user_id>` | 0 | Owner + admin |
| Approved guest chart (legacy) | NULL | 0 | Admin only (orphan) |
| Admin-saved chart | NULL | 0 | Admin only (orphan) |

> **Note on guest approval:** `POST /api/charts/pending/{id}/approve` sets `is_guest = 0` only. `user_id` stays NULL; the chart becomes an admin-visible orphan. Adopting orphan charts is out of scope.
>
> **Note on admin saving charts:** The admin (`user_id = NULL`) can save charts; they are stored with `user_id = NULL, is_guest = 0` — visible to admin only. This is correct and intentional.

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
- `create_access_token(data: dict)` unchanged in signature; callers pass `{"sub": username, "uid": user_id}`.
- `is_admin` is **not** stored in the token — derived at decode time: `username == AUTH_USERNAME`.

### `auth_router.py`

**New endpoint: `POST /api/auth/register`**

Request:
```json
{ "username": "...", "password": "..." }
```

Validation (server-side):
- `username` not empty, max 50 chars
- `password` length 6–128 chars (enforced; bcrypt truncates at 72 bytes)
- `username != AUTH_USERNAME` → 400 "该用户名不可用"
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

Returns `{"username": user["username"], "is_admin": user["is_admin"]}`.

- User state is derived from the JWT payload client-side on page load (no rehydration call needed). `/me` is kept as a token-validity check; it now also exposes `is_admin` for the frontend to conditionally show admin UI.
- **Code change:** `user: UserInfo = Depends(require_auth)` — update from current `user: str = Depends(require_auth)` and change return to `{"username": user["username"], "is_admin": user["is_admin"]}`.

### `db.py`

**New functions:**
- `db_create_user(username: str, password_hash: str) -> dict`
- `db_get_user_by_username(username: str) -> dict | None`
- `db_list_all_charts() -> list[dict]` — `WHERE is_guest = 0` (excludes pending guest charts; includes orphans and all user charts); admin use only

**Updated functions:**
- `db_list_charts(user_id: int) -> list[dict]` — `WHERE user_id = ? AND is_guest = 0`
- `db_save_chart(data: dict)` — `data` now includes optional `user_id` key

**`create_tables()` additions:**
```python
# users table (before saved_charts migration)
_turso_exec / conn.execute(_CREATE_USERS)

# migration: user_id column
if not _has_column("saved_charts", "user_id"):
    _turso_exec / conn.execute("ALTER TABLE saved_charts ADD COLUMN user_id INTEGER")
```

### `charts_router.py`

All `require_auth` callers in this router now receive `UserInfo`. Callers that previously used `_user` (discarded) must be updated to named `user: UserInfo` where an `is_admin` check is needed. Full breakdown:

| Endpoint | Parameter change | Logic change |
|---|---|---|
| `GET /api/charts` | `_user` → `user: UserInfo` | branch on `is_admin` |
| `POST /api/charts` | `user: Optional[str]` → `user: Optional[UserInfo]` | write `user_id` |
| `GET /api/charts/pending` | `_user` → `user: UserInfo` | check `is_admin`, else 403 |
| `POST /api/charts/pending/{id}/approve` | `_user` → `user: UserInfo` | check `is_admin`, else 403 |
| `GET /api/charts/{id}` | `_user` → `user: UserInfo` | ownership check |
| `PATCH /api/charts/{id}` | `_user` → `user: UserInfo` | ownership check |
| `DELETE /api/charts/{id}` | `_user` → `user: UserInfo` | ownership check |
| `GET /api/charts/{id}/events` | `_user` → `user: UserInfo` | ownership check |
| `PUT /api/charts/{id}/events` | `_user` → `user: UserInfo` | ownership check |

**Ownership check pattern** (applied to all `/{id}` endpoints):

```python
if not user["is_admin"] and row.get("user_id") != user["user_id"]:
    raise HTTPException(status_code=403, detail="无权访问此星盘")
```

> `is_admin` is checked first. If both `row["user_id"]` and `user["user_id"]` are `None` (orphan chart accessed by admin), the `is_admin` branch handles it correctly without a false positive.

**`GET /api/charts` branching:**
```python
if user["is_admin"]:
    return db_list_all_charts()
return db_list_charts(user["user_id"])
```

**`POST /api/charts`:**
```python
data["user_id"] = user["user_id"] if user else None
data["is_guest"] = user is None
```

### Other routers (`admin_router.py`, `interpret_router.py`, etc.)

These use `_user = Depends(require_auth)` as an auth gate — value is discarded. Python does not enforce type annotations at runtime, so changing `require_auth`'s return type to `UserInfo` will not break these callers. **No code changes needed.**

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
- On success: store token and set user state (same as login path)
- User state is derived from JWT payload (client-side decode) on page load; no additional `/me` rehydration call needed
- `is_admin` can be stored in user state for conditional admin UI (read from `/me` response on login or decoded from JWT)

---

## Security Notes

- Passwords stored as bcrypt hashes (never plaintext)
- Max password length 128 chars enforced server-side (bcrypt silently truncates at 72 bytes)
- Admin credentials remain outside the database (env vars only)
- Registration blocked for usernames matching `AUTH_USERNAME`
- Ownership checks on all chart detail endpoints prevent cross-user access
- `is_admin` derived from env var comparison, never stored in DB or JWT
- JWT expiry unchanged (30 days, no refresh/revocation — pre-existing limitation)
- Username enumeration on register accepted as a known trade-off for UX clarity
- Rate limiting on auth endpoints is out of scope (acknowledged risk)

---

## Out of Scope

- Email verification or password reset
- Rate limiting on auth endpoints
- Admin promoting regular users to admin
- Public/shared charts
- Adopting orphan charts to a registered user account
