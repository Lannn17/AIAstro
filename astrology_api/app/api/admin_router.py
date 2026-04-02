import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..security import require_admin
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
from .. import rag
from ..rag.client import GENERATE_MODEL
from google.genai import types as _gtypes


router = APIRouter(prefix="/api/admin", tags=["admin"])

class CreateDraftRequest(BaseModel):
    caller: str
    prompt_text: str
    system_instruction: str = ""

class PatchDraftRequest(BaseModel):
    prompt_text: str | None = None
    system_instruction: str | None = None

class RunTestRequest(BaseModel):
    chart_id: int
    query_text: str = ""

class AdminEvalRequest(BaseModel):
    log_id: str
    score_overall: float | None = None
    dimensions: dict | None = None
    notes: str | None = None


@router.get("/analytics")
def get_analytics(_user: str = Depends(require_admin)):
    """返回 query_analytics 的聚合摘要 + 最近200条记录。"""
    return {
        "summary": db_get_analytics_summary(),
        "records": db_get_analytics_records(limit=200),
    }


@router.post("/analytics/report")
def generate_analytics_report(_user: str = Depends(require_admin)):
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
def list_prompt_versions(caller: str | None = None, _user: str = Depends(require_admin)):
    return db_list_prompt_versions(caller=caller)


@router.post("/prompt-versions")
def create_draft(body: CreateDraftRequest, _user: str = Depends(require_admin)):
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
def get_prompt_version(id: str, _user: str = Depends(require_admin)):
    v = db_get_prompt_version(id)
    if not v:
        raise HTTPException(404, "Not found")
    return v


@router.patch("/prompt-versions/{id}")
def patch_draft(id: str, body: PatchDraftRequest, _user: str = Depends(require_admin)):
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

# ── AI evaluation helper ───────────────────────────────────────────

