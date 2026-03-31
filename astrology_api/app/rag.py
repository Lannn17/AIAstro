"""
app/rag.py — RAG 核心模块

流程：query → sentence-transformers(e5) → Qdrant检索 → Gemini生成答案
"""

import os
import re
import json
import threading
from contextvars import ContextVar
import numpy as np
import time       # 如果已有就不用重复
import inspect    # 新增
from .prompt_log import PromptLogEntry, prompt_store   # 新增
from google import genai
from google.genai import types
from dotenv import load_dotenv
from .interpretations.translations import translate_planet, translate_sign, translate_aspect

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("请在 .env 中设置 GOOGLE_API_KEY")

QDRANT_URL     = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError("请在 .env 中设置 QDRANT_URL 和 QDRANT_API_KEY")

_raw_client = genai.Client(api_key=GOOGLE_API_KEY)

GENERATE_MODEL  = "gemini-3.1-flash-lite-preview"
_FALLBACK_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = "deepseek-chat"

_local = threading.local()  # per-thread tracking of last model used

# Per-request region (CN / GLOBAL) — ContextVar is async-safe unlike threading.local
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
    """Minimal adapter so DeepSeek responses look like Gemini GenerateContentResponse."""
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
            # 匹配 app/ 下所有 .py，排除本类自身的方法
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

        # ── DeepSeek path (CN region) ──────────────────────────────────────
        if get_thread_region() == "CN" and DEEPSEEK_API_KEY:
            try:
                from openai import OpenAI as _OpenAI
                ds = _OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
                msgs = self._to_openai_messages(contents, config)
                temp = getattr(config, 'temperature', 0.5) if config else 0.5
                completion = ds.chat.completions.create(
                    model=DEEPSEEK_MODEL,
                    messages=msgs,
                    temperature=temp,
                )
                text = completion.choices[0].message.content or ""
                _local.model_used = DEEPSEEK_MODEL
                entry.model_used = DEEPSEEK_MODEL
                entry.response_text = text[:5000]
                entry.finish_reason = "STOP"
                entry.response_tokens_est = len(text) // 2
                entry.latency_ms = int((time.time() - t0) * 1000)
                prompt_store.append(entry)
                return _DeepSeekResponse(text)
            except Exception as e:
                print(f"[DeepSeek] failed, falling back to Gemini: {e}", flush=True)
                # fall through to Gemini loop below

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
                raise

        entry.response_text = f"ALL_FAILED: {last_err}"
        entry.latency_ms = int((time.time() - t0) * 1000)
        prompt_store.append(entry)
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
COLLECTION_NAME = "astro_chunks"
E5_MODEL        = "intfloat/multilingual-e5-small"
E5_PREFIX       = "query: "
_index_source   = "qdrant"

_QUERY_LABELS = (
    "planet_sign",   # 行星在某星座的解读
    "planet_house",  # 行星在某宫位的解读
    "aspect",        # 相位解读
    "life_area",     # 感情/事业/财运/健康等生活领域
    "psychological", # 性格/心理/行为模式
    "prediction",    # 运势预测/时机判断
    "other",         # 兜底
)


def classify_query(query: str) -> str:
    """用 Gemini 将占星问题分类为 7 个预定义标签之一。失败时返回 'other'。"""
    labels_str = " | ".join(_QUERY_LABELS)
    prompt = (
        f"占星问题：{query}\n\n"
        f"从以下标签中选一个最合适的，只输出标签本身，不要其他文字：\n{labels_str}"
    )
    try:
        resp = client.models.generate_content(
            model=GENERATE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )
        label = resp.text.strip().lower().rstrip(".，。")
        return label if label in _QUERY_LABELS else "other"
    except Exception as e:
        print(f"[Analytics] classify_query failed: {e}", flush=True)
        return "other"


def _parse_json(text: str) -> dict | list:
    """Strip optional markdown code fences then parse JSON."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` wrappers
    text = re.sub(r'^```[a-z]*\s*', '', text)
    text = re.sub(r'\s*```$', '', text.strip())
    return json.loads(text.strip())


# ── 懒加载（首次查询时初始化）────────────────────────────────────

_qdrant = None          # QdrantClient
_e5_model = None        # SentenceTransformer


def _load():
    global _qdrant, _e5_model
    if _qdrant is not None:
        return
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer
    _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30)
    _e5_model = SentenceTransformer(E5_MODEL)
    print(f"[RAG] Qdrant connected, e5 model loaded")


# ── Retrieval ─────────────────────────────────────────────────────

def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    向量检索，返回 top-k 相关 chunks。
    每条结果格式: {text, source, start, score}
    """
    _load()

    query_vec = _e5_model.encode(
        [E5_PREFIX + query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].tolist()

    response = _qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=k,
        with_payload=True,
    )

    results = []
    for hit in response.points:
        p = hit.payload or {}
        results.append({
            "text":   p.get("text", ""),
            "source": p.get("source", ""),
            "start":  p.get("start", 0),
            "score":  round(float(hit.score), 4),
        })

    # 暂存供 _ModelsWithFallback 日志读取
    _local.pending_rag_query = query
    _local.pending_rag_chunks = results

    return results


# ── Generation ────────────────────────────────────────────────────

_SYSTEM_PROMPT_RAG = """你是一位专业的占星师助手。根据下方提供的占星书籍原文片段和用户的本命盘数据，
用中文回答用户的问题。回答要具体、有依据，并在适当位置注明参考来源（书名）。
如果片段中没有足够信息，请如实说明，不要编造内容。"""

_SYSTEM_PROMPT_INTERPRET = """你是一位经验丰富的职业占星师，精通西方占星学。
请基于你深厚的占星学专业知识，结合用户提供的本命盘数据，用中文给出深入、具体的解读。
如果提供了参考书籍片段且与问题相关，可以引用作为佐证，但解读质量不依赖于这些片段。"""

# 兼容旧代码
_SYSTEM_PROMPT = _SYSTEM_PROMPT_RAG


