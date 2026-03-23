from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api", tags=["Rectification"])


class EventInput(BaseModel):
    year: int
    month: int
    day: int
    event_type: str  # marriage/divorce/career_up/career_down/bereavement/illness/relocation/accident/other
    weight: float = 1.0  # 1=一般, 2=重要, 3=非常重要


class RectifyRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    latitude: float
    longitude: float
    tz_str: str
    house_system: str = "Placidus"
    events: List[EventInput]
    approx_hour: Optional[int] = None
    approx_minute: Optional[int] = None
    time_range_hours: Optional[float] = None
    natal_chart_data: Dict[str, Any] = {}


@router.post("/rectify")
async def rectify(body: RectifyRequest):
    """
    出生时间校对：两阶段扫描 + AI解读。
    返回 Top3 候选时间（含上升星座）及 AI 解读文本。
    """
    try:
        from ..core.rectification import rectify_birth_time
        from ..rag import analyze_rectification

        events = [e.model_dump() for e in body.events]

        top3 = rectify_birth_time(
            birth_year=body.birth_year,
            birth_month=body.birth_month,
            birth_day=body.birth_day,
            lat=body.latitude,
            lng=body.longitude,
            tz_str=body.tz_str,
            events=events,
            approx_hour=body.approx_hour,
            approx_minute=body.approx_minute,
            time_range_hours=body.time_range_hours,
        )

        ai = analyze_rectification(
            natal_chart=body.natal_chart_data,
            top3=top3,
            events=events,
        )

        return {"top3": top3, "analysis": ai.get("answer", "")}

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rectification error: {e}")
