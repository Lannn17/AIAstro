"""
JWT-based authentication for AstroAPI.

Credentials are set via env vars AUTH_USERNAME and AUTH_PASSWORD.
JWT_SECRET should be a strong random string in production.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "changeme")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_optional_user(token: str = Depends(oauth2_scheme)) -> Optional[str]:
    """Returns username if token is valid, None otherwise (guest mode)."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


async def require_auth(token: str = Depends(oauth2_scheme)) -> str:
    """Raises 401 if not authenticated. Use as a FastAPI dependency."""
    if not token:
        raise HTTPException(status_code=401, detail="需要登录才能访问")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="无效的令牌")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="令牌已失效，请重新登录")
