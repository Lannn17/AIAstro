"""
app/rag.py — RAG 核心模块

流程：query → Gemini embedding → FAISS检索 → Gemini生成答案

优先加载 demo_index，若不存在则加载完整 faiss_index。
"""

import os
import json
import pathlib
import numpy as np
import faiss
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("请在 .env 中设置 GOOGLE_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)

EMBED_MODEL    = "gemini-embedding-001"
GENERATE_MODEL = "gemini-3.1-flash-lite-preview"

# 索引优先级: e5_index → minilm_index → gemini_demo_index → gemini_index
_BASE     = pathlib.Path(__file__).parent.parent / "data"
_E5_DIR   = _BASE / "e5_index"
_MINILM_DIR = _BASE / "minilm_index"
_DEMO_DIR = _BASE / "gemini_demo_index"
_FULL_DIR = _BASE / "gemini_index"


# ── 懒加载（首次查询时初始化）────────────────────────────────────

_index: faiss.Index | None = None
_chunks: list[dict] | None = None
_index_source: str = ""


_local_model = None        # SentenceTransformer or None (Gemini)
_query_prefix: str = ""    # "query: " for e5_index, "" for all others


def _pick_index_dir():
    for d in [_E5_DIR, _MINILM_DIR, _DEMO_DIR, _FULL_DIR]:
        if (d / "index.faiss").exists():
            return d
    raise RuntimeError(
        "找不到 FAISS 索引文件。请先运行 build_e5_index.py / build_minilm_index.py / build_gemini_index.py。"
    )


def _load_index():
    global _index, _chunks, _index_source, _local_model

    if _index is not None:
        return

    index_dir = _pick_index_dir()
    _index = faiss.read_index(str(index_dir / "index.faiss"))
    with open(index_dir / "chunks.json", encoding="utf-8") as f:
        _chunks = json.load(f)

    _index_source = index_dir.name

    # sentence-transformers 索引（e5 或 minilm）
    if index_dir in (_E5_DIR, _MINILM_DIR):
        from sentence_transformers import SentenceTransformer
        mi = json.loads((index_dir / "model_info.json").read_text())
        _local_model = SentenceTransformer(mi["model"])
        _query_prefix = mi.get("prefix", "")   # "query: " for e5, "" for minilm
        print(f"[RAG] using sentence-transformers: {mi['model']} (prefix='{_query_prefix}')")

    print(f"[RAG] index: {_index_source}, {_index.ntotal} vectors")


# ── Retrieval ─────────────────────────────────────────────────────

def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    向量检索，返回 top-k 相关 chunks。
    每条结果格式: {text, source, start, score}
    """
    _load_index()

    if _local_model is not None:
        # sentence-transformers (e5: prepend "query: ", minilm: no prefix)
        encoded = _query_prefix + query
        query_vec = _local_model.encode([encoded], convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
    else:
        # Gemini 嵌入
        response = client.models.embed_content(
            model=EMBED_MODEL,
            contents=[query],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        query_vec = np.array([response.embeddings[0].values], dtype=np.float32)
        faiss.normalize_L2(query_vec)

    scores, indices = _index.search(query_vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = dict(_chunks[idx])
        chunk["score"] = round(float(score), 4)
        results.append(chunk)

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

def format_chart_summary(chart_data: dict) -> str:
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

    # ── 相位（全部输出）──
    aspects = chart_data.get("aspects", [])
    if aspects:
        lines.append("\n【相位列表】")
        for asp in aspects:
            p1     = asp.get("p1_name_original") or asp.get("p1_name")
            p2     = asp.get("p2_name_original") or asp.get("p2_name")
            aspect = asp.get("aspect_original") or asp.get("aspect")
            orb    = asp.get("orbit", 0)
            lines.append(f"  {p1} {aspect} {p2} (容许度 {orb:.1f}°)")

    return "\n".join(lines)


# ── 多轮对话辅助 ──────────────────────────────────────────────────

def _build_contents(history: list[dict], current_prompt: str) -> list:
    """
    将对话历史 + 当前 prompt 转成 Gemini multi-turn contents 格式。
    history 格式: [{role: "user"|"assistant", text: str}, ...]
    """
    contents = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["text"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=current_prompt)]))
    return contents


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
    _load_index()
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


def rag_query_with_chart(query: str, chart_data: dict, k: int = 5, history: list[dict] = None) -> dict:
    """带星盘上下文的 RAG：把星盘数据注入 prompt，再检索+生成。支持多轮对话。"""
    _load_index()
    chunks = retrieve(query, k=k)
    chart_summary = format_chart_summary(chart_data)

    context_parts = []
    for i, c in enumerate(chunks, 1):
        source = c["source"].replace("[EN]", "").split("(")[0].strip()
        context_parts.append(f"[片段{i} · 来源: {source}]\n{c['text']}")
    context = "\n\n".join(context_parts)

    prompt = f"""以下是用户的本命盘信息：

{chart_summary}

---
以下是来自占星书籍的相关片段：

{context}

---
用户问题：{query}

请结合用户的本命盘数据和书籍片段，给出具体、有针对性的占星解读。"""

    contents = _build_contents(history or [], prompt)
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_RAG,
            temperature=0.4,
        ),
    )

    return {
        "answer": response.text,
        "sources": [
            {"text": c["text"], "source": c["source"], "score": c["score"]}
            for c in chunks
        ],
        "index_used": _index_source,
    }


# 相关性阈值：低于此分数的片段不纳入补充引用
_RELEVANCE_THRESHOLD = 0.3


def interpret_with_chart(query: str, chart_data: dict, k: int = 5, history: list[dict] = None) -> dict:
    """
    版本B — AI解读版：AI用自身知识主导解读，RAG片段作可选补充。
    若检索片段相关性低，不影响AI主体答案质量。
    """
    _load_index()
    chunks = retrieve(query, k=k)
    chart_summary = format_chart_summary(chart_data)

    # 过滤相关性足够高的片段
    relevant_chunks = [c for c in chunks if c["score"] >= _RELEVANCE_THRESHOLD]

    if relevant_chunks:
        context_parts = []
        for i, c in enumerate(relevant_chunks, 1):
            source = c["source"].replace("[EN]", "").split("(")[0].strip()
            context_parts.append(f"[参考{i} · {source}]\n{c['text']}")
        rag_section = "以下是来自占星书籍的参考片段（可作为佐证）：\n\n" + "\n\n".join(context_parts) + "\n\n---\n"
    else:
        rag_section = ""

    prompt = f"""用户本命盘：

{chart_summary}

---
{rag_section}用户问题：{query}

请基于你的占星学专业知识，结合本命盘数据给出深入解读。"""

    contents = _build_contents(history or [], prompt)
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_INTERPRET,
            temperature=0.5,
        ),
    )

    return {
        "answer": response.text,
        "sources": [
            {"text": c["text"], "source": c["source"], "score": c["score"]}
            for c in relevant_chunks
        ],
        "rag_used": len(relevant_chunks) > 0,
        "index_used": _index_source,
    }