def _run_ai_evaluation(test_log_id, test_response, version_id, deployed_log):
    results = []

    abs_prompt = f"""请对以下占星 AI 分析输出进行质量评估。

【输出内容】
{test_response[:3000]}

请以 JSON 格式返回：
{{
  "score_overall": <1-5的浮点数>,
  "dimensions": {{"accuracy": <1-5>, "readability": <1-5>, "astro_quality": <1-5>}},
  "notes": "<100字以内的综合评价>",
  "suggestions": ["<改进建议1>", "<改进建议2>"]
}}"""

    try:
        resp = rag.client.models.generate_content(
            model=GENERATE_MODEL,
            contents=abs_prompt,
            config=_gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        data = json.loads(resp.text)
        eval_id = uuid.uuid4().hex[:16]
        db_insert_prompt_evaluation(
            id_=eval_id, log_id=test_log_id, version_id=version_id,
            evaluator_type="ai_absolute",
            score_overall=data.get("score_overall"),
            dimensions=json.dumps(data.get("dimensions"), ensure_ascii=False),
            notes=data.get("notes"),
            suggestions=json.dumps(data.get("suggestions", []), ensure_ascii=False),
        )
        results.append({"type": "ai_absolute", **data})
    except Exception as e:
        print(f"[eval] ai_absolute failed: {e}")

    if deployed_log:
        cmp_prompt = f"""请对比以下两个版本的占星 AI 分析输出质量。

【当前版本（草稿）输出】
{test_response[:2000]}

【上一版本（线上）输出】
{(deployed_log.get('response_text') or '')[:2000]}

请以 JSON 格式返回：
{{
  "score_overall": <1-5，草稿版本的综合评分>,
  "dimensions": {{"accuracy": <1-5>, "readability": <1-5>, "astro_quality": <1-5>}},
  "notes": "<100字以内，对比分析草稿相对上一版本的优劣>",
  "suggestions": ["<针对草稿的改进建议>"]
}}"""
        try:
            resp = rag.client.models.generate_content(
                model=GENERATE_MODEL,
                contents=cmp_prompt,
                config=_gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            data = json.loads(resp.text)
            eval_id = uuid.uuid4().hex[:16]
            db_insert_prompt_evaluation(
                id_=eval_id, log_id=test_log_id, version_id=version_id,
                evaluator_type="ai_comparative",
                score_overall=data.get("score_overall"),
                dimensions=json.dumps(data.get("dimensions"), ensure_ascii=False),
                notes=data.get("notes"),
                suggestions=json.dumps(data.get("suggestions", []), ensure_ascii=False),
                compared_to_log_id=deployed_log["id"],
            )
            results.append({"type": "ai_comparative", "compared_to_log_id": deployed_log["id"], **data})
        except Exception as e:
            print(f"[eval] ai_comparative failed: {e}")

    return results


# ── Run test endpoint ──────────────────────────────────────────────

@router.post("/prompt-versions/{id}/run-test")
def run_test(id: str, body: RunTestRequest, _user: str = Depends(require_admin)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Version not found")

    chart = db_get_chart(body.chart_id)
    if not chart:
        raise HTTPException(404, "Chart not found")

    chart_data = json.loads(chart.get("chart_data") or "{}")
    caller = version["caller"]

    try:
        from ..rag.prompt_registry import PROMPTS
        from ..rag.chart_summary import format_chart_summary
        cfg = PROMPTS.get(caller, {})
        chart_summary = format_chart_summary(chart_data)

        draft_prompt = version["prompt_text"]
        rag_query = ""
        rag_chunks_json = "[]"

        if caller == "generate":
            # generate 需要 RAG 检索 + query 注入
            query = body.query_text or "占星基础问答"
            rag_query = query
            try:
                from ..rag.retrieval import retrieve
                chunks = retrieve(query, k=4)
                rag_chunks_json = json.dumps(chunks, ensure_ascii=False)[:4000]
                context_parts = []
                for i, c in enumerate(chunks, 1):
                    source = c["source"].replace("[EN]", "").split("(")[0].strip()
                    context_parts.append(f"[片段{i} · 来源: {source}]\n{c['text']}")
                context = "\n\n".join(context_parts)
            except Exception:
                context = "（RAG 检索失败，使用空上下文）"
            try:
                class _DD(dict):
                    def __missing__(self, key): return "{" + key + "}"
                test_prompt = draft_prompt.format_map(_DD(context=context, query=query))
            except Exception:
                test_prompt = draft_prompt

        elif caller == "chat_with_chart":
            # chat_with_chart 需要 chart_summary + transit_context
            try:
                class _DD(dict):
                    def __missing__(self, key): return "{" + key + "}"
                test_prompt = draft_prompt.format_map(_DD(chart_summary=chart_summary, transit_context=""))
            except Exception:
                test_prompt = draft_prompt

        else:
            # 其他业务 prompt 注入 chart_summary
            try:
                class _DD(dict):
                    def __missing__(self, key): return "{" + key + "}"
                test_prompt = draft_prompt.format_map(_DD(chart_summary=chart_summary))
            except Exception:
                test_prompt = draft_prompt

        import time
        t0 = time.time()
        resp = rag.client.models.generate_content(
            model=GENERATE_MODEL,
            contents=test_prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=version.get("system_instruction") or None,
                temperature=cfg.get("temperature", 0.5),
            ),
        )
        latency_ms = int((time.time() - t0) * 1000)
        response_text = getattr(resp, "text", "") or ""
    except Exception as e:
        raise HTTPException(500, f"AI call failed: {e}")

    log_id = uuid.uuid4().hex[:16]
    db_insert_prompt_log(
        id_=log_id, version_id=id, source="test",
        input_data=json.dumps({"chart_id": body.chart_id, "query_text": body.query_text}, ensure_ascii=False),
        rag_query=rag_query, rag_chunks=rag_chunks_json,
        response_text=response_text[:5000],
        latency_ms=latency_ms, model_used=GENERATE_MODEL,
        temperature=cfg.get("temperature", 0.5),
        finish_reason="STOP", prompt_tokens_est=0, response_tokens_est=0,
        user_id=None,
    )

    # 对比逻辑：deployed 版本取最近同类型 test log；当前版本若即为 deployed，取前一条
    deployed = db_get_deployed_version(caller)
    deployed_log = None
    if deployed and deployed["id"] != id:
        deployed_log = db_get_recent_log_for_version(deployed["id"], source="test")
        if not deployed_log:
            deployed_log = db_get_recent_log_for_version(deployed["id"])

    evaluations = _run_ai_evaluation(log_id, response_text, id, deployed_log)

    return {
        "log_id": log_id,
        "response_text": response_text,
        "latency_ms": latency_ms,
        "evaluations": evaluations,
        "deployed_response": deployed_log.get("response_text") if deployed_log else None,
    }


# ── Prompt logs + evaluations ──────────────────────────────────────

@router.get("/prompt-logs")
def list_prompt_logs(
    version_id: str | None = None,
    caller: str | None = None,
    source: str | None = None,
    limit: int = 50,
    _user: str = Depends(require_admin),
):
    return db_query_prompt_logs(version_id=version_id, caller=caller, source=source, limit=limit)


@router.get("/prompt-logs/{log_id}/evaluations")
def get_log_evaluations(log_id: str, _user: str = Depends(require_admin)):
    return db_get_evaluations_for_log(log_id)


@router.post("/prompt-evaluations")
def submit_admin_eval(body: AdminEvalRequest, _user: str = Depends(require_admin)):
    version_id = None
    try:
        rows = _turso_query("SELECT version_id FROM prompt_logs WHERE id=?", [body.log_id])
        version_id = rows[0]["version_id"] if rows else None
    except Exception:
        pass
    eval_id = uuid.uuid4().hex[:16]
    db_insert_prompt_evaluation(
        id_=eval_id, log_id=body.log_id, version_id=version_id,
        evaluator_type="admin",
        score_overall=body.score_overall,
        dimensions=json.dumps(body.dimensions, ensure_ascii=False) if body.dimensions else None,
        notes=body.notes,
        suggestions=None,
    )
    return {"id": eval_id, "status": "ok"}

# ── Deploy, revise, compare ────────────────────────────────────────

@router.post("/prompt-versions/{id}/deploy")
def deploy_version(id: str, _user: str = Depends(require_admin)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Not found")
    if version["status"] != "draft":
        raise HTTPException(400, "Only draft can be deployed")

    caller = version["caller"]
    all_versions = db_list_prompt_versions(caller=caller)
    major_tags = [
        int(v["version_tag"].lstrip("v"))
        for v in all_versions
        if v["version_tag"].startswith("v") and "." not in v["version_tag"]
        and v["version_tag"].lstrip("v").isdigit()
    ]
    next_major = max(major_tags, default=0) + 1
    new_tag = f"v{next_major}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    deployed = db_get_deployed_version(caller)
    if deployed:
        db_update_prompt_version(deployed["id"], status="retired")

    db_update_prompt_version(id, status="deployed", version_tag=new_tag, deployed_at=now)
    _cache_set(caller, id)

    return db_get_prompt_version(id)


@router.post("/prompt-versions/{id}/revise")
def revise_version(id: str, _user: str = Depends(require_admin)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Not found")
    if version["status"] != "draft":
        raise HTTPException(400, "Only draft can be revised")

    # 若 prompt_text 与上一个 superseded/deployed 版本完全相同，直接返回当前版本
    caller = version["caller"]
    all_versions = db_list_prompt_versions(caller=caller)
    prev_texts = {
        v["prompt_text"] for v in all_versions
        if v["id"] != id and v["status"] in ("deployed", "superseded")
    }
    if version["prompt_text"] in prev_texts:
        return version

    current_tag = version["version_tag"]
    parts = current_tag.split(".")
    base = parts[0]
    minor = int(parts[1]) if len(parts) > 1 else 0
    new_tag = f"{base}.{minor + 1}"

    db_update_prompt_version(id, status="superseded")

    new_id = uuid.uuid4().hex[:16]
    db_insert_prompt_version(
        id_=new_id,
        caller=caller,
        version_tag=new_tag,
        prompt_text=version["prompt_text"],
        system_instruction=version.get("system_instruction"),
        status="draft",
    )
    return db_get_prompt_version(new_id)


@router.get("/prompt-versions/{id}/compare")
def compare_versions(id: str, _user: str = Depends(require_admin)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Not found")
    deployed = db_get_deployed_version(version["caller"])
    return {
        "draft": version,
        "deployed": deployed,
        "draft_evaluations": db_get_evaluations_for_version(id),
        "deployed_evaluations": db_get_evaluations_for_version(deployed["id"]) if deployed else [],
    }