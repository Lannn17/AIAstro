"""
app/rag/client.py — AI 客户端：Gemini + OpenRouter fallback + 区域切换
"""
import os
import time
import inspect
import threading
from contextvars import ContextVar

from google import genai
from google.genai import types
from dotenv import load_dotenv

from ..prompt_log import PromptLogEntry, prompt_store
from ..prompt_version_cache import get_version_id as _get_version_id

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("请在 .env 中设置 GOOGLE_API_KEY")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-14b-plus:free")
OPENROUTER_BASE    = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# ★ 启动时打印，方便确认环境变量
print(f"[STARTUP] OPENROUTER_API_KEY: {'SET (' + OPENROUTER_API_KEY[:8] + '...)' if OPENROUTER_API_KEY else 'NOT SET'}", flush=True)
print(f"[STARTUP] OPENROUTER_MODEL: {OPENROUTER_MODEL}", flush=True)
print(f"[STARTUP] OPENROUTER_BASE: {OPENROUTER_BASE}", flush=True)

_raw_client = genai.Client(api_key=GOOGLE_API_KEY)

GENERATE_MODEL   = "gemini-3.1-flash-lite-preview"
_FALLBACK_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

_local = threading.local()

_region_var: ContextVar[str] = ContextVar('region', default='GLOBAL')


def set_thread_region(region: str) -> None:
    _region_var.set(region)


def get_thread_region() -> str:
    return _region_var.get()


def get_last_model_used() -> str:
    return getattr(_local, 'model_used', GENERATE_MODEL)


class _DSFinishReason:
    name = "STOP"


class _DSCandidate:
    finish_reason = _DSFinishReason()


class _DeepSeekResponse:
    """Minimal adapter so OpenRouter responses look like Gemini GenerateContentResponse."""
    def __init__(self, text: str):
        self.text = text
        self.candidates = [_DSCandidate()]


