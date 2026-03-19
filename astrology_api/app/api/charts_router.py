import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db import db_list_charts, db_save_chart, db_get_chart, db_delete_chart

router = APIRouter(prefix="/api/v1/charts", tags=["charts"])


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
    created_at: datetime


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
    created_at: datetime


def _parse(row: dict) -> dict:
    if row.get("chart_data") and isinstance(row["chart_data"], str):
        row["chart_data"] = json.loads(row["chart_data"])
    return row


@router.get("", response_model=list[ChartSummary])
def list_charts():
    return db_list_charts()


@router.post("", response_model=ChartDetail)
def save_chart(body: SaveChartRequest):
    data = body.model_dump()
    if data.get("chart_data"):
        data["chart_data"] = json.dumps(data["chart_data"])
    row = db_save_chart(data)
    return _parse(row)


@router.get("/{chart_id}", response_model=ChartDetail)
def get_chart(chart_id: int):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    return _parse(row)


@router.delete("/{chart_id}")
def delete_chart(chart_id: int):
    row = db_get_chart(chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    db_delete_chart(chart_id)
    return {"ok": True}