def generate(query: str, chunks: list[dict]) -> str:
    """用检索到的 chunks 作为上下文，调用 Gemini 生成解读。"""
    context_parts = []
    for i, c in enumerate(chunks, 1):
        source = c["source"].replace("[EN]", "").split("(")[0].strip()
        context_parts.append(f"[片段{i} · 来源: {source}]\n{c['text']}")

    context = "\n\n".join(context_parts)

    prompt = f"""以下是来自占星书籍的相关片段：

{context}

---
用户问题：{query}

请根据以上片段回答问题。"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.4,
        ),
    )
    return response.text


# ── 星盘摘要格式化辅助数据 ────────────────────────────────────────

_SIGN_ELEMENT = {
    "Aries": "火", "Leo": "火", "Sagittarius": "火",
    "Taurus": "土", "Virgo": "土", "Capricorn": "土",
    "Gemini": "风", "Libra": "风", "Aquarius": "风",
    "Cancer": "水", "Scorpio": "水", "Pisces": "水",
}

_SIGN_MODALITY = {
    "Aries": "开创", "Cancer": "开创", "Libra": "开创", "Capricorn": "开创",
    "Taurus": "固定", "Leo": "固定", "Scorpio": "固定", "Aquarius": "固定",
    "Gemini": "变动", "Virgo": "变动", "Sagittarius": "变动", "Pisces": "变动",
}

# 传统+现代守护星：星座 → 守护星英文名
_SIGN_RULER = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Pluto", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}

# 七颗传统行星的尊贵表（英文名）
_DIGNITY = {
    # planet: {domicile:[signs], exalt:sign, detriment:[signs], fall:sign}
    "Sun":     {"domicile": ["Leo"],               "exalt": "Aries",      "detriment": ["Aquarius"],         "fall": "Libra"},
    "Moon":    {"domicile": ["Cancer"],             "exalt": "Taurus",     "detriment": ["Capricorn"],        "fall": "Scorpio"},
    "Mercury": {"domicile": ["Gemini", "Virgo"],   "exalt": "Virgo",      "detriment": ["Sagittarius", "Pisces"], "fall": "Pisces"},
    "Venus":   {"domicile": ["Taurus", "Libra"],   "exalt": "Pisces",     "detriment": ["Aries", "Scorpio"], "fall": "Virgo"},
    "Mars":    {"domicile": ["Aries", "Scorpio"],  "exalt": "Capricorn",  "detriment": ["Taurus", "Libra"],  "fall": "Cancer"},
    "Jupiter": {"domicile": ["Sagittarius", "Pisces"], "exalt": "Cancer", "detriment": ["Gemini", "Virgo"],  "fall": "Capricorn"},
    "Saturn":  {"domicile": ["Capricorn", "Aquarius"], "exalt": "Libra",  "detriment": ["Cancer", "Leo"],    "fall": "Aries"},
}

_DIGNITY_LABEL = {"domicile": "入庙", "exalt": "入旺", "detriment": "失势", "fall": "陷落"}

# 用于元素/模式统计的主要行星列表
_MAIN_PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars",
                  "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}


def _get_dignity(planet_en: str, sign_en: str) -> str | None:
    """返回行星在该星座的尊贵状态标签，不在尊贵表中则返回 None。"""
    table = _DIGNITY.get(planet_en)
    if not table:
        return None
    if sign_en in table["domicile"]:
        return _DIGNITY_LABEL["domicile"]
    if sign_en == table.get("exalt"):
        return _DIGNITY_LABEL["exalt"]
    if sign_en == table.get("fall"):
        return _DIGNITY_LABEL["fall"]
    if sign_en in table.get("detriment", []):
        return _DIGNITY_LABEL["detriment"]
    return None


# ── 星盘摘要格式化 ────────────────────────────────────────────────

def format_chart_summary(chart_data: dict, max_aspects: int | None = None) -> str:
    """把 NatalChartResponse dict 转成可读文本，作为 LLM 上下文。"""
    lines = []

    # ── 基本信息 ──
    inp = chart_data.get("input_data", {})
    name = inp.get("name") or "此人"
    lines.append(f"【本命盘】姓名: {name}")
    lines.append(
        f"出生: {inp.get('year')}/{inp.get('month')}/{inp.get('day')} "
        f"{str(inp.get('hour', 0)).zfill(2)}:{str(inp.get('minute', 0)).zfill(2)}"
    )

    asc = chart_data.get("ascendant", {})
    mc  = chart_data.get("midheaven", {})
    asc_sign = asc.get("sign_original") or asc.get("sign", "")
    mc_sign  = mc.get("sign_original") or mc.get("sign", "")
    if asc_sign:
        lines.append(f"上升点: {asc_sign}  |  中天(MC): {mc_sign}")

    # ── 收集行星信息（供后续各模块使用）──
    planets_raw = chart_data.get("planets", {})
    # planet_en → {sign_en, house, retrograde}
    planet_info: dict[str, dict] = {}
    for _, p in planets_raw.items():
        pname = p.get("name_original") or p.get("name", "")
        sign  = p.get("sign_original") or p.get("sign", "")
        planet_info[pname] = {
            "sign": sign,
            "house": p.get("house"),
            "retrograde": p.get("retrograde", False),
        }

    # ── 行星位置与尊贵状态 ──
    lines.append("\n【行星位置与尊贵状态】")
    for pname, info in planet_info.items():
        sign_en = info["sign"]
        house   = info["house"]
        retro   = " (逆行)" if info["retrograde"] else ""
        dignity = _get_dignity(pname, sign_en)
        dignity_str = f" [{dignity}]" if dignity else ""
        lines.append(f"  {pname}: {sign_en}, 第{house}宫{retro}{dignity_str}")

    # ── 宫位主星 ──
    houses_raw = chart_data.get("houses", {})
    if houses_raw:
        lines.append("\n【宫位主星】")
        for _, h in sorted(houses_raw.items(), key=lambda x: x[1].get("number", 0) if isinstance(x[1], dict) else 0):
            if not isinstance(h, dict):
                continue
            hnum     = h.get("number")
            hsign    = h.get("sign_original") or h.get("sign", "")
            ruler_en = _SIGN_RULER.get(hsign, "?")
            ruler_pos = planet_info.get(ruler_en)
            if ruler_pos:
                retro = " 逆" if ruler_pos["retrograde"] else ""
                lines.append(
                    f"  第{hnum}宫({hsign}) → 主星: {ruler_en} "
                    f"[在{ruler_pos['sign']}·第{ruler_pos['house']}宫{retro}]"
                )
            else:
                lines.append(f"  第{hnum}宫({hsign}) → 主星: {ruler_en}")

    # ── 元素 / 模式分布 ──
    elem_count: dict[str, int] = {"火": 0, "土": 0, "风": 0, "水": 0}
    mode_count: dict[str, int] = {"开创": 0, "固定": 0, "变动": 0}
    angular_planets: list[str] = []
    house_buckets: dict[int, list[str]] = {}
    sign_buckets:  dict[str, list[str]] = {}

    for pname, info in planet_info.items():
        if pname not in _MAIN_PLANETS:
            continue
        sign_en = info["sign"]
        house   = info["house"]
        elem = _SIGN_ELEMENT.get(sign_en)
        mode = _SIGN_MODALITY.get(sign_en)
        if elem:
            elem_count[elem] += 1
        if mode:
            mode_count[mode] += 1
        if house in (1, 4, 7, 10):
            angular_planets.append(f"{pname}(第{house}宫)")
        # stellium tracking
        house_buckets.setdefault(house, []).append(pname)
        sign_buckets.setdefault(sign_en, []).append(pname)

    lines.append("\n【星盘特征】")
    elem_str = "  ".join(f"{k}{v}" for k, v in elem_count.items() if v > 0)
    mode_str = "  ".join(f"{k}{v}" for k, v in mode_count.items() if v > 0)
    lines.append(f"  元素分布: {elem_str}")
    lines.append(f"  模式分布: {mode_str}")

    if angular_planets:
        lines.append(f"  角宫行星: {', '.join(angular_planets)}")

    # Stellium：同宫或同星座 3+ 行星
    stelliums = []
    for house, ps in house_buckets.items():
        if len(ps) >= 3:
            stelliums.append(f"第{house}宫群星({'/'.join(ps)})")
    for sign, ps in sign_buckets.items():
        if len(ps) >= 3:
            stelliums.append(f"{sign}群星({'/'.join(ps)})")
    if stelliums:
        lines.append(f"  群星(Stellium): {'; '.join(stelliums)}")

    # ── 相位 ──
    aspects = chart_data.get("aspects", [])
    if aspects:
        shown = aspects[:max_aspects] if max_aspects else aspects
        truncated = max_aspects and len(aspects) > max_aspects
        lines.append(f"\n【相位列表】{'（仅显示最紧密的10条）' if truncated else ''}")
        for asp in shown:
            p1     = asp.get("p1_name_original") or asp.get("p1_name")
            p2     = asp.get("p2_name_original") or asp.get("p2_name")
            aspect = asp.get("aspect_original") or asp.get("aspect")
            orb    = asp.get("orbit", 0)
            lines.append(f"  {p1} {aspect} {p2} (容许度 {orb:.1f}°)")

    return "\n".join(lines)


# ── 多轮对话辅助 ──────────────────────────────────────────────────

def _build_contents(history: list[dict], current_prompt: str, summary: str = "") -> list:
    """
    将摘要 + 对话历史 + 当前 prompt 转成 Gemini multi-turn contents 格式。
    summary: 早期对话的压缩摘要（可为空）
    history: 最近几轮原始对话 [{role: "user"|"assistant", text: str}, ...]
    """
    contents = []
    if summary:
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=f"[早期对话摘要]\n{summary}")],
        ))
        contents.append(types.Content(
            role="model",
            parts=[types.Part(text="已了解早期对话内容，继续为您解答。")],
        ))
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["text"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=current_prompt)]))
    return contents


def summarize_messages(messages: list, chart_name: str = "") -> str:
    """将一组对话消息压缩成简洁的中文摘要。"""
    dialog = "\n".join(
        f"{'用户' if m.role == 'user' else 'AI'}：{m.text}"
        for m in messages
    )
    subject = f"（星盘主人：{chart_name}）" if chart_name else ""
    prompt = (
        f"以下是一段占星解读对话{subject}，"
        "请将其压缩为简洁摘要（不超过200字），"
        "保留用户问过的主要问题和AI给出的关键结论：\n\n"
        f"{dialog}\n\n请输出摘要："
    )
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return response.text


# ── 完整 RAG 流程 ─────────────────────────────────────────────────

def rag_query(query: str, k: int = 5) -> dict:
    """
    完整 RAG：检索 + 生成。

    返回:
    {
        "answer": str,
        "sources": [{text, source, score}, ...],
        "index_used": str   # "demo_index" 或 "faiss_index"
    }
    """
    _load()
    chunks = retrieve(query, k=k)
    answer = generate(query, chunks)

    return {
        "answer": answer,
        "sources": [
            {
                "text": c["text"],
                "source": c["source"],
                "score": c["score"],
            }
            for c in chunks
        ],
        "index_used": _index_source,
    }


_SYSTEM_PROMPT_UNIFIED = """你是一位执业25年的西方占星师，融合古典占星（尊贵/飞星/接纳）与现代心理占星（原型/动力）。

【分析方法论】
对任何星盘论断，严格遵循以下推理链：
1. 定位：行星 → 所在星座（能量底色）→ 所在宫位（显化领域）
2. 飞星：该宫主星飞入哪一宫？形成什么能量流向？
3. 相位网络：与哪些行星形成紧密相位（优先分析容许度 ≤3° 的）？这些相位如何修正该行星的表达？
4. 整合：以上要素如何共同指向一个具体的人生主题或行为模式？

【风格要求】
- 每个论断必须有明确的星盘依据（行星+星座+宫位+相位），不说无根据的话
- 用具体的生活场景举例，让非专业用户也能理解
- 不回避困难相位的真实含义，但要指出成长路径和转化可能
- 善于发现星盘中看似矛盾的配置之间的深层联系
- 如果两颗行星的能量彼此冲突，直接点明张力而非模糊化

【禁止事项】
- 禁止使用"你很有创造力""充满挑战""潜力无限"等空泛表述
- 禁止堆砌占星术语而不解释其实际影响
- 禁止对每颗行星给出孤立解读而忽略行星之间的相互作用
- 禁止编造星盘中不存在的配置

【参考资料使用】
若提供了参考书籍片段且与当前分析相关，可引用其观点作为佐证,但不需要在表述中明确指出引用了什么书籍以免破坏解析的流畅程度,
书籍片段是可选补充而非限制,但你应该尽量寻找参考片段中的作证,在保证你个人知识不受到影响的基础上利用参考片段进行知识增强。