class _ModelsWithFallback:
    """Wraps generate_content with automatic model fallback + prompt logging."""

    def __init__(self, original):
        self._orig = original

    @staticmethod
    def _extract_prompt_text(contents, config) -> tuple[str, str]:
        sys_inst = ""
        if config:
            si = getattr(config, 'system_instruction', None)
            if si:
                sys_inst = si if isinstance(si, str) else str(si)

        if isinstance(contents, str):
            return sys_inst, contents

        parts = []
        if isinstance(contents, list):
            for item in contents:
                role = getattr(item, 'role', 'unknown')
                item_parts = getattr(item, 'parts', [])
                for p in item_parts:
                    text = getattr(p, 'text', str(p))
                    parts.append(f"[{role}] {text}")
        else:
            parts.append(str(contents))

        return sys_inst, "\n---\n".join(parts)

    @staticmethod
    def _guess_caller() -> str:
        for frame_info in inspect.stack():
            fn_name = frame_info.function
            filename = frame_info.filename
            if ('app/' in filename or 'app\\' in filename) and fn_name not in (
                'generate_content', '_guess_caller',
                '_extract_prompt_text',
            ):
                if not fn_name.startswith('_'):
                    return fn_name
        return "unknown"

    @staticmethod
    def _to_openai_messages(contents, config=None) -> list[dict]:
        messages = []
        if config:
            si = getattr(config, 'system_instruction', None)
            if si:
                messages.append({"role": "system", "content": si if isinstance(si, str) else str(si)})
        if isinstance(contents, str):
            messages.append({"role": "user", "content": contents})
        elif isinstance(contents, list):
            for item in contents:
                role = getattr(item, 'role', 'user')
                if role == 'model':
                    role = 'assistant'
                text = "".join(
                    getattr(p, 'text', str(p))
                    for p in getattr(item, 'parts', [])
                )
                messages.append({"role": role, "content": text})
        return messages

    @staticmethod
    def _serialize_contents(contents) -> list:
        try:
            if isinstance(contents, str):
                return [{"role": "user", "text": contents}]
            if isinstance(contents, list):
                return [
                    {
                        "role": getattr(c, 'role', 'unknown'),
                        "text": " ".join(
                            getattr(p, 'text', str(p))
                            for p in getattr(c, 'parts', [])
                        ),
                    }
                    for c in contents
                ]
            return [{"raw": str(contents)[:2000]}]
        except Exception:
            return [{"raw": str(contents)[:2000]}]

    def generate_content(self, model, contents, config=None, **kwargs):
        # ── 构建日志条目 ──
        entry = PromptLogEntry(
            model=model,
            caller=self._guess_caller(),
            temperature=getattr(config, 'temperature', 0) if config else 0,
        )
        entry.version_id = _get_version_id(entry.caller) or ""
        sys_inst, prompt_text = self._extract_prompt_text(contents, config)
        entry.system_instruction = sys_inst
        entry.prompt_text = prompt_text
        entry.prompt_tokens_est = len(prompt_text) // 2
        entry.contents = self._serialize_contents(contents)

        entry.rag_query = getattr(_local, 'pending_rag_query', '')
        _local.pending_rag_query = ''
        entry.rag_chunks = getattr(_local, 'pending_rag_chunks', [])
        _local.pending_rag_chunks = []

        t0 = time.time()

        # ── OpenRouter path (CN region) ──
        if get_thread_region() == "CN" and OPENROUTER_API_KEY:
            print(f"[OpenRouter] ✅ Region=CN, calling model={OPENROUTER_MODEL}", flush=True)
            print(f"[OpenRouter] Base URL: {OPENROUTER_BASE}", flush=True)
            try:
                from openai import OpenAI as _OpenAI
                import httpx as _httpx

                # ★ 先快速测试连通性（5秒内知道能不能通）
                try:
                    _test = _httpx.get(
                        f"{OPENROUTER_BASE}/models",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                        timeout=5.0,
                    )
                    print(f"[OpenRouter] Connectivity test: HTTP {_test.status_code}", flush=True)
                except Exception as _ce:
                    print(f"[OpenRouter] ❌ Cannot reach {OPENROUTER_BASE}: {_ce}", flush=True)
                    entry.model_used = OPENROUTER_MODEL
                    entry.response_text = f"ERROR: Cannot reach OpenRouter: {_ce}"
                    entry.latency_ms = int((time.time() - t0) * 1000)
                    prompt_store.append(entry)
                    _persist_prompt_log(entry)
                    return _DeepSeekResponse(f"⚠️ 无法连接AI服务({OPENROUTER_BASE})，请稍后重试。")

                sf = _OpenAI(
                    api_key=OPENROUTER_API_KEY,
                    base_url=OPENROUTER_BASE,
                    timeout=30.0,  # ★ 30秒超时
                )
                msgs = self._to_openai_messages(contents, config)
                temp = getattr(config, 'temperature', 0.5) if config else 0.5
                wants_json = (
                    config and getattr(config, 'response_mime_type', '') == 'application/json'
                )
                create_kwargs = dict(model=OPENROUTER_MODEL, messages=msgs, temperature=temp)
                if wants_json:
                    create_kwargs['response_format'] = {"type": "json_object"}

                print(f"[OpenRouter] Sending request: msgs={len(msgs)}, temp={temp}, json={wants_json}", flush=True)
                completion = sf.chat.completions.create(**create_kwargs)
                text = completion.choices[0].message.content or ""
                print(f"[OpenRouter] ✅ Success! Response length={len(text)}", flush=True)

                _local.model_used = OPENROUTER_MODEL
                entry.model_used = OPENROUTER_MODEL
                entry.response_text = text[:5000]
                entry.finish_reason = "STOP"
                entry.response_tokens_est = len(text) // 2
                entry.latency_ms = int((time.time() - t0) * 1000)
                prompt_store.append(entry)
                _persist_prompt_log(entry)
                return _DeepSeekResponse(text)

            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                print(f"[OpenRouter] ❌ FAILED: {error_msg}", flush=True)
                entry.model_used = OPENROUTER_MODEL
                entry.response_text = f"ERROR: {error_msg}"
                entry.latency_ms = int((time.time() - t0) * 1000)
                prompt_store.append(entry)
                _persist_prompt_log(entry)
                return _DeepSeekResponse(f"⚠️ AI服务暂时不可用，请稍后重试。\n错误: {error_msg}")

        else:
            if get_thread_region() == "CN":
                print(f"[OpenRouter] ❌ Region=CN but OPENROUTER_API_KEY is empty!", flush=True)

        # ── Gemini Fallback 调用 (GLOBAL only) ──
        chain = [model] + [m for m in _FALLBACK_MODELS if m != model]
        last_err = None

        for m in chain:
            try:
                resp = self._orig.generate_content(
                    model=m, contents=contents, config=config, **kwargs
                )
                _local.model_used = m

                entry.model_used = m
                entry.response_text = getattr(resp, 'text', '')[:5000]
                entry.finish_reason = (
                    resp.candidates[0].finish_reason.name
                    if resp.candidates else "UNKNOWN"
                )
                entry.response_tokens_est = len(entry.response_text) // 2
                entry.latency_ms = int((time.time() - t0) * 1000)
                prompt_store.append(entry)
                _persist_prompt_log(entry)
                return resp

            except Exception as e:
                if '503' in str(e) or 'UNAVAILABLE' in str(e):
                    print(f"[fallback] {m} 503, trying next…", flush=True)
                    last_err = e
                    continue
                entry.model_used = m
                entry.response_text = f"ERROR: {e}"
                entry.latency_ms = int((time.time() - t0) * 1000)
                prompt_store.append(entry)
                _persist_prompt_log(entry)
                raise

        entry.response_text = f"ALL_FAILED: {last_err}"
        entry.latency_ms = int((time.time() - t0) * 1000)
        prompt_store.append(entry)
        _persist_prompt_log(entry)
        raise last_err

    def __getattr__(self, name):
        return getattr(self._orig, name)


class _ClientWithFallback:
    def __init__(self, original):
        self._orig = original
        self.models = _ModelsWithFallback(original.models)

    def __getattr__(self, name):
        return getattr(self._orig, name)


client = _ClientWithFallback(_raw_client)


def _persist_prompt_log(entry) -> None:
    try:
        import json as _json, uuid as _uuid
        from ..db import db_insert_prompt_log
        db_insert_prompt_log(
            id_=_uuid.uuid4().hex[:16],
            version_id=entry.version_id or None,
            source="production",
            input_data=None,
            rag_query=entry.rag_query,
            rag_chunks=_json.dumps(entry.rag_chunks, ensure_ascii=False)[:4000],
            response_text=entry.response_text[:5000],
            latency_ms=entry.latency_ms,
            model_used=entry.model_used,
            temperature=entry.temperature,
            finish_reason=entry.finish_reason,
            prompt_tokens_est=entry.prompt_tokens_est,
            response_tokens_est=entry.response_tokens_est,
            user_id=None,
        )
    except Exception as e:
        print(f"[PromptLog] persist failed: {e}", flush=True)