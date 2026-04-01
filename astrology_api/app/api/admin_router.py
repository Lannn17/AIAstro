import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..security import require_auth
from ..db import (
    db_get_analytics_summary, db_get_analytics_records,
    db_list_prompt_versions, db_get_prompt_version,
    db_insert_prompt_version, db_update_prompt_version,
    db_get_deployed_version, db_get_chart,
    db_insert_prompt_log, db_insert_prompt_evaluation,
    db_get_evaluations_for_log, db_get_recent_log_for_version,
    db_query_prompt_logs, db_get_evaluations_for_version,
    _turso_query,
)
from ..prompt_version_cache import set_version_id as _cache_set


router = APIRouter(prefix="/api/admin", tags=["admin"])

class CreateDraftRequest(BaseModel):
    caller: str
    prompt_text: str
    system_instruction: str = ""

class PatchDraftRequest(BaseModel):
    prompt_text: str | None = None
    system_instruction: str | None = None


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
    
# ── Prompt versions CRUD ───────────────────────────────────────────

@router.get("/prompt-versions")
def list_prompt_versions(caller: str | None = None, _user: str = Depends(require_auth)):
    return db_list_prompt_versions(caller=caller)


@router.post("/prompt-versions")
def create_draft(body: CreateDraftRequest, _user: str = Depends(require_auth)):
    deployed = db_get_deployed_version(body.caller)
    if deployed:
        base = deployed["version_tag"]
        all_versions = db_list_prompt_versions(caller=body.caller)
        prefix = base + "."
        minors = [
            int(v["version_tag"].split(".")[-1])
            for v in all_versions
            if v["version_tag"].startswith(prefix) and v["version_tag"].split(".")[-1].isdigit()
        ]
        next_minor = max(minors, default=0) + 1
        version_tag = f"{base}.{next_minor}"
    else:
        version_tag = "v1"

    id_ = uuid.uuid4().hex[:16]
    db_insert_prompt_version(
        id_=id_,
        caller=body.caller,
        version_tag=version_tag,
        prompt_text=body.prompt_text,
        system_instruction=body.system_instruction or None,
        status="draft" if deployed else "deployed",
        deployed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if not deployed else None,
    )
    if not deployed:
        _cache_set(body.caller, id_)
    return db_get_prompt_version(id_)


@router.get("/prompt-versions/{id}")
def get_prompt_version(id: str, _user: str = Depends(require_auth)):
    v = db_get_prompt_version(id)
    if not v:
        raise HTTPException(404, "Not found")
    return v


@router.patch("/prompt-versions/{id}")
def patch_draft(id: str, body: PatchDraftRequest, _user: str = Depends(require_auth)):
    v = db_get_prompt_version(id)
    if not v:
        raise HTTPException(404, "Not found")
    if v["status"] != "draft":
        raise HTTPException(400, "Only draft versions can be edited")
    updates = {}
    if body.prompt_text is not None:
        updates["prompt_text"] = body.prompt_text
    if body.system_instruction is not None:
        updates["system_instruction"] = body.system_instruction
    if updates:
        db_update_prompt_version(id, **updates)
    return db_get_prompt_version(id)