用中文回答，语言自然流畅，像是面对面咨询而非教科书。"""


def _clean_source_name(raw: str) -> str:
    """提取书名关键部分，用于引用检测。"""
    name = raw.replace("[EN]", "").split("(")[0].strip().lstrip("_").rstrip("_")
    # 去掉文件扩展名
    name = re.sub(r'\.[a-z]{2,4}$', '', name)
    # camelCase → 空格分隔（如 WhatAreWinningTransits → What Are Winning Transits）
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    return name.strip()


_REFS_DELIMITER = "===引用概括==="

_REFS_INSTRUCTION = (
    "\n\n如引用了上述参考，请在正文末尾另起一行写 ===引用概括===，"
    "然后每行一条 [参考N] 一句简洁中文（20-40字）说明从该参考获取的核心观点，"
    "未引用的参考无需列出。"
)


def _parse_answer_with_refs(raw: str, num_chunks: int) -> tuple[str, dict]:
    """Split Gemini output on ===引用概括=== into (main_answer, {1-based index: summary_zh}).
    Returns (raw, {}) if delimiter is absent."""
    if _REFS_DELIMITER not in raw:
        return raw.strip(), {}
    main, _, refs_part = raw.partition(_REFS_DELIMITER)
    summaries: dict[int, str] = {}
    for line in refs_part.strip().split("\n"):
        m = re.match(r'\[参考(\d+)\]\s*(.+)', line.strip())
        if m:
            idx = int(m.group(1))
            if 1 <= idx <= num_chunks:
                summaries[idx] = m.group(2).strip()
    return main.strip(), summaries


def _detect_citations(answer: str, chunks: list[dict], summaries: dict = None) -> list[dict]:
    """
    检测 AI 回答中是否引用了各 chunk 的来源书名。
    策略1：书名中长度>2的英文词子串匹配。
    策略2：检测"参考{i}"模式（模型用参考编号引用的情况）。
    """
    answer_lower = answer.lower()
    result = []
    for i, c in enumerate(chunks, 1):
        name = _clean_source_name(c["source"])
        words = [w for w in name.replace("·", " ").split() if len(w) > 2]
        cited_by_name = any(w.lower() in answer_lower for w in words)
        cited_by_ref = f"参考{i}" in answer or f"参考 {i}" in answer
        cited = cited_by_name or cited_by_ref
        print(f"[Citation] {name!r} by_name={cited_by_name} by_ref={cited_by_ref}", flush=True)
        result.append({
            "source":     c["source"],
            "score":      round(c["score"], 3),
            "cited":      cited,
            "text":       c["text"],
            "summary_zh": (summaries or {}).get(i, ""),
        })
    return result


def _build_rag_section(chunks: list[dict]) -> str:
    """将检索到的书籍片段拼成 prompt 追加块（含引用概括指令）。chunks 为空时返回空串。"""
    if not chunks:
        return ""
    parts = [
        f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    ]
    return (
        "\n\n---\n以下是检索到的占星书籍片段，若与问题相关可引用作为佐证（请注明书名），不相关可忽略：\n\n"
        + "\n\n".join(parts)
        + _REFS_INSTRUCTION
    )


def rag_generate(query: str, prompt: str, *, k: int = 5, temperature: float = 0.5) -> tuple[str, list]:
    """
    通用 RAG 增强生成（所有业务模块的统一入口）：
      retrieve → _build_rag_section → Gemini 生成
      → _parse_answer_with_refs → _detect_citations
    返回 (answer, sources)
    """
    _load()
    chunks = retrieve(query, k=k)
    full_prompt = prompt + _build_rag_section(chunks)
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            temperature=temperature,
        ),
    )
    finish = response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN"
    if finish != "STOP":
        print(f"[RAG] rag_generate finish_reason={finish}")
    answer, summaries = _parse_answer_with_refs(response.text, len(chunks))
    sources = _detect_citations(answer, chunks, summaries)
    return answer, sources


def chat_with_chart(query: str, chart_data: dict, k: int = 5,
                    history: list[dict] = None, summary: str = "",
                    transit_context: dict = None) -> dict:
    """
    统一对话：AI 知识为主，RAG 书籍片段为可选佐证。
    使用 _build_rag_section 构建知识增强块，通过 _build_contents 注入对话历史。
    当传入 transit_context 时，prompt 额外注入当日行运摘要，回答聚焦当下。
    """
    _load()
    chunks = retrieve(query, k=k)
    chart_summary = format_chart_summary(chart_data)

    if transit_context:
        date = transit_context.get("date", "")
        overall = transit_context.get("overall", "")
        aspects = transit_context.get("aspects", [])
        aspect_lines = "\n".join(
            f"  · {a.get('transit_planet_zh', a.get('transit_planet', ''))} "
            f"{a.get('aspect', '')} "
            f"{a.get('natal_planet_zh', a.get('natal_planet', ''))}"
            f"（{a.get('tone', '')}）"
            + (f"：{a.get('analysis', '')[:80]}…" if a.get('analysis') else "")
            for a in aspects[:8]
        )
        base_prompt = f"""用户本命盘：

{chart_summary}

当前行运日期：{date}
活跃行运相位：
{aspect_lines}

整体行运综述：{overall[:400] if overall else '（无）'}

---
请结合以上本命盘与当日行运，回答用户问题：{query}"""
    else:
        base_prompt = f"""用户本命盘：

{chart_summary}

---
用户问题：{query}"""

    full_prompt = base_prompt + _build_rag_section(chunks)
    contents = _build_contents(history or [], full_prompt, summary=summary)
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            temperature=0.5,
        ),
    )

    finish = response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN"
    if finish != "STOP":
        print(f"[RAG] chat_with_chart finish_reason={finish} — output may be truncated")

    answer, summaries = _parse_answer_with_refs(response.text, len(chunks))
    sources = _detect_citations(answer, chunks, summaries)
    return {
        "answer":     answer,
        "sources":    sources,
        "index_used": _index_source,
        "model_used": get_last_model_used(),
    }


# ── 行运解读 ───────────────────────────────────────────────────────

def analyze_transits(
    natal_chart: dict,
    transit_aspects: list[dict],
    transit_planets: dict,
    transit_date: str,
) -> dict:
    """
    行运解读：分析行运-本命相位对当事人的影响。

    返回:
    {
        "answer": str,
        "sources": [{source, score, cited}, ...],
        "index_used": str
    }
    """
    _load()

    # 取最紧密的相位构造检索 query
    tight = sorted(transit_aspects, key=lambda a: a.get("orbit", 99))[:3]
    desc_parts = []
    for a in tight:
        is_tp1   = a.get("p1_owner") == "transit"
        t_planet = (a.get("p1_name_original") or a.get("p1_name", "")) if is_tp1 \
                   else (a.get("p2_name_original") or a.get("p2_name", ""))
        n_planet = (a.get("p2_name_original") or a.get("p2_name", "")) if is_tp1 \
                   else (a.get("p1_name_original") or a.get("p1_name", ""))
        aspect   = a.get("aspect_original") or a.get("aspect", "")
        desc_parts.append(f"{t_planet} {aspect} natal {n_planet}")
    query = "transit " + ", ".join(desc_parts) if desc_parts else "transit aspects interpretation"

    # 本命盘摘要（保留行星位置+宫位主星，仅截断相位列表以控制 prompt 大小）
    chart_summary = format_chart_summary(natal_chart, max_aspects=10) if natal_chart else "（无本命盘数据）"

    # 行运行星位置
    planet_lines = []
    for _, p in transit_planets.items():
        pname = p.get("name_original") or p.get("name", "")
        sign  = p.get("sign_original") or p.get("sign", "")
        retro = " ℞" if p.get("retrograde") else ""
        planet_lines.append(f"  {pname}: {sign}{retro}")

    # 行运相位列表（按容许度排序）
    sorted_aspects = sorted(transit_aspects, key=lambda a: a.get("orbit", 99))
    aspect_lines = []
    for a in sorted_aspects:
        is_tp1   = a.get("p1_owner") == "transit"
        t_planet = (a.get("p1_name_original") or a.get("p1_name", "")) if is_tp1 \
                   else (a.get("p2_name_original") or a.get("p2_name", ""))
        n_planet = (a.get("p2_name_original") or a.get("p2_name", "")) if is_tp1 \
                   else (a.get("p1_name_original") or a.get("p1_name", ""))
        aspect   = a.get("aspect_original") or a.get("aspect", "")
        orb      = a.get("orbit", 0)
        applying = "入相" if a.get("applying") else "出相"
        t_retro  = " (逆行)" if (a.get("p1_retrograde") if is_tp1 else a.get("p2_retrograde")) else ""
        aspect_lines.append(
            f"  行运{t_planet}{t_retro} {aspect} 本命{n_planet}"
            f" (容许度{orb:.1f}° {applying})"
        )

    prompt = f"""行运日期：{transit_date}

{chart_summary}

【行运行星位置】
{chr(10).join(planet_lines) or '（无数据）'}

【行运-本命相位】（按容许度排序）
{chr(10).join(aspect_lines) or '（无相位）'}

---
请根据以上数据，对当日行运给出综合解读：
1. 整体能量与基调
2. 重点相位的具体影响（优先分析容许度≤2°的相位）
3. 机遇与挑战
4. 建议关注的事项"""

    answer, sources = rag_generate(query, prompt)
    return {
        "answer":     answer,
        "sources":    sources,
        "index_used": _index_source,
    }


# ── 活跃行运完整分析（per-transit DB 缓存）────────────────────────

def analyze_active_transits_full(
    natal_chart: dict,
    active_transits: list[dict],
    query_date: str,
    chart_id: int = 0,
    force_refresh: bool = False,
) -> dict:
    """
    per-transit DB 缓存的 Gemini 行运分析。
    - 未缓存/已过期的行运 → 调用 AI
    - 已缓存的行运 → 直接从 DB 读取
    - overall：有新行运则重新生成；否则从 DB 读取（按行运集合 hash 缓存）

    每条 aspect 返回：key, analysis, tone, themes (list), is_new (bool)
    """
    import hashlib
    from .db import (
        db_get_transit_cache, db_save_transit_cache,
        db_get_overall_cache, db_save_overall_cache,
    )

    if not active_transits:
        return {"aspects": [], "overall": "当前没有在容许度内的活跃行运相位。"}

    # ── 1. 逐条检查 DB 缓存 ───────────────────────────────────────────
    cached_aspects: dict[str, dict] = {}
    new_transits: list[dict] = []

    for t in active_transits:
        if not force_refresh:
            row = db_get_transit_cache(chart_id, t["key"], query_date)
            if row:
                cached_aspects[t["key"]] = {
                    "key":      t["key"],
                    "analysis": row["analysis"],
                    "tone":     row["tone"],
                    "themes":   json.loads(row["themes"]),
                    "is_new":   False,
                }
                continue
        new_transits.append(t)

    # ── 2. 计算行运集合 hash（用于 overall 缓存）──────────────────────
    all_keys_sorted = sorted(t["key"] for t in active_transits)
    set_hash = hashlib.md5("|".join(all_keys_sorted).encode()).hexdigest()[:12]

    # ── 3. 全部命中缓存时检查 overall ────────────────────────────────
    if not new_transits and not force_refresh:
        overall = db_get_overall_cache(chart_id, set_hash)
        if overall:
            aspects = [cached_aspects[t["key"]] for t in active_transits]
            return {"aspects": aspects, "overall": overall}
        # overall 未缓存 → 继续调用 AI（仅生成 overall）

    # ── 4. RAG 检索 ───────────────────────────────────────────────────
    _load()
    rag_query_parts = [
        f"transit {t['transit_planet_zh']} {t['aspect']} {t['natal_planet_zh']}"
        for t in sorted(active_transits, key=lambda x: -x.get("priority", 0))[:3]
    ]
    rag_query = ", ".join(rag_query_parts) if rag_query_parts else "transit aspects interpretation"
    rag_chunks = retrieve(rag_query, k=5)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = (
            "\n\n【参考书籍片段（可选）】\n"
            "以下占星书籍内容可作为分析佐证，若引用请在 source_refs 中按编号注明中文概括：\n\n"
            + "\n\n".join(parts)
        )

    # ── 5. 构建 prompt ────────────────────────────────────────────────
    chart_summary = format_chart_summary(natal_chart, max_aspects=10)

    def _line(i, t):
        orb_dir    = "入相" if t["applying"] else "出相"
        retro_note = f"（含逆行·{t['pass_count']} 次精确）" if t.get("retrograde_cycle") else ""
        return (
            f"{i}. key={t['key']}  [分类:{t.get('category','')} 优先级:{t.get('priority',0)}/14]\n"
            f"   行运 {t['transit_planet_zh']} {t['aspect']} 本命 {t['natal_planet_zh']}\n"
            f"   容许度：{t['current_orb']}°/{t.get('effective_orb','?')}°上限，{orb_dir}\n"
            f"   时段：{t['start_date']} 至 {t['end_date']}{retro_note}"
        )

    all_block = "\n\n".join(_line(i, t) for i, t in enumerate(active_transits, 1))

    source_refs_schema = (
        '"source_refs": {"<参考编号>": "<20-40字中文概括>"}  // 仅填写实际引用的编号，未引用可省略或留空'
    )

    if new_transits:
        new_block = "\n\n".join(_line(i, t) for i, t in enumerate(new_transits, 1))
        prompt = f"""你是一位经验丰富的职业占星师，精通西方占星学的行运分析。

