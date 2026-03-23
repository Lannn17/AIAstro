from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List
from ..interpretations.text_search import simple_text_search

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
    mode: str = "interpret"  # "rag" = RAG测试版, "interpret" = AI解读版
    history: List[HistoryMessage] = []


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
        history = [{"role": m.role, "text": m.text} for m in body.history]
        if body.mode == "rag":
            from ..rag import rag_query_with_chart
            result = rag_query_with_chart(body.query, body.chart_data, k=body.k, history=history)
        else:
            from ..rag import interpret_with_chart
            result = interpret_with_chart(body.query, body.chart_data, k=body.k, history=history)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")