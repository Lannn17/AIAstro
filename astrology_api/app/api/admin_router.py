from fastapi import APIRouter, HTTPException, Depends
from ..security import require_auth
from ..db import db_get_analytics_summary, db_get_analytics_records

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/analytics")
def get_analytics(_user: str = Depends(require_auth)):
    """返回 query_analytics 的聚合摘要 + 最近200条记录。"""
    return {
        "summary": db_get_analytics_summary(),
        "records": db_get_analytics_records(limit=200),
    }


@router.post("/analytics/report")
def generate_analytics_report(_user: str = Depends(require_auth)):
    """用 Gemini 生成 RAG 质量分析报告。"""
    summary = db_get_analytics_summary()
    if not summary:
        return {"report": "暂无数据，请在占星对话模块积累一些对话后再生成报告。"}
    try:
        from ..rag import client, GENERATE_MODEL
        from google.genai import types

        summary_text = "\n".join(
            f"- {r['label']}: {r['count']}条, 平均RAG分={r['avg_score']}, 引用率={r['cite_rate']}"
            for r in summary
        )
        total = sum(r["count"] for r in summary)

        prompt = f"""以下是占星对话系统的 RAG 检索质量统计数据（共 {total} 条对话）：

{summary_text}

说明：
- avg_score：向量检索相似度均值（0~1，越高说明书籍库与该类问题的匹配越好）
- cite_rate：AI 在回答中引用书籍的比例（越高说明检索结果对 AI 有帮助）

请生成一份简洁的中文分析报告，包含：
1. 整体 RAG 覆盖情况评估
2. 哪类问题检索效果最好 / 最差（重点分析 avg_score 较低的类别）
3. 具体建议（应补充哪类占星书籍内容来改善弱项）
4. 一句话总结"""

        resp = client.models.generate_content(
            model=GENERATE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7)
        )
        return {"report": resp.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