{chart_summary}

━━━ 当前所有活跃行运（{query_date}，供整体分析参考） ━━━

{all_block}

━━━ 以下行运需要新的逐相位解读 ━━━

{new_block}{rag_context}

【分析要求】

**对"需要新解读"的每条行运**（约 150-250 字/条）：
- 结合本命盘中该行星的星座、宫位
- 说明具体影响的生活领域
- 若为逆行周期，点明三次过境节奏
- 给出 tone（顺势/挑战/转化 之一）和 themes（从"事业、感情、家庭、财务、健康、自我成长、人际关系、创意、精神"中选 1-3 个）

**整体行运综述**（约 300-400 字，基于所有活跃行运）：
- 开头先点出当前阶段主要影响的人生命题（1-2 句）
- 识别主题叠加（多个相位指向同一领域则标注"已获多重星象确认"）
- 给出具体行动建议
- 语言自然，避免机械罗列

JSON 格式返回（aspects 只包含"需要新解读"的行运）：
{{
  "aspects": [
    {{
      "key": "<与上方 key 完全一致>",
      "analysis": "<150-250字解读>",
      "tone": "<顺势|挑战|转化>",
      "themes": ["<主题1>", "<主题2>"]
    }}
  ],
  "overall": "<整体综述>",
  {source_refs_schema}
}}
"""
    else:
        # 全部命中缓存，只需生成 overall
        prompt = f"""你是一位经验丰富的职业占星师，精通西方占星学的行运分析。

{chart_summary}

━━━ 当前所有活跃行运（{query_date}） ━━━

{all_block}{rag_context}

请提供整体行运综述（约 300-400 字）：
- 开头先点出当前阶段主要影响的人生命题（1-2 句）
- 识别主题叠加（多个相位指向同一领域则标注"已获多重星象确认"）
- 给出具体行动建议
- 语言自然，避免机械罗列

JSON 格式返回：
{{"overall": "<整体综述>", {source_refs_schema}}}
"""

    # ── 6. 调用 Gemini ────────────────────────────────────────────────
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.5,
        ),
    )

    finish = response.candidates[0].finish_reason if response.candidates else None
    if finish and str(finish) != "STOP":
        print(f"[RAG] analyze_active_transits_full finish_reason={finish}")

    try:
        ai_result = _parse_json(response.text)
    except Exception as e:
        print(f"[RAG] JSON parse error: {e}")
        ai_result = {"aspects": [], "overall": response.text}

    # ── 7. 构建 RAG sources ───────────────────────────────────────────
    source_refs = ai_result.get("source_refs", {})
    rag_sources = []
    for i, c in enumerate(rag_chunks, 1):
        summary_zh = source_refs.get(str(i), "")
        rag_sources.append({
            "source":     c["source"],
            "score":      round(c["score"], 3),
            "cited":      bool(summary_zh),
            "text":       c["text"],
            "summary_zh": summary_zh,
        })

    # ── 8. 写入 DB 缓存 ───────────────────────────────────────────────
    new_map: dict[str, dict] = {}
    for a in ai_result.get("aspects", []):
        key = a.get("key", "")
        if not key:
            continue
        new_map[key] = a
        for t in new_transits:
            if t["key"] == key:
                db_save_transit_cache(
                    chart_id, key,
                    a.get("analysis", ""),
                    a.get("tone", ""),
                    json.dumps(a.get("themes", []), ensure_ascii=False),
                    t["end_date"],
                )
                break

    overall = ai_result.get("overall", "")
    if overall:
        db_save_overall_cache(chart_id, set_hash, overall)

    # ── 9. 合并返回 ───────────────────────────────────────────────────
    all_aspects = []
    for t in active_transits:
        key = t["key"]
        if key in new_map:
            a = new_map[key]
            all_aspects.append({
                "key":      key,
                "analysis": a.get("analysis", ""),
                "tone":     a.get("tone", ""),
                "themes":   a.get("themes", []),
                "is_new":   True,
            })
        elif key in cached_aspects:
            all_aspects.append(cached_aspects[key])
        else:
            all_aspects.append({"key": key, "analysis": "", "tone": "", "themes": [], "is_new": True})

    return {
        "aspects":     all_aspects,
        "overall":     overall,
        "sources":     rag_sources,
        "index_used":  _index_source,
    }


# ── 出生时间校对解读 ───────────────────────────────────────────────

_EVENT_TYPE_ZH = {
    'marriage':    '结婚',
    'divorce':     '离婚',
    'career_up':   '升职/事业突破',
    'career_down': '失业/事业受挫',
    'bereavement': '亲人离世',
    'illness':     '重大疾病',
    'relocation':  '搬迁',
    'accident':    '意外事故',
    'other':       '其他重大事件',
}


def analyze_rectification(
    natal_chart: dict,
    top3: list[dict],
    events: list[dict],
) -> dict:
    """
    AI解读出生时间校对结果：
    - 每个候选时间的上升星座特征与事件模式是否相符
    - 算法选出这些时间的占星依据
    - 推荐哪个候选，以及如何进一步验证
    """
    _load()

    chart_summary = format_chart_summary(natal_chart, max_aspects=5) if natal_chart else "（无本命盘数据）"

    event_lines = []
    for ev in events:
        etype = _EVENT_TYPE_ZH.get(ev.get('event_type', 'other'), ev.get('event_type', ''))
        w = int(ev.get('weight', 1))
        wlabel = ['', '一般', '重要', '非常重要'][min(w, 3)]
        m = ev.get('month')
        d = ev.get('day')
        date_str = (
            f"{ev['year']}/{m:02d}/{d:02d}" if m and d
            else f"{ev['year']}/{m:02d}/xx" if m
            else f"{ev['year']}/xx/xx"
        )
        event_lines.append(f"  {date_str}  {etype}（{wlabel}）")

    top3_lines = []
    for i, t in enumerate(top3, 1):
        asc = t.get('asc_sign', '')
        asc_str = f"，上升 {asc}" if asc else ''
        top3_lines.append(
            f"  候选{i}：{t['hour']:02d}:{t['minute']:02d}{asc_str}  评分 {t['score']}"
        )

    query = "birth time rectification ascendant secondary progressions life events"
    chunks = retrieve(query, k=3)
    rag_section = ""
    if chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        rag_section = (
            "\n\n---\n以下为相关占星书籍参考（可按需引用，注明书名）：\n\n"
            + "\n\n".join(parts)
        )

    candidates_list = ",\n".join(
        f'    {{"rank": {i}, "reason": "..."}}'
        for i in range(1, len(top3) + 1)
    )

    prompt = f"""出生时间校对结果：

{chart_summary}

用户提供的重大人生事件：
{chr(10).join(event_lines)}

算法评分 Top3 候选出生时间（rank 1 为算法评分最高）：
{chr(10).join(top3_lines)}

---
分析要求：
- 对每个候选时间（rank 1/2/3），在 reason 字段中单独分析：该上升星座的性格特征、哪些宫位或角点在用户事件日期被行运激活、与事件模式的吻合或不吻合之处（100-150字）
- 每个 reason 只分析自身对应的候选，不提及其他候选
- overall 给出综合推荐与验证建议（150-200字）
- ai_recommended_rank：根据你的占星理论分析，哪个候选最符合用户的人生事件模式？填写该候选的 rank 编号（1、2 或 3）

返回 JSON：
{{
  "candidates": [
{candidates_list}
  ],
  "overall": "...",
  "ai_recommended_rank": 1
}}{rag_section}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            response_mime_type="application/json",
            temperature=0.5,
        ),
    )

    print(f"[rectify] raw response ({len(response.text)} chars): {response.text[:300]}")
    try:
        parsed = _parse_json(response.text)
    except Exception as e:
        print(f"[rectify] JSON parse error: {e}")
        parsed = {"candidates": [], "overall": response.text}

    ai_rank = parsed.get("ai_recommended_rank")
    try:
        ai_rank = int(ai_rank)
        if ai_rank not in range(1, len(top3) + 1):
            ai_rank = None
    except (TypeError, ValueError):
        ai_rank = None
    print(f"[rectify] candidates: {len(parsed.get('candidates', []))}, overall len: {len(parsed.get('overall', ''))}, ai_recommended_rank: {ai_rank}")
    sources = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in chunks]
    return {
        "candidates": parsed.get("candidates", []),
        "overall": parsed.get("overall", ""),
        "ai_recommended_rank": ai_rank,
        "sources": sources,
    }


# ── 上升星座性格问卷生成 ─────────────────────────────────────────

