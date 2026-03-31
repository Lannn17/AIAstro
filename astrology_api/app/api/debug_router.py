"""
app/api/debug_router.py — Prompt 可观测性接口
"""

import os
from fastapi import APIRouter, Query, Header, HTTPException, Body
from ..prompt_log import prompt_store

router = APIRouter(prefix="/api/debug", tags=["debug"])

# ── 鉴权 ──────────────────────────────────────────────────────────
# .env 中加一行: DEBUG_TOKEN=你自己设一个随机字符串
_DEBUG_TOKEN = os.getenv("DEBUG_TOKEN", "")


def _check_token(x_debug_token: str = Header("")):
    if not _DEBUG_TOKEN:
        raise HTTPException(503, "DEBUG_TOKEN 未配置，debug 接口已禁用")
    if x_debug_token != _DEBUG_TOKEN:
        raise HTTPException(401, "unauthorized")


# ── 1. 列表（摘要） ───────────────────────────────────────────────

@router.get("/prompts")
def list_prompts(
    limit: int = Query(20, ge=1, le=200),
    caller: str = Query(""),
    x_debug_token: str = Header(""),
):
    """
    GET /api/debug/prompts?limit=20&caller=analyze_planets

    返回最近的 prompt 调用记录（摘要模式）
    """
    _check_token(x_debug_token)

    if caller:
        logs = prompt_store.get_by_caller(caller, limit=limit)
    else:
        logs = prompt_store.get_all(limit=limit)

    summaries = []
    for log in logs:
        pt = log["prompt_text"]
        rt = log["response_text"]
        summaries.append({
            "id":                 log["id"],
            "timestamp":          log["timestamp_readable"],
            "caller":             log["caller"],
            "model":              log["model"],
            "model_used":         log["model_used"],
            "temperature":        log["temperature"],
            "prompt_preview":     pt[:200] + "…" if len(pt) > 200 else pt,
            "prompt_tokens_est":  log["prompt_tokens_est"],
            "response_preview":   rt[:200] + "…" if len(rt) > 200 else rt,
            "response_tokens_est": log["response_tokens_est"],
            "finish_reason":      log["finish_reason"],
            "latency_ms":         log["latency_ms"],
        })

    return {"count": len(summaries), "logs": summaries}


# ── 2. 统计（必须在 /{log_id} 之前注册，否则被参数路由遮蔽） ───────

@router.get("/prompts/stats")
def prompt_stats(x_debug_token: str = Header("")):
    _check_token(x_debug_token)

    from collections import defaultdict
    all_logs = prompt_store.get_all(limit=200)
    stats = defaultdict(lambda: {"count": 0, "total_latency": 0, "total_tokens": 0})

    for log in all_logs:
        c = log["caller"]
        stats[c]["count"] += 1
        stats[c]["total_latency"] += log["latency_ms"]
        stats[c]["total_tokens"] += log["prompt_tokens_est"]

    result = {}
    for caller, s in stats.items():
        n = s["count"]
        result[caller] = {
            "count":            n,
            "avg_latency_ms":   round(s["total_latency"] / n),
            "avg_prompt_tokens": round(s["total_tokens"] / n),
        }
    return result


# ── 3. 清空缓冲区 ──────────────────────────────────────────────────

@router.delete("/prompts")
def clear_prompts(x_debug_token: str = Header("")):
    """DELETE /api/debug/prompts — 清空内存缓冲，便于隔离调试特定功能"""
    _check_token(x_debug_token)
    prompt_store.clear()
    return {"cleared": True}


# ── 4. 详情（完整 prompt + response） ─────────────────────────────

@router.get("/prompts/{log_id}")
def get_prompt_detail(log_id: str, x_debug_token: str = Header("")):
    """GET /api/debug/prompts/{log_id}"""
    _check_token(x_debug_token)

    log = prompt_store.get_by_id(log_id)
    if not log:
        raise HTTPException(404, "not found")
    return log


# ── 3. 重放（可修改参数后重新调用） ────────────────────────────────

@router.post("/prompts/{log_id}/replay")
def replay_prompt(
    log_id: str,
    x_debug_token: str = Header(""),
    body: dict = Body(default={}),
):
    """
    POST /api/debug/prompts/{log_id}/replay
    Body(可选): {"temperature": 0.3, "model": "gemini-2.5-flash", "prompt_text": "自定义prompt"}
    """
    _check_token(x_debug_token)

    log = prompt_store.get_by_id(log_id)
    if not log:
        raise HTTPException(404, "not found")

    from ..rag import client, GENERATE_MODEL
    from google.genai import types

    temperature = body.get("temperature", log["temperature"])
    model = body.get("model", log["model"])
    custom_prompt = body.get("prompt_text", None)
    prompt_text = custom_prompt or log["prompt_text"]

    config_kwargs = {"temperature": temperature}
    sys_inst = log.get("system_instruction", "")
    if sys_inst:
        config_kwargs["system_instruction"] = sys_inst

    response = client.models.generate_content(
        model=model,
        contents=prompt_text,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    return {
        "original_id":     log_id,
        "model":           model,
        "temperature":     temperature,
        "prompt_modified": custom_prompt is not None,
        "response_text":   response.text,
        "finish_reason":   (
            response.candidates[0].finish_reason.name
            if response.candidates else "UNKNOWN"
        ),
    }


# ── 4. 对比 ───────────────────────────────────────────────────────

@router.post("/prompts/compare")
def compare_prompts(
    body: dict = Body(...),
    x_debug_token: str = Header(""),
):
    """
    POST /api/debug/prompts/compare
    Body: {"ids": ["abc123", "def456"]}
    """
    _check_token(x_debug_token)

    ids = body.get("ids", [])
    if len(ids) < 2:
        raise HTTPException(400, "至少提供 2 个 log id")

    logs = [prompt_store.get_by_id(lid) for lid in ids]
    logs = [l for l in logs if l]

    if len(logs) < 2:
        raise HTTPException(404, "部分 id 未找到")

    return {
        "entries": logs,
        "diff_summary": {
            "models":          [l["model_used"] for l in logs],
            "temperatures":    [l["temperature"] for l in logs],
            "prompt_lengths":  [l["prompt_tokens_est"] for l in logs],
            "response_lengths": [l["response_tokens_est"] for l in logs],
            "latencies_ms":    [l["latency_ms"] for l in logs],
        },
    }
