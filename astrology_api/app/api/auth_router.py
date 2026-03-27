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
    password: str = Field(..., min_length=6, max_length=16)


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
