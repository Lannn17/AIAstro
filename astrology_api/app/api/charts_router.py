import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.db import (
    db_list_user_charts, db_list_all_charts, db_save_chart, db_get_chart,
    db_delete_chart, db_list_pending_charts, db_approve_chart, db_update_chart,
    db_get_events, db_save_events,
)
from app.security import require_auth, get_optional_user, UserInfo

router = APIRouter(prefix="/api/charts", tags=["charts"])


class ChartBaseRequest(BaseModel):
    """Shared fields for chart create/update."""
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


class SaveChartRequest(ChartBaseRequest):
    label: str
    name: Optional[str] = None


class UpdateChartRequest(ChartBaseRequest):
    label: Optional[str] = None
    name: Optional[str] = None


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
    return db_list_user_charts(user["user_id"])


@router.post("", response_model=ChartDetail)
def save_chart(body: SaveChartRequest, user: Optional[UserInfo] = Depends(get_optional_user)):
    data = body.model_dump()
    if data.get("chart_data"):
        data["chart_data"] = json.dumps(data["chart_data"])
    if user is None:
        data["is_guest"] = True
    else:
        data["is_guest"] = False
    data["user_id"] = user["user_id"] if user else None
    row = db_save_chart(data)
    return _parse(row)

# ⚠️ Fixed paths must be defined BEFORE /{chart_id} to avoid route conflict
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
