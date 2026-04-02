"""
app/rag/client.py — AI 客户端：Gemini + SiliconFlow fallback + 区域切换
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

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_MODEL   = "Qwen/Qwen3.5-4B"

_raw_client = genai.Client(api_key=GOOGLE_API_KEY)

GENERATE_MODEL   = "gemini-3.1-flash-lite-preview"
_FALLBACK_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

_local = threading.local()  # per-thread tracking of last model used

# Per-request region (CN / GLOBAL) — ContextVar is async-safe
_region_var: ContextVar[str] = ContextVar('region', default='GLOBAL')


def set_thread_region(region: str) -> None:
    _region_var.set(region)


def get_thread_region() -> str:
    return _region_var.get()


def get_last_model_used() -> str:
    """返回本线程最近一次 generate_content 实际使用的模型名。"""
    return getattr(_local, 'model_used', GENERATE_MODEL)


class _DSFinishReason:
    name = "STOP"


class _DSCandidate:
    finish_reason = _DSFinishReason()


class _DeepSeekResponse:
    """Minimal adapter so SiliconFlow responses look like Gemini GenerateContentResponse."""
    def __init__(self, text: str):
        self.text = text
        self.candidates = [_DSCandidate()]


class _ModelsWithFallback:
    """Wraps generate_content with automatic model fallback + prompt logging."""

    def __init__(self, original):
        self._orig = original

    @staticmethod
    def _extract_prompt_text(contents, config) -> tuple[str, str]:
        """从 contents 和 config 中提取可读文本，返回 (system_instruction, prompt_text)"""
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
        """遍历调用栈，找到 app/ 目录下的业务函数名"""
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
        """Convert Gemini contents + config to OpenAI chat messages format."""
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
        """将 contents 序列化为可 JSON 化的 list"""
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

        # 读取 retrieve() 暂存的 RAG 信息
        entry.rag_query = getattr(_local, 'pending_rag_query', '')
        _local.pending_rag_query = ''
        entry.rag_chunks = getattr(_local, 'pending_rag_chunks', [])
        _local.pending_rag_chunks = []

        # ── Fallback 调用 ──
        chain = [model] + [m for m in _FALLBACK_MODELS if m != model]
        last_err = None
        t0 = time.time()

        # ★ 在 if 判断之前加这几行
    print(f"[DIAG] get_thread_region() = {get_thread_region()}", flush=True)
    print(f"[DIAG] SILICONFLOW_API_KEY = {repr(SILICONFLOW_API_KEY)}", flush=True)
    print(f"[DIAG] SILICONFLOW_MODEL = {repr(SILICONFLOW_MODEL)}", flush=True)
    print(f"[DIAG] Condition: region=={'CN'==get_thread_region()}, key_exists={bool(SILICONFLOW_API_KEY)}", flush=True)

# ── SiliconFlow path (CN region) ──
if get_thread_region() == "CN" and SILICONFLOW_API_KEY:
    print("[DIAG] ✅ Entering SiliconFlow path", flush=True)
    # ... 你的代码 ...
else:
    print("[DIAG] ❌ Skipped SiliconFlow path, falling to Gemini", flush=True)
        # ── SiliconFlow path (CN region) ──
        if get_thread_region() == "CN" and SILICONFLOW_API_KEY:
            try:
                from openai import OpenAI as _OpenAI
                sf = _OpenAI(api_key=SILICONFLOW_API_KEY, base_url="https://api.siliconflow.cn/v1")
                msgs = self._to_openai_messages(contents, config)
                temp = getattr(config, 'temperature', 0.5) if config else 0.5
                wants_json = (
                    config and getattr(config, 'response_mime_type', '') == 'application/json'
                )
                create_kwargs = dict(model=SILICONFLOW_MODEL, messages=msgs, temperature=temp)
                if wants_json:
                    create_kwargs['response_format'] = {"type": "json_object"}
                completion = sf.chat.completions.create(**create_kwargs)
                text = completion.choices[0].message.content or ""
                _local.model_used = SILICONFLOW_MODEL
                entry.model_used = SILICONFLOW_MODEL
                entry.response_text = text[:5000]
                entry.finish_reason = "STOP"
                entry.response_tokens_est = len(text) // 2
                entry.latency_ms = int((time.time() - t0) * 1000)
                prompt_store.append(entry)
                _persist_prompt_log(entry)
                return _DeepSeekResponse(text)
            except Exception as e:
                print(f"[SiliconFlow] failed, falling back to Gemini: {e}", flush=True)

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
    """Wraps genai.Client so client.models uses fallback logic."""
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