def generate_asc_quiz(asc_signs: list[str]) -> dict:
    """
    根据 Top3 的上升星座动态生成 5 道鉴别性选择题。
    返回: {"questions": [...], "sources": [...]}
    """
    _load()
    signs_str = "、".join(asc_signs)

    rag_chunks = retrieve(f"上升星座性格特征外貌体态 {signs_str}", k=3)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = "\n\n【参考书籍片段（可用于增强题目描述的准确性）】\n" + "\n\n".join(parts) + "\n\n"

    prompt = f"""你是一位专业占星师，需要设计一套用于区分以下三种上升星座的性格/外貌选择题：{signs_str}
{rag_context}

请生成5道选择题，每道题4个选项（A/B/C/D），从以下5个维度各出1题：
1. 外貌与体态特征
2. 他人对你的第一印象
3. 面对压力或冲突时的本能反应
4. 日常行为与做事风格
5. 最能描述你早年经历的模式

要求：
- 选项必须能有效区分这3个上升星座
- 描述具体生动，不直接提及星座名称
- 每个选项标注它最符合哪个/哪些上升星座（用英文名，如 Aries）
- 可以有一个"都不太符合"选项，signs 为空数组

以JSON格式返回（只返回JSON，不要其他文字）：
{{
  "questions": [
    {{
      "id": "q1",
      "text": "题目",
      "options": [
        {{"id": "a", "text": "选项描述", "signs": ["Aries"]}},
        {{"id": "b", "text": "选项描述", "signs": ["Taurus"]}},
        {{"id": "c", "text": "选项描述", "signs": ["Gemini"]}},
        {{"id": "d", "text": "以上都不太符合", "signs": []}}
      ]
    }}
  ]
}}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.6,
        ),
    )
    sources = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in rag_chunks]
    try:
        data = _parse_json(response.text)
        return {"questions": data.get("questions", []), "sources": sources}
    except Exception:
        return {"questions": [], "sources": sources}


# ── 生命主题置信度评分 ───────────────────────────────────────────

def calc_confidence(
    candidate: dict,
    birth_year: int, birth_month: int, birth_day: int,
    lat: float, lng: float, tz_str: str,
    theme_answers: list[dict],
) -> dict:
    """
    根据生命主题问卷答案，评估候选出生时间的置信度。
    返回: {score: 0-100, label: "高/中/低", analysis: str}
    """
    _load()

    h, m = candidate["hour"], candidate["minute"]
    try:
        from kerykeion import AstrologicalSubject
        subj = AstrologicalSubject(
            "conf", birth_year, birth_month, birth_day,
            h, m, lng=lng, lat=lat, tz_str=tz_str,
        )
        natal_data = {
            "asc_sign": candidate.get("asc_sign", ""),
            "sun_sign": subj.sun.sign,
            "moon_sign": subj.moon.sign,
            "mc_sign": subj.tenth_house.sign,
            "stelliums": [],
        }
        # 简单统计各宫的行星数（找聚集宫位）
        house_count = {}
        for attr in ['sun','moon','mercury','venus','mars','jupiter','saturn','uranus','neptune','pluto']:
            if hasattr(subj, attr):
                p = getattr(subj, attr)
                if p:
                    house_count[p.house] = house_count.get(p.house, 0) + 1
        for house, cnt in house_count.items():
            if cnt >= 3:
                natal_data["stelliums"].append(f"{house}宫{cnt}星")
    except Exception:
        natal_data = {"asc_sign": candidate.get("asc_sign", ""), "error": "chart calc failed"}

    answers_text = "\n".join(
        f"Q{i+1}（{a['question']}）→ {a['answer']}" for i, a in enumerate(theme_answers)
    )

    asc_sign = natal_data.get('asc_sign', '')
    rag_chunks = retrieve(f"birth time rectification ascendant life themes {asc_sign}", k=3)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = "\n\n【参考书籍片段（供评估时参考）】\n" + "\n\n".join(parts) + "\n\n"

    prompt = f"""候选出生时间：{h:02d}:{m:02d}，上升星座：{asc_sign}
太阳星座：{natal_data.get('sun_sign','')}，月亮星座：{natal_data.get('moon_sign','')}，天顶：{natal_data.get('mc_sign','')}
宫位聚集：{natal_data.get('stelliums', []) or '无明显聚集'}

用户生命主题问卷回答：
{answers_text}
{rag_context}
请综合评估以上出生时间与用户生命主题的匹配程度，给出：
1. 置信度分数（0-100整数）
2. 置信度标签（高 ≥70 / 中 40-69 / 低 <40）
3. 简短分析（150字以内）：哪些宫位/行星配置与回答吻合，哪些存在出入

以JSON返回（只返回JSON）：
{{"score": 75, "label": "中", "analysis": "..."}}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    sources = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in rag_chunks]
    try:
        result = _parse_json(response.text)
        result["sources"] = sources
        return result
    except Exception:
        return {"score": 0, "label": "低", "analysis": response.text, "sources": sources}


# ── 本命盘行星逐一解读 ────────────────────────────────────────────

_SKIP_PLANETS = {'true_node', 'true_lilith', 'true_south_node'}

