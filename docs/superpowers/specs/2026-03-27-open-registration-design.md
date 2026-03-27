# Open Registration + User Isolation + Admin Design

**Date:** 2026-03-27
**Status:** Approved

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

- Guest charts: `user_id = NULL`, `is_guest = 1`
- Registered user charts: `user_id = <user_id>`, `is_guest = 0`
- Existing charts (pre-migration): `user_id = NULL`, `is_guest = 0` — visible only to admin

---

## Backend Changes

### `security.py`

- Add `hash_password(plain: str) -> str` using `bcrypt`
- Add `verify_password(plain: str, hashed: str) -> bool`
- Change `UserInfo = TypedDict` with fields: `username`, `user_id` (int | None), `is_admin` (bool)
- `get_optional_user` returns `UserInfo | None`
- `require_auth` returns `UserInfo`
- `is_admin` = `username == AUTH_USERNAME`

### `auth_router.py`

**New endpoint: `POST /api/auth/register`**
- Request: `{ username, password }`
- Validates: username not empty, password >= 6 chars, username not already taken
- Creates user in `users` table with bcrypt-hashed password
- Returns JWT token (same format as login) — auto-login on register

**Updated: `POST /api/auth/login`**
1. Check if `username == AUTH_USERNAME` and `password == AUTH_PASSWORD` (env var admin)
2. Else look up `users` table, verify bcrypt hash
3. JWT `sub` carries `username`; `user_id` also embedded in token payload

### `db.py`

New functions:
- `db_create_user(username, password_hash) -> dict`
- `db_get_user_by_username(username) -> dict | None`
- `db_list_all_charts()` — returns all charts regardless of `user_id` (admin use)

Updated functions:
- `db_list_charts(user_id: int)` — filters by `user_id`
- `db_save_chart(data)` — `data` includes `user_id`
- Migration in `create_tables()`: add `user_id` column if missing; add `users` table

### `charts_router.py`

- `GET /api/charts`: admin → `db_list_all_charts()`; user → `db_list_charts(user_id)`
- `POST /api/charts`: write `user_id` from token (None for guests)
- `GET /api/charts/{id}`: verify `row.user_id == current_user.user_id` OR `is_admin`; else 403
- `PATCH /api/charts/{id}`: same ownership check
- `DELETE /api/charts/{id}`: same ownership check
- `GET /api/charts/pending`: admin only (401 if not admin)
- `POST /api/charts/pending/{id}/approve`: admin only

---

## Frontend Changes

### `LoginModal`

- Add toggle between **登录** and **注册** tabs
- Register form fields: username, password, confirm password
- Client-side validation: passwords match, min length 6
- On success: store JWT (same as login), close modal
- On error: show server error message (e.g. "用户名已存在")

### `AuthContext`

- Add `register(username, password)` method calling `POST /api/auth/register`
- No other changes needed — token storage and user state are reused

---

## Security Notes

- Passwords stored as bcrypt hashes (never plaintext)
- Admin credentials remain outside the database (env vars only)
- Ownership checks on all chart endpoints prevent cross-user access
- JWT expiry unchanged (30 days)

---

## Out of Scope

- Email verification
- Password reset
- Admin promoting regular users to admin
- Public/shared charts
