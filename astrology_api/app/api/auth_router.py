from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.security import (
    create_access_token,
    require_auth,
    AUTH_USERNAME,
    AUTH_PASSWORD,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if body.username != AUTH_USERNAME or body.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({"sub": body.username})
    return TokenResponse(access_token=token)


@router.get("/me")
def get_me(user: str = Depends(require_auth)):
    return {"username": user}
