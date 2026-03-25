import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db import (
    db_list_charts, db_save_chart, db_get_chart, db_delete_chart,
    db_list_pending_charts, db_approve_chart, db_update_chart,
)
from app.security import require_auth, get_optional_user

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


@router.get("", response_model=list[ChartSummary])
def list_charts(_user: str = Depends(require_auth)):
    return db_list_charts()


@router.post("", response_model=ChartDetail)
def save_chart(body: SaveChartRequest, user: Optional[str] = Depends(get_optional_user)):
    data = body.model_dump()
    if data.get("chart_data"):
        data["chart_data"] = json.dumps(data["chart_data"])
    # Guests (no valid token) → marked for review; owners → direct save
    data["is_guest"] = user is None
    row = db_save_chart(data)
    return _parse(row)


@router.get("/pending", response_model=list[ChartSummary])
def list_pending(_user: str = Depends(require_auth)):
    return db_list_pending_charts()


@router.post("/pending/{chart_id}/approve")
def approve_chart(chart_id: int, _user: str = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    db_approve_chart(chart_id)
    return {"ok": True}


@router.get("/{chart_id}", response_model=ChartDetail)
def get_chart(chart_id: int, _user: str = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
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
def update_chart(chart_id: int, body: UpdateChartRequest, _user: str = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
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
def delete_chart(chart_id: int, _user: str = Depends(require_auth)):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    db_delete_chart(chart_id)
    return {"ok": True}
