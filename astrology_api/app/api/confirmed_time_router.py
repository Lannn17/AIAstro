"""
confirmed_time_router.py — POST /api/confirmed-birth-time

收录用户主动确认精确到分钟的出生时间，用于校正算法验证数据集。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.db import db_insert_confirmed_birth_time

router = APIRouter()


class ConfirmedBirthTimeIn(BaseModel):
    birth_year:   int
    birth_month:  int
    birth_day:    int
    birth_hour:   int
    birth_minute: int
    latitude:     float
    longitude:    float
    tz_str:       str
    location_name: str | None = None


@router.post("/api/confirmed-birth-time")
async def submit_confirmed_birth_time(payload: ConfirmedBirthTimeIn):
    db_insert_confirmed_birth_time(
        birth_year=payload.birth_year,
        birth_month=payload.birth_month,
        birth_day=payload.birth_day,
        birth_hour=payload.birth_hour,
        birth_minute=payload.birth_minute,
        latitude=payload.latitude,
        longitude=payload.longitude,
        tz_str=payload.tz_str,
        location_name=payload.location_name,
    )
    return {"ok": True}
