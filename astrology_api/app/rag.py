"""
app/rag.py — RAG 核心模块

流程：query → fastembed(e5) → Qdrant检索 → Gemini生成答案
"""

import os
import re
import json
import numpy as np
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("请在 .env 中设置 GOOGLE_API_KEY")

QDRANT_URL     = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError("请在 .env 中设置 QDRANT_URL 和 QDRANT_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)

GENERATE_MODEL  = "gemini-3.1-flash-lite-preview"
COLLECTION_NAME = "astro_chunks"
E5_MODEL        = "intfloat/multilingual-e5-small"
E5_PREFIX       = "query: "


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


_SYSTEM_PROMPT_UNIFIED = """你是一位经验丰富的职业占星师，精通西方占星学。
请基于你深厚的专业知识，结合用户本命盘数据给出深入、具体的解读。
若提供的参考书籍片段与问题相关，可在解读中引用作为佐证并注明书名；
解读质量以你自身的占星学知识为主，书籍片段是可选补充而非限制。
用中文回答。"""


def _clean_source_name(raw: str) -> str:
    """提取书名关键部分，用于引用检测。"""
    return raw.replace("[EN]", "").split("(")[0].strip()


def _detect_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """
    检测 AI 回答中是否引用了各 chunk 的来源书名。
    用书名中长度>2的词做子串匹配，属启发式检测，非精确。
    """
    answer_lower = answer.lower()
    result = []
    for c in chunks:
        name = _clean_source_name(c["source"])
        words = [w for w in name.replace("·", " ").split() if len(w) > 2]
        cited = any(w.lower() in answer_lower for w in words)
        result.append({
            "source": c["source"],
            "score":  round(c["score"], 3),
            "cited":  cited,
        })
    return result


def chat_with_chart(query: str, chart_data: dict, k: int = 5,
                    history: list[dict] = None, summary: str = "") -> dict:
    """
    统一对话：AI 知识为主，RAG 书籍片段为可选佐证。
    prompt 顺序：星盘 → 问题 → 书籍参考（可选）
    始终返回来源及引用检测结果，供前端评估 RAG 质量。
    """
    _load()
    chunks = retrieve(query, k=k)
    chart_summary = format_chart_summary(chart_data)

    context_parts = []
    for i, c in enumerate(chunks, 1):
        name = _clean_source_name(c["source"])
        context_parts.append(f"[参考{i} · {name}]\n{c['text']}")
    rag_section = "\n\n".join(context_parts)

    prompt = f"""用户本命盘：

{chart_summary}

---
用户问题：{query}

---
以下是检索到的占星书籍片段，若与问题相关可引用作为佐证（请注明书名），不相关可忽略：

{rag_section}"""

    contents = _build_contents(history or [], prompt, summary=summary)
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

    sources = _detect_citations(response.text, chunks)
    return {
        "answer":     response.text,
        "sources":    sources,
        "index_used": _index_source,
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

    chunks = retrieve(query, k=5)

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

    # RAG 书籍参考
    rag_section = ""
    if chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        rag_section = (
            "\n\n---\n以下是检索到的占星书籍参考片段，若与当前行运相关可引用作为佐证"
            "（注明书名），不相关可忽略：\n\n"
            + "\n\n".join(parts)
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
4. 建议关注的事项{rag_section}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            temperature=0.5,
        ),
    )

    sources = _detect_citations(response.text, chunks) if chunks else []
    return {
        "answer":     response.text,
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

    # ── 4. 构建 prompt ────────────────────────────────────────────────
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

    if new_transits:
        new_block = "\n\n".join(_line(i, t) for i, t in enumerate(new_transits, 1))
        prompt = f"""你是一位经验丰富的职业占星师，精通西方占星学的行运分析。

{chart_summary}

━━━ 当前所有活跃行运（{query_date}，供整体分析参考） ━━━

{all_block}

━━━ 以下行运需要新的逐相位解读 ━━━

{new_block}

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
  "overall": "<整体综述>"
}}
"""
    else:
        # 全部命中缓存，只需生成 overall
        prompt = f"""你是一位经验丰富的职业占星师，精通西方占星学的行运分析。

{chart_summary}

━━━ 当前所有活跃行运（{query_date}） ━━━

{all_block}

请提供整体行运综述（约 300-400 字）：
- 开头先点出当前阶段主要影响的人生命题（1-2 句）
- 识别主题叠加（多个相位指向同一领域则标注"已获多重星象确认"）
- 给出具体行动建议
- 语言自然，避免机械罗列

JSON 格式返回：
{{"overall": "<整体综述>"}}
"""

    # ── 5. 调用 Gemini ────────────────────────────────────────────────
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

    # ── 6. 写入 DB 缓存 ───────────────────────────────────────────────
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

    # ── 7. 合并返回 ───────────────────────────────────────────────────
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

    return {"aspects": all_aspects, "overall": overall}


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
        event_lines.append(
            f"  {ev['year']}/{ev['month']:02d}/{ev['day']:02d}  {etype}（{wlabel}）"
        )

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

    prompt = f"""出生时间校对结果：

{chart_summary}

用户提供的重大人生事件：
{chr(10).join(event_lines)}

算法评分 Top3 候选出生时间：
{chr(10).join(top3_lines)}

---
请以 JSON 格式返回分析结果，结构如下：
{{
  "candidates": [
    {{
      "rank": 1,
      "reason": "候选1的具体占星理由：上升星座特征、哪些宫位或角点在事件日期被行运/推运激活、与用户事件模式的吻合度（100-150字）"
    }},
    {{
      "rank": 2,
      "reason": "候选2的具体占星理由（100-150字）"
    }},
    {{
      "rank": 3,
      "reason": "候选3的具体占星理由（100-150字）"
    }}
  ],
  "overall": "综合推荐与验证建议：明确指出最推荐哪个候选及原因，并给出用户可用其他事件进一步验证的方法（150-200字）"
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

    print(f"[rectify] candidates: {len(parsed.get('candidates', []))}, overall len: {len(parsed.get('overall', ''))}")
    return {"candidates": parsed.get("candidates", []), "overall": parsed.get("overall", "")}


# ── 上升星座性格问卷生成 ─────────────────────────────────────────

def generate_asc_quiz(asc_signs: list[str]) -> list[dict]:
    """
    根据 Top3 的上升星座动态生成 5 道鉴别性选择题。
    返回: [{id, text, options: [{id, text, signs: [...]}]}]
    """
    _load()
    signs_str = "、".join(asc_signs)
    prompt = f"""你是一位专业占星师，需要设计一套用于区分以下三种上升星座的性格/外貌选择题：{signs_str}

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
    try:
        data = _parse_json(response.text)
        return data.get("questions", [])
    except Exception:
        return []


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

    prompt = f"""候选出生时间：{h:02d}:{m:02d}，上升星座：{natal_data.get('asc_sign','')}
太阳星座：{natal_data.get('sun_sign','')}，月亮星座：{natal_data.get('moon_sign','')}，天顶：{natal_data.get('mc_sign','')}
宫位聚集：{natal_data.get('stelliums', []) or '无明显聚集'}

用户生命主题问卷回答：
{answers_text}

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
    try:
        return _parse_json(response.text)
    except Exception:
        return {"score": 0, "label": "低", "analysis": response.text}
