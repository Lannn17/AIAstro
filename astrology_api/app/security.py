"""
JWT-based authentication for AstroAPI.

Credentials are set via env vars AUTH_USERNAME and AUTH_PASSWORD.
JWT_SECRET should be a strong random string in production.
"""
import hashlib
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
    # Pre-hash with SHA-256 so passwords up to 128 chars work within bcrypt's 72-byte limit
    digest = hashlib.sha256(plain.encode()).digest()
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    digest = hashlib.sha256(plain.encode()).digest()
    try:
        return bcrypt.checkpw(digest, hashed.encode())
    except ValueError:
        return False


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