_SIGN_ELEMENT = {
    'Aries': '火', 'Leo': '火', 'Sagittarius': '火',
    'Taurus': '土', 'Virgo': '土', 'Capricorn': '土',
    'Gemini': '风', 'Libra': '风', 'Aquarius': '风',
    'Cancer': '水', 'Scorpio': '水', 'Pisces': '水',
}
_SIGN_MODE = {
    'Aries': '本始', 'Cancer': '本始', 'Libra': '本始', 'Capricorn': '本始',
    'Taurus': '固定', 'Leo': '固定', 'Scorpio': '固定', 'Aquarius': '固定',
    'Gemini': '变动', 'Virgo': '变动', 'Sagittarius': '变动', 'Pisces': '变动',
}
_CORE_PLANETS = {'sun', 'moon', 'mercury', 'venus', 'mars',
                 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'}


def _compute_chart_facts(natal_chart: dict) -> list[str]:
    """从星盘数据中用规则提取确定性事实标签，供 AI prompt 使用。"""
    planets = natal_chart.get('planets', {})
    aspects = natal_chart.get('aspects', [])

    sign_planets: dict[str, list] = {}   # 各星座包含的行星名（中文）
    house_planets: dict[int, list] = {}  # 各宫位包含的行星名（中文）
    elem_count = {'火': 0, '土': 0, '风': 0, '水': 0}
    mode_count = {'本始': 0, '固定': 0, '变动': 0}
    retro_names = []

    for key, p in planets.items():
        sign_raw = p.get('sign_original') or p.get('sign', '')             # 英文，用于 SIGN_ELEMENT/SIGN_MODE 查表
        sign_zh = translate_sign(sign_raw, 'zh') if sign_raw else sign_raw  # 中文带"座"，如"天蝎座"
        house = p.get('house') or 0
        name_raw = p.get('name_original') or p.get('name', key)
        name_zh = translate_planet(name_raw, 'zh') if name_raw else name_raw
        if key in _CORE_PLANETS:
            sign_planets.setdefault(sign_zh, []).append(name_zh)
            if house:
                house_planets.setdefault(house, []).append(name_zh)
            if sign_raw in _SIGN_ELEMENT:
                elem_count[_SIGN_ELEMENT[sign_raw]] += 1
            if sign_raw in _SIGN_MODE:
                mode_count[_SIGN_MODE[sign_raw]] += 1
        if p.get('retrograde') and key in _CORE_PLANETS:
            retro_names.append(name_zh)

    facts = []

    # 星座群星（含具体行星名；sign_zh 已含"座"，直接嵌入括号内）
    for s, planets_list in sign_planets.items():
        if len(planets_list) >= 3:
            planet_str = '·'.join(planets_list)
            facts.append(f"群星{s}（{planet_str}）")

    # 宫位强势（含具体行星名）
    for h, planets_list in house_planets.items():
        if len(planets_list) >= 3:
            planet_str = '·'.join(planets_list)
            facts.append(f"第{h}宫强势（{planet_str}）")

    # 元素主导
    dom_elem = max(elem_count, key=elem_count.get)
    if elem_count[dom_elem] >= 4:
        facts.append(f"多{dom_elem}象行星（{elem_count[dom_elem]}颗）")

    # 模式主导
    dom_mode = max(mode_count, key=mode_count.get)
    if mode_count[dom_mode] >= 4:
        facts.append(f"多{dom_mode}星（{mode_count[dom_mode]}颗）")

    # 逆行
    if retro_names:
        facts.append(f"逆行行星：{'、'.join(retro_names)}")

    # 相位格局检测
    trine_pairs: set[tuple] = set()
    opp_pairs: list[tuple] = []
    sq_map: dict[str, set] = {}  # planet → set of planets it squares

    for a in aspects:
        asp = (a.get('aspect_original') or a.get('aspect', '')).lower()
        orb = a.get('orbit', 99)
        p1, p2 = a.get('p1_name', ''), a.get('p2_name', '')
        if not p1 or not p2:
            continue
        if 'trine' in asp and orb < 8:
            trine_pairs.add((p1, p2))
            trine_pairs.add((p2, p1))
        if 'opposition' in asp and orb < 8:
            opp_pairs.append((p1, p2))
        if 'square' in asp and orb < 8:
            sq_map.setdefault(p1, set()).add(p2)
            sq_map.setdefault(p2, set()).add(p1)

    # 大三角：三颗行星互相形成三分相
    tp_list = list({p for pair in trine_pairs for p in pair})
    gt_found = False
    for i in range(len(tp_list)):
        for j in range(i + 1, len(tp_list)):
            for k in range(j + 1, len(tp_list)):
                a, b, c = tp_list[i], tp_list[j], tp_list[k]
                if (a, b) in trine_pairs and (a, c) in trine_pairs and (b, c) in trine_pairs:
                    facts.append(f"大三角格局（{a}·{b}·{c}）")
                    gt_found = True
                    break
            if gt_found:
                break
        if gt_found:
            break

    # T三角：一对对冲 + 一颗行星分别四分两端
    for (a, b) in opp_pairs:
        sq_a = sq_map.get(a, set())
        sq_b = sq_map.get(b, set())
        apex_set = sq_a & sq_b
        if apex_set:
            apex = next(iter(apex_set))
            facts.append(f"T三角格局（顶点：{apex}，对冲：{a}·{b}）")
            break

    return facts


# ── Solar Return Rule Engine ───────────────────────────────────────────────
# 权重三档：强=3 / 中=2 / 弱=1，避免细粒度数字导致伪精度排名翻转

_SR_ASC_NATAL_HOUSE_WEIGHTS = {
    # 角宫(1/4/7/10) → 强(3)；续宫(2/6/9/12) → 中(2)；变宫次要 → 弱(1)
    "1":  {"self_identity": 3},
    "2":  {"money_resources": 2},
    "3":  {"learning_expansion": 1},
    "4":  {"home_family": 3},
    "5":  {"relationships": 1},
    "6":  {"health_routine": 2},
    "7":  {"relationships": 3},
    "8":  {"inner_healing": 2, "money_resources": 1},
    "9":  {"learning_expansion": 2},
    "10": {"career_public": 3},
    "11": {"career_public": 1, "learning_expansion": 1},
    "12": {"inner_healing": 2},
}

_SR_SUN_HOUSE_WEIGHTS = {
    # 角宫/6/9/12 → 强(3)；2/8 → 中(2)；3/5/11 → 弱(1)
    "1":  {"self_identity": 3},
    "2":  {"money_resources": 2},
    "3":  {"learning_expansion": 1},
    "4":  {"home_family": 3},
    "5":  {"relationships": 1, "self_identity": 1},
    "6":  {"health_routine": 3},
    "7":  {"relationships": 3},
    "8":  {"inner_healing": 2, "money_resources": 1},
    "9":  {"learning_expansion": 3},
    "10": {"career_public": 3},
    "11": {"learning_expansion": 1, "relationships": 1},
    "12": {"inner_healing": 3},
}

_SR_MOON_HOUSE_WEIGHTS = {
    # 整体降一档，最高 2（月亮为情绪指向，信号强度次于太阳）
    "1":  {"self_identity": 2},
    "2":  {"money_resources": 1},
    "3":  {"learning_expansion": 1},
    "4":  {"home_family": 2},
    "5":  {"relationships": 1},
    "6":  {"health_routine": 2},
    "7":  {"relationships": 2},
    "8":  {"inner_healing": 2},
    "9":  {"learning_expansion": 2},
    "10": {"career_public": 2},
    "11": {"relationships": 1},
    "12": {"inner_healing": 2},
}

_SR_PLANET_HOUSE_WEIGHTS = {
    # 木/土为中(2)，金/火为弱(1)
    "jupiter": {
        "2": {"money_resources": 2}, "4": {"home_family": 2},
        "7": {"relationships": 2},   "9": {"learning_expansion": 2},
        "10": {"career_public": 2},  "11": {"learning_expansion": 1},
    },
    "saturn": {
        "2": {"money_resources": 2}, "6": {"health_routine": 2},
        "7": {"relationships": 1},   "10": {"career_public": 2},
        "12": {"inner_healing": 2},
    },
    "venus": {
        "5": {"relationships": 1},   "7": {"relationships": 2},
        "2": {"money_resources": 1},
    },
    "mars": {
        "1": {"self_identity": 1},   "6": {"health_routine": 1},
        "10": {"career_public": 1},  "8": {"inner_healing": 1},
    },
}

_SR_ANGULAR_THEMES = {"1": "self_identity", "4": "home_family", "7": "relationships", "10": "career_public"}

_SR_TRADITIONAL_RULER = {
    "Aries": "mars",    "Taurus": "venus",   "Gemini": "mercury",
    "Cancer": "moon",   "Leo": "sun",        "Virgo": "mercury",
    "Libra": "venus",   "Scorpio": "mars",   "Sagittarius": "jupiter",
    "Capricorn": "saturn", "Aquarius": "saturn", "Pisces": "jupiter",
}

_SR_THEME_NAMES_ZH = {
    "self_identity": "自我身份",
    "relationships": "人际关系",
    "career_public": "事业公众",
    "home_family": "家庭居所",
    "money_resources": "财务资源",
    "health_routine": "健康日常",
    "learning_expansion": "学习扩展",
    "inner_healing": "内在疗愈",
}


def _sr_find_natal_house(asc_degree: float, natal_houses: dict) -> str | None:
    """Return the natal house number (str) that contains asc_degree."""
    house_cusps = []
    for num in range(1, 13):
        h = natal_houses.get(str(num), {})
        lon = h.get("longitude")
        if lon is not None:
            house_cusps.append((num, float(lon)))
    if not house_cusps:
        return None
    house_cusps.sort(key=lambda x: x[1])
    asc = float(asc_degree) % 360
    for i, (num, cusp) in enumerate(house_cusps):
        next_cusp = house_cusps[(i + 1) % 12][1]
        if next_cusp <= cusp:  # wraps around 0°
            if asc >= cusp or asc < next_cusp:
                return str(num)
        else:
            if cusp <= asc < next_cusp:
                return str(num)
    return str(house_cusps[0][0])


def _compute_sr_theme_scores(
    sr_planets: dict,
    sr_houses: dict,
    natal_planets: dict,
    natal_houses: dict,
    sr_asc_degree: float,
) -> dict:
    """
    6-layer SR theme scoring engine.
    Returns core_facts, theme_scores (8 themes), top_themes, modifiers, confidence.
    """
    scores: dict[str, float] = {
        "self_identity": 0, "relationships": 0, "career_public": 0,
        "home_family": 0, "money_resources": 0, "health_routine": 0,
        "learning_expansion": 0, "inner_healing": 0,
    }
    facts: list[str] = []
    modifiers: list[str] = []

    def add(weights: dict, label: str):
        for theme, pts in weights.items():
            scores[theme] = scores.get(theme, 0) + pts
        facts.append(label)

    # ── Layer 1: SR ASC in natal house ────────────────────────────────────
    natal_house = _sr_find_natal_house(sr_asc_degree, natal_houses)
    if natal_house and natal_house in _SR_ASC_NATAL_HOUSE_WEIGHTS:
        add(_SR_ASC_NATAL_HOUSE_WEIGHTS[natal_house], f"SR上升落本命第{natal_house}宫")

    # ── Layer 2: SR Sun house ──────────────────────────────────────────────
    sun = sr_planets.get("sun", {})
    sun_house = str(sun.get("house", "")) if sun.get("house") else ""
    if sun_house in _SR_SUN_HOUSE_WEIGHTS:
        add(_SR_SUN_HOUSE_WEIGHTS[sun_house], f"SR太阳落第{sun_house}宫")

    # ── Layer 3: SR Moon house ─────────────────────────────────────────────
    moon = sr_planets.get("moon", {})
    moon_house = str(moon.get("house", "")) if moon.get("house") else ""
    if moon_house in _SR_MOON_HOUSE_WEIGHTS:
        add(_SR_MOON_HOUSE_WEIGHTS[moon_house], f"SR月亮落第{moon_house}宫")

    # ── Layer 4: SR ASC ruler house (+1 per theme, +1 bonus if angular) ───
    asc_sign_raw = sr_houses.get("1", {}).get("sign_original") or sr_houses.get("1", {}).get("sign")
    if asc_sign_raw:
        ruler_key = _SR_TRADITIONAL_RULER.get(asc_sign_raw)
        if ruler_key and ruler_key in sr_planets:
            ruler_planet = sr_planets[ruler_key]
            ruler_house = str(ruler_planet.get("house", ""))
            if ruler_house in _SR_SUN_HOUSE_WEIGHTS:
                for theme in _SR_SUN_HOUSE_WEIGHTS[ruler_house]:
                    scores[theme] = scores.get(theme, 0) + 1
                if ruler_house in _SR_ANGULAR_THEMES:
                    scores[_SR_ANGULAR_THEMES[ruler_house]] = scores.get(_SR_ANGULAR_THEMES[ruler_house], 0) + 1
                facts.append(f"上升守护星{translate_planet(ruler_key, 'zh')}落SR第{ruler_house}宫")

    # ── Layer 5: Angular house emphasis ───────────────────────────────────
    house_planet_count: dict[str, int] = {}
    for key, p in sr_planets.items():
        h = str(p.get("house", ""))
        if h in _SR_ANGULAR_THEMES:
            house_planet_count[h] = house_planet_count.get(h, 0) + 1
    for h, cnt in house_planet_count.items():
        if cnt >= 2:
            theme = _SR_ANGULAR_THEMES[h]
            bonus = min(cnt - 1, 2)  # 2颗+1, 3颗+2
            scores[theme] = scores.get(theme, 0) + bonus
            facts.append(f"第{h}宫角宫强调（{cnt}颗行星）")

    # ── Layer 6: Jupiter / Saturn / Venus / Mars house ─────────────────────
    for planet_key, house_map in _SR_PLANET_HOUSE_WEIGHTS.items():
        p = sr_planets.get(planet_key, {})
        p_house = str(p.get("house", ""))
        if p_house in house_map:
            add(house_map[p_house], f"{translate_planet(planet_key, 'zh')}落SR第{p_house}宫")

    # ── Modifier aspects (orb ≤ 3°) ────────────────────────────────────────
    _ASPECT_MODIFIERS = [
        ("sun", "saturn",  [0, 90, 180], "restructuring"),
        ("sun", "jupiter", [0, 90, 180], "expansion"),
        ("sun", "uranus",  [0],          "change"),
        ("sun", "neptune", [0],          "dissolution"),
        ("sun", "pluto",   [0],          "transformation"),
        ("moon", "saturn", [0],          "emotional_weight"),
    ]

    for p1_key, p2_key, aspect_angles, label in _ASPECT_MODIFIERS:
        p1_lon = float(sr_planets.get(p1_key, {}).get("longitude", -999))
        p2_lon = float(sr_planets.get(p2_key, {}).get("longitude", -999))
        if p1_lon < 0 or p2_lon < 0:
            continue
        diff = abs(p1_lon - p2_lon) % 360
        if diff > 180:
            diff = 360 - diff
        for angle in aspect_angles:
            if abs(diff - angle) <= 3.0:
                if label not in modifiers:
                    modifiers.append(label)
                break

    # ── Compile output ─────────────────────────────────────────────────────
    top_themes = sorted(
        [{"theme": k, "score": int(v)} for k, v in scores.items()],
        key=lambda x: -x["score"]
    )[:3]

    # confidence: top theme's share of total × 2, capped at 1.0
    # e.g. top=50% of total → 1.0; uniform(12.5% each) → 0.25
    total = sum(scores.values()) or 1
    top_score = max(scores.values())
    confidence = round(min(top_score / total * 2, 1.0), 2)

    return {
        "core_facts": facts,
        "theme_scores": {k: int(v) for k, v in scores.items()},
        "top_themes": top_themes,
        "modifiers": modifiers,
        "confidence": confidence,
    }


def analyze_solar_return(
    sr_planets: dict,
    sr_houses: dict,
    natal_chart_data: dict,
    sr_asc_degree: float,
    return_year: int,
    language: str = "zh",
) -> dict:
    """
    Generate AI annual report for a Solar Return chart.
    Returns: keywords, summary, themes (top3), domains (8), suggestions, sources,
             model_used, theme_scores.
    """
    natal_planets = natal_chart_data.get("planets", {})
    natal_houses  = natal_chart_data.get("houses", {})

    analysis = _compute_sr_theme_scores(
        sr_planets=sr_planets,
        sr_houses=sr_houses,
        natal_planets=natal_planets,
        natal_houses=natal_houses,
        sr_asc_degree=sr_asc_degree,
    )

    top3 = analysis["top_themes"][:3]
    top3_zh = "、".join(_SR_THEME_NAMES_ZH.get(t["theme"], t["theme"]) for t in top3)
    modifiers_zh = "、".join(analysis["modifiers"]) if analysis["modifiers"] else "无特别修正"
    facts_text = "\n".join(f"- {f}" for f in analysis["core_facts"])
    scores_text = "\n".join(
        f"  {_SR_THEME_NAMES_ZH.get(k, k)}: {v}"
        for k, v in sorted(analysis["theme_scores"].items(), key=lambda x: -x[1])
    )

    rag_query = (
        f"solar return {return_year} annual themes {top3_zh} "
        f"house interpretation yearly forecast"
    )

    prompt = f"""请根据以下太阳回归年度分析数据，生成一份面向普通用户的{return_year}年度报告（中文）。

【规则引擎分析结果】
确定性事实：
{facts_text}

年度主题得分（从高到低）：
{scores_text}

修正标签：{modifiers_zh}
置信度：{analysis["confidence"]}

【输出要求】
请严格按照以下 JSON 结构返回（不要在 JSON 外加任何解释文字）：
{{
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "summary": "100-150字的年度核心主轴段落",
  "themes": [
    {{
      "theme": "home_family",
      "score": 79,
      "name_zh": "家庭居所",
      "analysis": "80-120字分析",
      "evidence": ["依据1", "依据2"]
    }},
    ... (top 3)
  ],
  "domains": {{
    "career_public": "50-80字",
    "relationships": "50-80字",
    "money_resources": "50-80字",
    "home_family": "50-80字",
    "health_routine": "50-80字",
    "learning_expansion": "50-80字",
    "inner_healing": "50-80字",
    "self_identity": "50-80字"
  }},
  "suggestions": ["建议1（具体行动）", "建议2", "建议3"],
  "source_refs": {{"<参考编号>": "<20字中文概括>"}}
}}

规则：
- 只使用输入中给出的信息，不要杜撰相位或宫位
- 使用"倾向、重点、可能、容易"等概率性表达，不做绝对预言
- themes 必须按得分从高到低排列，且与 theme_scores 一致
- 对健康、财务等敏感主题避免确定性建议
"""

    answer, sources = rag_generate(rag_query, prompt, k=5, temperature=0.35)
    model_used = get_last_model_used()

    try:
        parsed = _parse_json(answer)
    except Exception:
        parsed = {}

    themes_out = parsed.get("themes", [])
    if not themes_out:
        themes_out = [
            {
                "theme": t["theme"],
                "score": t["score"],
                "name_zh": _SR_THEME_NAMES_ZH.get(t["theme"], t["theme"]),
                "analysis": "",
                "evidence": [],
            }
            for t in top3
        ]

    return {
        "keywords":     parsed.get("keywords", []),
        "summary":      parsed.get("summary", answer[:200] if answer else ""),
        "themes":       themes_out,
        "domains":      parsed.get("domains", {}),
        "suggestions":  parsed.get("suggestions", []),
        "sources":      sources,
        "model_used":   model_used,
        "theme_scores": analysis["theme_scores"],
    }


def analyze_planets(natal_chart: dict, language: str = 'zh') -> dict:
    """
    为本命盘每颗行星生成简洁解读（单次 Gemini 调用，返回全部结果）。
    返回: {"sun": "解读文字", "moon": "...", ...}
    """
    planets = natal_chart.get('planets', {})
    asc = natal_chart.get('ascendant', {})
    mc  = natal_chart.get('midheaven', {})
    asc_sign_raw = asc.get('sign_original') or asc.get('sign', '')
    mc_sign_raw  = mc.get('sign_original')  or mc.get('sign', '')
    asc_sign = translate_sign(asc_sign_raw, 'zh') if asc_sign_raw else ''
    mc_sign  = translate_sign(mc_sign_raw,  'zh') if mc_sign_raw  else ''

    # 推算 DSC/IC 对点星座
    _OPPOSITE = {
        'Aries':'Libra','Taurus':'Scorpio','Gemini':'Sagittarius','Cancer':'Capricorn',
        'Leo':'Aquarius','Virgo':'Pisces','Libra':'Aries','Scorpio':'Taurus',
        'Sagittarius':'Gemini','Capricorn':'Cancer','Aquarius':'Leo','Pisces':'Virgo',
    }
    dsc_sign_raw = _OPPOSITE.get(asc_sign_raw, '')
    ic_sign_raw  = _OPPOSITE.get(mc_sign_raw,  '')
    dsc_sign = translate_sign(dsc_sign_raw, 'zh') if dsc_sign_raw else ''
    ic_sign  = translate_sign(ic_sign_raw,  'zh') if ic_sign_raw  else ''

    # 行星列表（含逆行标注），同时记录 key 顺序用于生成 JSON 模板
    lines = []
    planet_keys = []
    for key, p in planets.items():
        if key in _SKIP_PLANETS:
            continue
        name_raw = p.get('name_original') or p.get('name', key)
        sign_raw = p.get('sign_original') or p.get('sign', '')
        name = translate_planet(name_raw, 'zh') if name_raw else name_raw
        sign = translate_sign(sign_raw, 'zh') if sign_raw else sign_raw
        house = p.get('house', '')
        retro = '（逆行）' if p.get('retrograde') else ''
        lines.append(f"{name}（key: {key}）: {sign} 第{house}宫{retro}")
        planet_keys.append(key)
    planet_list = '\n'.join(lines)
    # 动态生成 JSON 模板，确保 AI 为每颗行星（包括小行星）返回分析
    planet_entries = ',\n  '.join(f'"{k}": "..."' for k in planet_keys)
    json_template = (
        '{\n  ' + planet_entries + ',\n'
        '  "asc": "...",\n'
        '  "dsc": "...",\n'
        '  "mc": "...",\n'
        '  "ic": "...",\n'
        '  "overall": {\n'
        '    "tags": ["...", "..."],\n'
        '    "summary": "...",\n'
        '    "career": "...",\n'
        '    "love": "...",\n'
        '    "wealth": "...",\n'
        '    "health": "..."\n'
        '  },\n'
        '  "source_refs": {"<参考编号>": "<20-40字中文概括>"}  // 仅填写实际引用的编号\n'
        '}'
    )

    # 宫位守星表（第N宫所在星座 → 该星座守护星）
    houses = natal_chart.get('houses', {})
    house_lines = []
    for num in range(1, 13):
        h = houses.get(str(num), {})
        hsign_raw = h.get('sign_original') or h.get('sign', '')
        if hsign_raw:
            hsign = translate_sign(hsign_raw, 'zh')
            house_lines.append(f"第{num}宫: {hsign}")
    house_summary = '\n'.join(house_lines)

    # 主要相位摘要（合/对/四分/三分/六分，容许度<6°）
    aspects = natal_chart.get('aspects', [])
    aspect_lines = []
    for a in aspects:
        p1 = a.get('p1_name', '')
        p2 = a.get('p2_name', '')
        asp = a.get('aspect', '')
        orbit = a.get('orbit', 99)
        if orbit < 6 and p1 and p2 and asp:
            aspect_lines.append(f"{p1} {asp} {p2}（容许度{round(orbit,1)}°）")
    aspect_summary = '\n'.join(aspect_lines) if aspect_lines else '（无数据）'

    # 规则提取确定性事实
    chart_facts = _compute_chart_facts(natal_chart)
    facts_section = ''
    if chart_facts:
        facts_section = '\n\n【规则检测到的确定性事实（必须体现在 tags 中）】\n' + '\n'.join(f'- {f}' for f in chart_facts)

    # RAG 检索（JSON 模式用 source_refs 字段标注引用）
    _load()
    try:
        rag_chunks = retrieve(f"行星星座宫位解读 {asc_sign}上升", k=3)
    except Exception:
        rag_chunks = []
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = (
            "\n\n---\n参考书籍片段（仅供内部参考，不得在行星解读文字中引用英文原文或标注书名；"
            "若引用，请只在 source_refs 字段中填写编号和中文概括，不得在解读正文中出现任何英文或引用格式）：\n\n"
            + "\n\n".join(parts)
        )

    # 四交点信息（供 prompt 使用）
    angles_section = ""
    if asc_sign or mc_sign:
        angles_section = f"""
四交点轴线：
上升 ASC（第1宫起点）: {asc_sign}  |  下降 DSC（第7宫起点）: {dsc_sign}
天顶 MC（第10宫起点）: {mc_sign}   |  天底 IC（第4宫起点）: {ic_sign}
"""

    prompt = f"""请为以下本命盘行星位置分别生成占星解读，并在最后给出四交点解读和综合概述。

上升星座：{asc_sign}
{angles_section}
行星位置：
{planet_list}

宫位起点星座（用于推算飞星/守护星落位）：
{house_summary}

主要相位：
{aspect_summary}{facts_section}

分析要求——每颗行星必须同时结合以下维度：
1. 【星座特质】该行星在此星座的表达方式与能量底色
2. 【宫位主题】该宫位代表的人生领域，以及行星如何在此显化
3. 【飞星影响】该行星所在星座的守护星落在哪个宫位，形成何种能量流向；若行星本身也是某宫主星，一并说明其飞入他宫的含义
4. 若有重要相位（容许度<4°），简述其对该行星能量的加强或挑战
5. 逆行行星需特别说明内化/重新审视的主题

每颗行星 80-120 字，风格专业简洁，直接指向对当事人的影响。

四交点分析要求（asc/dsc/mc/ic）：
- asc（上升 {asc_sign}）：外在气质、第一印象、身体与外貌特征，80-120 字
- dsc（下降 {dsc_sign}）：理想伴侣特质、人际关系模式与吸引规律，80-120 字
- mc（天顶 {mc_sign}）：职业方向、社会形象与人生志向，80-120 字
- ic（天底 {ic_sign}）：家庭底色、童年环境与内心安全感来源，80-120 字

综合概述（overall）为结构化对象，包含以下字段：
- tags: 字符串数组，**必须优先使用上方【确定性事实】中列出的标签**，再补充 AI 判断的其他特征（如「命主星逆行」「日月形成对冲」等），共 3-6 个
- summary: 主要人生命题、核心潜力与成长方向，100-150 字
- career: 学业与事业领域分析，列出支持该结论的具体行星/宫位依据，80-100 字
- love: 恋爱与家庭领域分析，附占星依据，80-100 字
- wealth: 财富与物质领域分析，附占星依据，80-100 字
- health: 健康与身体领域分析，附占星依据，60-80 字

**必须为以上列出的每一颗行星（包括凯龙、北交点、南交点、莉莉丝等小行星）生成解读，不得遗漏任何一个。**
**必须为四交点（asc/dsc/mc/ic）各生成解读，不得遗漏。**

**严格禁止**在任何行星解读文字（JSON 值）中出现：英文引用原文、书名标注、「参考《...》」格式、或任何引用注记。行星解读必须是纯中文分析文字。引用信息只能通过 source_refs 字段以中文概括表达。

以 JSON 格式返回（严格使用以下 key，每个 key 对应一段解读文字，overall 为嵌套对象；source_refs 仅填写实际引用的参考编号）：
{json_template}{rag_context}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )
    model_used = get_last_model_used()
    try:
        parsed = _parse_json(response.text)
    except Exception as e:
        print(f"[planets] JSON parse error: {e}")
        return {"analyses": {}, "sources": [], "model_used": model_used}

    print(f"[planets] parsed keys: {list(parsed.keys())}", flush=True)
    # Detect any planet/angle keys Gemini silently dropped (output token pressure)
    _angle_sign_map = {'asc': asc_sign, 'dsc': dsc_sign, 'mc': mc_sign, 'ic': ic_sign}
    angle_keys = [k for k, s in _angle_sign_map.items() if s]
    missing_keys = [k for k in planet_keys + angle_keys if k not in parsed]
    if missing_keys:
        print(f"[planets] Gemini dropped {missing_keys}, retrying", flush=True)
        missing_planet_lines = [l for l in lines if any(f"(key: {k})" in l for k in missing_keys)]
        _angle_desc = {
            'asc': f"上升 ASC（key: asc）: {asc_sign} — 外在气质、第一印象、外貌特征",
            'dsc': f"下降 DSC（key: dsc）: {dsc_sign} — 理想伴侣特质、人际关系模式",
            'mc':  f"天顶 MC（key: mc）: {mc_sign} — 职业方向、社会形象与志向",
            'ic':  f"天底 IC（key: ic）: {ic_sign} — 家庭底色、童年环境与安全感来源",
        }
        missing_angle_lines = [_angle_desc[k] for k in missing_keys if k in _angle_desc]
        all_missing_lines = missing_planet_lines + missing_angle_lines
        missing_entries = ',\n  '.join(f'"{k}": "..."' for k in missing_keys)
        retry_prompt = f"""请为以下本命盘位置生成占星解读，仅针对列出的条目。

上升星座：{asc_sign}

位置列表：
{chr(10).join(all_missing_lines)}

宫位起点星座：
{house_summary}

主要相位：
{aspect_summary}

每项 80-120 字，专业简洁。以 JSON 格式返回：
{{\n  {missing_entries}\n}}"""
        try:
            retry_resp = client.models.generate_content(
                model=GENERATE_MODEL,
                contents=retry_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT_UNIFIED,
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            retry_parsed = _parse_json(retry_resp.text)
            parsed.update(retry_parsed)
        except Exception as e:
            print(f"[planets] retry for missing planets failed: {e}", flush=True)

    source_refs = parsed.pop("source_refs", {}) or {}
    rag_sources = []
    for i, c in enumerate(rag_chunks, 1):
        summary_zh = source_refs.get(str(i), "")
        rag_sources.append({
            "source":     c["source"],
            "score":      round(c["score"], 3),
            "cited":      bool(summary_zh),
            "text":       c["text"],
            "summary_zh": summary_zh,
        })
    return {"analyses": parsed, "sources": rag_sources, "model_used": model_used}


# ── 合盘解读 ───────────────────────────────────────────────────────

_SYNASTRY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "texture_labels": {
            "type": "array",
            "items": {"type": "string", "enum": [
                "激情拉扯", "灵魂安栖", "头脑风暴", "相互成就",
                "命运纠缠", "温暖守护", "创意共振", "对立成长"
            ]},
            "minItems": 1,
            "maxItems": 2,
        },
        "texture_reasoning": {"type": "string"},
        "relationship_rankings": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": [
                        "浪漫伴侣", "深度友谊", "心智共鸣",
                        "职场搭档", "师徒引路", "创意灵感", "宿命牵绊"
                    ]},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "key_aspects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                    "summary": {"type": "string"},
                },
                "required": ["type", "score", "key_aspects", "summary"],
            },
        },
        "dimensions": {
            "type": "object",
            "properties": {
                "attraction":    {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score", "analysis"]},
                "emotional":     {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score", "analysis"]},
                "communication": {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score", "analysis"]},
                "stability":     {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score", "analysis"]},
                "growth":        {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score", "analysis"]},
                "friction":      {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score", "analysis"]},
            },
            "required": ["attraction", "emotional", "communication", "stability", "growth", "friction"],
        },
    },
    "required": ["texture_labels", "texture_reasoning", "relationship_rankings", "dimensions"],
}


def analyze_synastry(
    chart1_name: str,
    chart2_name: str,
    chart1_planets: dict,
    chart2_planets: dict,
    aspects: list[dict],
) -> dict:
    """
    合盘 AI 解读：Gemini 从完整星盘数据推理关系质感、关系类型 Top3 及六维分析。
    返回结构化 dict，字段由 response_schema 强制。
    """
    _load()

    # ── 1. 构建行星列表 ──────────────────────────────────────────────
    # chart1_planets values are plain dicts (deserialised from JSON), use .get() not getattr()
    def _planet_list(planets_dict: dict) -> list[dict]:
        result = []
        for name, p in planets_dict.items():
            try:
                p_dict = p if isinstance(p, dict) else vars(p)
                longitude = float(p_dict.get('longitude', 0))
                sign_raw = p_dict.get('sign', '')
                result.append({
                    "planet": translate_planet(name, 'zh') if name else name,
                    "sign": translate_sign(sign_raw, 'zh') if sign_raw else sign_raw,
                    "degree": round(longitude % 30, 1),
                    "house": p_dict.get('house', None),
                })
            except Exception as e:
                print(f"[synastry] skipped planet {name}: {e}", flush=True)
        return result

    planets1 = _planet_list(chart1_planets)
    planets2 = _planet_list(chart2_planets)

    # ── 2. 构建富化相位列表（补充星座信息）────────────────────────────
    def _sign(p) -> str:
        raw = p.get('sign', '') if isinstance(p, dict) else getattr(p, 'sign', '')
        return translate_sign(raw, 'zh') if raw else raw

    sign_lookup1 = {name: _sign(p) for name, p in chart1_planets.items()}
    sign_lookup2 = {name: _sign(p) for name, p in chart2_planets.items()}

    enriched_aspects = []
    for a in aspects:
        p1_name = a.get('p1_name', a.get('p1', ''))
        p2_name = a.get('p2_name', a.get('p2', ''))
        enriched_aspects.append({
            "p1": p1_name,
            "p1_sign": sign_lookup1.get(p1_name, '') or sign_lookup2.get(p1_name, ''),
            "aspect": a.get('aspect', ''),
            "p2": p2_name,
            "p2_sign": sign_lookup2.get(p2_name, '') or sign_lookup1.get(p2_name, ''),
            "orb": round(float(a.get('orbit', a.get('orb', 0))), 1),
            "double_whammy": bool(a.get('double_whammy', False)),
        })

    # ── 3. RAG 检索 ───────────────────────────────────────────────────
    rag_query = f"synastry relationship compatibility aspects {' '.join(a.get('aspect','') for a in aspects[:5])}"
    rag_chunks = retrieve(rag_query, k=4)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = "\n\n【参考书籍片段（可参考相位解读，无需在 JSON 中注明）】\n" + "\n\n".join(parts) + "\n\n"

    # ── 4. 构建 Gemini payload ───────────────────────────────────────
    context = {
        "person1": {"name": chart1_name, "planets": planets1},
        "person2": {"name": chart2_name, "planets": planets2},
        "cross_aspects": enriched_aspects,
    }

    prompt = f"""你是专业占星师，请根据以下两人的完整星盘数据进行合盘分析。
{rag_context}

【数据】
{json.dumps(context, ensure_ascii=False, indent=2)}

【分析要求】
1. 识别1-2个关系质感标签（从给定列表中选择），并用一句话说明依据
2. 评估最可能自然形成的关系类型Top 3，给出0-100概率分，引用具体相位作为证据（最多3条），用2-3句话描述
3. 对六个维度各给出0-100分和分析，分析中必须引用具体行星相位，使用普通用户能理解的语言

注意：
- 概率分反映"这段关系的能量自然倾向"，不是主观建议
- 相位的星座背景很重要，请考虑星座特质对相位能量的调整
- double whammy（双向命中）相位的权重更高
- Top 3关系类型必须是三种不同的类型，不可重复
- 请用中文回答"""

    # ── 5. 调用 Gemini（强制 JSON schema）────────────────────────────
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_SYNASTRY_OUTPUT_SCHEMA,
            temperature=0.4,
        ),
    )
    model_used = get_last_model_used()

    try:
        result = _parse_json(response.text)
    except (json.JSONDecodeError, AttributeError) as e:
        raise RuntimeError(f"Gemini synastry schema parse failed: {e}\nRaw: {getattr(response, 'text', '')[:200]}")

    result["model_used"] = model_used
    result["sources"] = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in rag_chunks]
    return result
