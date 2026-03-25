from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api", tags=["Rectification"])


# ── 生命主题问卷（固定题库）────────────────────────────────────────
THEME_QUIZ = [
    {
        "id": "q1", "text": "在你的人生中，哪个领域占据最重要的位置？",
        "options": [
            {"id": "a", "text": "事业与社会成就", "houses": [10, 6]},
            {"id": "b", "text": "感情与亲密关系", "houses": [7, 5]},
            {"id": "c", "text": "家庭与安全感",   "houses": [4, 2]},
            {"id": "d", "text": "精神成长与探索", "houses": [9, 12]},
        ],
    },
    {
        "id": "q2", "text": "你的职业发展轨迹最接近哪种？",
        "options": [
            {"id": "a", "text": "在一个方向上持续深耕，稳步上升",   "houses": [10, 2]},
            {"id": "b", "text": "经历多次转变，每次都是全新开始",   "houses": [1, 9]},
            {"id": "c", "text": "服务他人或从事帮助/医疗/教育行业", "houses": [6, 12]},
            {"id": "d", "text": "创业或在艺术/创意领域发展",       "houses": [5, 1]},
        ],
    },
    {
        "id": "q3", "text": "你的感情关系模式更接近？",
        "options": [
            {"id": "a", "text": "长期稳定，重视承诺与忠诚",             "houses": [7, 4]},
            {"id": "b", "text": "感情起伏较大，曾经历重大转折或分离",   "houses": [8, 5]},
            {"id": "c", "text": "晚婚或对个人独立性有较高需求",         "houses": [1, 11]},
            {"id": "d", "text": "精神与灵魂的连接比外在条件更重要",     "houses": [9, 12]},
        ],
    },
    {
        "id": "q4", "text": "你的早年家庭环境如何？",
        "options": [
            {"id": "a", "text": "温馨稳定，家庭是重要的情感支撑",   "houses": [4, 2]},
            {"id": "b", "text": "父母权威或家规严格，成长压力较大", "houses": [10, 4]},
            {"id": "c", "text": "较早独立，或与家庭保持一定距离",   "houses": [1, 3]},
            {"id": "d", "text": "家庭环境变动频繁，需要不断适应",   "houses": [3, 9]},
        ],
    },
    {
        "id": "q5", "text": "你人生中最频繁出现的挑战类型是？",
        "options": [
            {"id": "a", "text": "自我认同与方向感的迷失", "houses": [1, 12]},
            {"id": "b", "text": "人际关系与合作的摩擦",   "houses": [7, 11]},
            {"id": "c", "text": "财务或物质安全感的起伏", "houses": [2, 8]},
            {"id": "d", "text": "职业或社会地位的压力",   "houses": [10, 6]},
        ],
    },
    {
        "id": "q6", "text": "你的「意义感」主要来源于？",
        "options": [
            {"id": "a", "text": "社会认可与外部成就",       "houses": [10, 1]},
            {"id": "b", "text": "亲密关系与家人的连接",     "houses": [4, 7]},
            {"id": "c", "text": "创造、表达与个人成长",     "houses": [5, 1]},
            {"id": "d", "text": "探索未知、精神或哲学追求", "houses": [9, 12]},
        ],
    },
]


class EventInput(BaseModel):
    year: int
    month: Optional[int] = None   # 可选；为 None 时按年份均匀采样（权重×0.4）
    day: Optional[int] = None     # 可选；为 None 时取月中第15日（权重×0.7）
    event_type: str  # marriage/divorce/career_up/career_down/bereavement/illness/relocation/accident/other
    weight: float = 1.0  # 1=一般, 2=重要, 3=非常重要
    is_turning_point: bool = False  # 用户标记为人生转折点 → 评分权重 ×2


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
    version: str = "v1.0"


@router.post("/rectify")
async def rectify(body: RectifyRequest):
    """
    出生时间校对：两阶段扫描 + AI解读。
    返回 Top3 候选时间（含上升星座）及 AI 解读文本。
    """
    try:
        from ..core.rectification import (
            rectify_birth_time, STRATEGY_DESCRIPTIONS, SCORING_STRATEGIES, DEFAULT_VERSION,
        )
        from ..rag import analyze_rectification

        version = body.version if body.version in SCORING_STRATEGIES else DEFAULT_VERSION
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
            version=version,
        )

        ai = analyze_rectification(
            natal_chart=body.natal_chart_data,
            top3=top3,
            events=events,
        )

        # 把逐候选理由合并进 top3
        for item in ai.get("candidates", []):
            idx = item.get("rank", 0) - 1
            if 0 <= idx < len(top3):
                top3[idx]["reason"] = item.get("reason", "")

        return {
            "top3": top3,
            "overall": ai.get("overall", ""),
            "version": version,
            "version_description": STRATEGY_DESCRIPTIONS.get(version, ""),
        }

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rectification error: {e}")


# ── 可用版本列表 ─────────────────────────────────────────────────

@router.get("/rectify/versions")
async def list_versions():
    """返回所有可用的推盘评分策略版本及说明"""
    from ..core.rectification import SCORING_STRATEGIES, STRATEGY_DESCRIPTIONS, DEFAULT_VERSION
    return {
        "default": DEFAULT_VERSION,
        "versions": [
            {
                "version": v,
                "description": STRATEGY_DESCRIPTIONS.get(v, ""),
                "dimensions": strat,
            }
            for v, strat in SCORING_STRATEGIES.items()
        ],
    }


# ── 上升星座性格问卷 ──────────────────────────────────────────────

class AscQuizRequest(BaseModel):
    asc_signs: List[str]  # e.g. ["Aries", "Taurus", "Gemini"]


@router.post("/rectify/asc_quiz")
async def asc_quiz(body: AscQuizRequest):
    """根据 Top3 上升星座动态生成 5 道性格鉴别题"""
    try:
        from ..rag import generate_asc_quiz
        questions = generate_asc_quiz(body.asc_signs)
        return {"questions": questions}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ASC quiz error: {e}")


# ── 生命主题问卷（静态返回）──────────────────────────────────────

@router.get("/rectify/theme_quiz")
async def theme_quiz():
    return {"questions": THEME_QUIZ}


# ── 置信度评分 ────────────────────────────────────────────────────

class ThemeAnswer(BaseModel):
    question: str
    answer: str


class ConfidenceRequest(BaseModel):
    candidate: Dict[str, Any]        # {hour, minute, asc_sign, score}
    birth_year: int
    birth_month: int
    birth_day: int
    latitude: float
    longitude: float
    tz_str: str
    theme_answers: List[ThemeAnswer]


@router.post("/rectify/confidence")
async def confidence(body: ConfidenceRequest):
    """根据生命主题问卷答案评估候选出生时间置信度"""
    try:
        from ..rag import calc_confidence
        result = calc_confidence(
            candidate=body.candidate,
            birth_year=body.birth_year,
            birth_month=body.birth_month,
            birth_day=body.birth_day,
            lat=body.latitude,
            lng=body.longitude,
            tz_str=body.tz_str,
            theme_answers=[a.model_dump() for a in body.theme_answers],
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confidence error: {e}")
