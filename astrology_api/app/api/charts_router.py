import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db import get_db, SavedChart

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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


@router.get("", response_model=list[ChartSummary])
def list_charts(db: Session = Depends(get_db)):
    rows = db.query(SavedChart).order_by(SavedChart.created_at.desc()).all()
    return rows


@router.post("", response_model=ChartDetail)
def save_chart(body: SaveChartRequest, db: Session = Depends(get_db)):
    row = SavedChart(
        label=body.label,
        name=body.name,
        birth_year=body.birth_year,
        birth_month=body.birth_month,
        birth_day=body.birth_day,
        birth_hour=body.birth_hour,
        birth_minute=body.birth_minute,
        location_name=body.location_name,
        latitude=body.latitude,
        longitude=body.longitude,
        tz_str=body.tz_str,
        house_system=body.house_system,
        language=body.language,
        chart_data=json.dumps(body.chart_data) if body.chart_data else None,
        svg_data=body.svg_data,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if row.chart_data:
        row.chart_data = json.loads(row.chart_data)
    return row


@router.get("/{chart_id}", response_model=ChartDetail)
def get_chart(chart_id: int, db: Session = Depends(get_db)):
    row = db.query(SavedChart).filter(SavedChart.id == chart_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    if row.chart_data:
        row.chart_data = json.loads(row.chart_data)
    return row


@router.delete("/{chart_id}")
def delete_chart(chart_id: int, db: Session = Depends(get_db)):
    row = db.query(SavedChart).filter(SavedChart.id == chart_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
