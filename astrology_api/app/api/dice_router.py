"""
占星骰子 API
POST /api/dice/roll     — 掷三骰 + 主解读
POST /api/dice/reroll   — 再掷（追问模式 / 补充能量模式）
"""
import asyncio
import hashlib
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.security import require_auth, UserInfo
from app.db import db_log_query_analytics, db_save_dice_roll

router = APIRouter(prefix="/api/dice", tags=["Dice"])


# ── Schemas ────────────────────────────────────────────────────────

class DiceRollRequest(BaseModel):
    question: str
    category: str = "其他"
    chart_id: Optional[int] = None   # 可选：结合指定本命盘解读


class DiceRerollRequest(BaseModel):
    original_planet: str
    original_sign: str
    original_house: str
    original_question: str
    category: str = "其他"
    mode: str  # "followup" | "supplement"
    followup_question: Optional[str] = None  # mode=followup 时必填


# ── 每日限制检查 ────────────────────────────────────────────────────

def _check_daily_limit(username: str) -> None:
    """查 dice_rolls 表：同一用户今日已有记录则拒绝。"""
    from app.db import USE_TURSO, _turso_query, _sqlite_fetchall
    today = date_type.today().isoformat()
    sql = """
        SELECT COUNT(*) as cnt FROM dice_rolls
        WHERE username = ?
          AND created_at >= ?
    """
    params = [username, f"{today}T00:00:00"]
    rows = _turso_query(sql, params) if USE_TURSO else _sqlite_fetchall(sql, params)
    cnt = rows[0]["cnt"] if rows else 0
    if cnt >= 1:
        raise HTTPException(
            status_code=429,
            detail="今日已完成一次占星骰子占卜。占星能量不宜滥用，明日再来。"
        )


# ── 端点 ───────────────────────────────────────────────────────────

@router.post("/roll")
async def dice_roll(body: DiceRollRequest, user: UserInfo = Depends(require_auth)):
    """掷三颗骰子并生成主解读"""
    from app.rag.dice import roll_dice, interpret_dice

    username = user.get("username", "")
    _check_daily_limit(username)  # 先检查，查 dice_rolls 表，同步

    try:
        dice = roll_dice()

        # 可选：提取本命盘上下文
        natal_context = ""
        if body.chart_id:
            from app.db import db_get_chart
            import json as _json
            chart_row = db_get_chart(body.chart_id)
            if chart_row:
                raw = chart_row.get("chart_data") or "{}"
                chart_data = _json.loads(raw) if isinstance(raw, str) else raw
                from app.rag.dice import extract_natal_context
                natal_context = extract_natal_context(
                    chart_data, dice["planet"], dice["sign"], dice["house"]
                )

        result = interpret_dice(
            planet=dice["planet"],
            sign=dice["sign"],
            house=dice["house"],
            question=body.question,
            category=body.category,
            natal_context=natal_context,
        )

        # 同步写入 dice_rolls（确保下次检查能查到）
        interp = result.get("interpretation", "")
        db_save_dice_roll(
            username=username,
            question=body.question,
            category=body.category,
            planet=dice["planet"],
            sign=dice["sign"],
            house=dice["house"],
            chart_id=body.chart_id,
            interp_summary=interp[:200],
        )

        # analytics 仍然异步（非关键）
        prefix = hashlib.sha256(f"dice:{username}:{date_type.today().isoformat()}".encode()).hexdigest()[:16]
        asyncio.create_task(_log_dice_analytics(body.question, result, prefix))
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[DICE ERROR]\n{traceback.format_exc()}", flush=True)
        raise HTTPException(status_code=500, detail=f"占星骰子解读失败: {e}")


@router.post("/reroll")
async def dice_reroll(body: DiceRerollRequest, user: UserInfo = Depends(require_auth)):
    """再掷：追问模式（2骰）或补充能量模式（1骰）"""
    from app.rag.dice import (
        roll_two_dice, roll_one_planet,
        interpret_followup, interpret_supplement,
    )

    try:
        if body.mode == "followup":
            if not body.followup_question:
                raise HTTPException(status_code=422, detail="追问模式需要提供 followup_question")
            new_dice = roll_two_dice()
            result = interpret_followup(
                original_planet=body.original_planet,
                original_sign=body.original_sign,
                original_house=body.original_house,
                original_question=body.original_question,
                new_planet=new_dice["planet"],
                new_house=new_dice["house"],
                followup_question=body.followup_question,
                category=body.category,
            )
        elif body.mode == "supplement":
            new_dice = roll_one_planet()
            result = interpret_supplement(
                original_planet=body.original_planet,
                original_sign=body.original_sign,
                original_house=body.original_house,
                original_question=body.original_question,
                supplement_planet=new_dice["planet"],
            )
        else:
            raise HTTPException(status_code=422, detail="mode 必须为 followup 或 supplement")

        asyncio.create_task(_log_reroll_analytics(body.original_question, result, body.mode))
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[DICE REROLL ERROR]\n{traceback.format_exc()}", flush=True)
        raise HTTPException(status_code=500, detail=f"再掷解读失败: {e}")


# ── Analytics ──────────────────────────────────────────────────────

async def _log_dice_analytics(query: str, result: dict, prefix: str):
    try:
        from app.rag import classify_query
        query_hash = prefix + hashlib.sha256(query.encode()).hexdigest()[16:]
        label = "astro_dice"
        sources = result.get("sources", [])
        max_score = max((s.get("score", 0.0) for s in sources), default=0.0)
        any_cited = any(s.get("cited", False) for s in sources)
        db_log_query_analytics(query_hash, label, max_score, any_cited)
        print(f"[Dice Analytics] score={max_score:.3f} cited={any_cited}", flush=True)
    except Exception as e:
        print(f"[Dice Analytics] log failed (non-fatal): {e}", flush=True)


async def _log_reroll_analytics(query: str, result: dict, mode: str):
    try:
        query_hash = hashlib.sha256(f"dice_reroll:{mode}:{query}".encode()).hexdigest()
        label = f"astro_dice_{mode}"
        sources = result.get("sources", [])
        max_score = max((s.get("score", 0.0) for s in sources), default=0.0)
        any_cited = any(s.get("cited", False) for s in sources)
        db_log_query_analytics(query_hash, label, max_score, any_cited)
    except Exception as e:
        print(f"[Dice Reroll Analytics] log failed (non-fatal): {e}", flush=True)
