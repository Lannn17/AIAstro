from datetime import date as date_type
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List
from ..interpretations.text_search import simple_text_search

# 注意：计算缓存已移除（Kerykeion 本地计算足够快，每次实时计算）
# AI 缓存在 rag.py 的 _TRANSIT_FULL_AI_CACHE 中管理

router = APIRouter(
    prefix="/api",
    tags=["Interpretations"],
)


@router.get("/interpret", response_model=List[Dict[str, Any]])
async def interpret_text(query: str = Query(..., description="Text to search in interpretations")):
    results = simple_text_search(query)
    return results


class RagRequest(BaseModel):
    query: str
    k: int = 5


class HistoryMessage(BaseModel):
    role: str   # "user" or "assistant"
    text: str


class ChatRequest(BaseModel):
    query: str
    chart_data: Dict[str, Any]
    k: int = 5
    history: List[HistoryMessage] = []
    summary: str = ""  # compressed summary of earlier turns


class SummarizeRequest(BaseModel):
    messages: List[HistoryMessage]
    chart_name: str = ""


@router.post("/interpret/rag")
async def interpret_rag(body: RagRequest):
    """
    RAG 解读：向量检索相关书籍片段 → Gemini 生成中文解读。

    返回:
    - answer: 生成的解读文本
    - sources: 检索到的原文片段（含来源书名和相似度分数）
    - index_used: 使用的索引（demo_index 或 faiss_index）
    """
    try:
        from ..rag import rag_query
        result = rag_query(body.query, k=body.k)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG error: {e}")


@router.post("/interpret/chat")
async def interpret_chat(body: ChatRequest):
    """
    星盘对话。mode="rag": RAG测试版（片段主导）；mode="interpret": AI解读版（AI主导，RAG补充）。
    """
    try:
        from ..rag import chat_with_chart
        history = [{"role": m.role, "text": m.text} for m in body.history]
        result = chat_with_chart(body.query, body.chart_data, k=body.k,
                                 history=history, summary=body.summary)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[CHAT ERROR]\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}: {e}")


class TransitInterpretRequest(BaseModel):
    natal_chart: Dict[str, Any]
    transit_aspects: List[Dict[str, Any]]
    transit_planets: Dict[str, Any]
    transit_date: str


@router.post("/interpret/transit")
async def interpret_transit(body: TransitInterpretRequest):
    """行运解读：AI分析行运相位对本命盘的影响。"""
    try:
        from ..rag import analyze_transits
        result = analyze_transits(
            natal_chart=body.natal_chart,
            transit_aspects=body.transit_aspects,
            transit_planets=body.transit_planets,
            transit_date=body.transit_date,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transit interpretation error: {e}")


class TransitsFullRequest(BaseModel):
    chart_id: int = 0
    natal_info: Dict[str, Any]        # year/month/day/hour/minute/latitude/longitude/tz_str/house_system
    natal_chart_data: Dict[str, Any]  # 完整 NatalChartResponse，供 AI 上下文
    query_date: str                   # "YYYY-MM-DD"
    language: str = "zh"
    force_refresh: bool = False       # True 时跳过 AI 缓存，重新生成解读


@router.post("/interpret/transits_full")
async def interpret_transits_full(body: TransitsFullRequest):
    """
    活跃行运完整分析：
    1. 计算当天所有容许度内的行运相位及时间窗口（有缓存）
    2. 单次 Gemini 调用生成逐相位解读 + 整体报告（有缓存）
    返回：{active_transits, overall}，其中每条 transit 包含 analysis 字段。
    """
    try:
        from ..core.transit_windows import get_active_transits
        from ..rag import analyze_active_transits_full

        # ── Step 1: 计算行运窗口（缓存永久有效，行星历表是确定性的）──
        # ── Step 1: 实时计算行运窗口（无缓存，确保始终反映最新代码）──
        q_date = date_type.fromisoformat(body.query_date)
        active = get_active_transits(
            natal_data=body.natal_info,
            query_date=q_date,
            language=body.language,
        )

        # ── Step 2: AI 分析（按 chart_id+date 缓存，force_refresh 可绕过）──
        ai_result = analyze_active_transits_full(
            natal_chart=body.natal_chart_data,
            active_transits=active,
            query_date=body.query_date,
            chart_id=body.chart_id,
            force_refresh=body.force_refresh,
        )

        # ── 合并：把 AI 分析注入每条行运 ──
        aspect_map = {a["key"]: a for a in ai_result.get("aspects", [])}
        for t in active:
            a = aspect_map.get(t["key"], {})
            t["analysis"] = a.get("analysis", "")
            t["tone"]     = a.get("tone", "")
            t["themes"]   = a.get("themes", [])
            t["is_new"]   = a.get("is_new", False)

        return {
            "active_transits": active,
            "overall": ai_result.get("overall", ""),
        }

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transit full analysis error: {e}")


@router.post("/interpret/summarize")
async def summarize_chat(body: SummarizeRequest):
    """将一段对话历史压缩为简洁摘要，用于滚动窗口记忆。"""
    try:
        from ..rag import summarize_messages
        result = summarize_messages(body.messages, body.chart_name)
        return {"summary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarize error: {e}")