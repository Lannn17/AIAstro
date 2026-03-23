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
    _load_index()
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
    _load_index()

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


# ── 活跃行运完整分析（单次 Gemini 调用）────────────────────────────

# 缓存：(chart_id, date_str) → {"aspects": [...], "overall": "..."}
_TRANSIT_FULL_AI_CACHE: dict[tuple, dict] = {}


def analyze_active_transits_full(
    natal_chart: dict,
    active_transits: list[dict],
    query_date: str,
    chart_id: int = 0,
    force_refresh: bool = False,
) -> dict:
    """
    一次 Gemini 调用，为所有活跃行运生成：
    - 每个相位的独立解读（per-aspect analysis）
    - 整体行运综述（overall report）

    返回：{"aspects": [{"key": str, "analysis": str}, ...], "overall": str}
    """
    cache_key = (chart_id, query_date)
    if not force_refresh and cache_key in _TRANSIT_FULL_AI_CACHE:
        return _TRANSIT_FULL_AI_CACHE[cache_key]

    if not active_transits:
        return {"aspects": [], "overall": "当前没有在容许度内的活跃行运相位。"}

    chart_summary = format_chart_summary(natal_chart, max_aspects=10)

    # 构建行运列表说明，包含优先级分类和容许度信息
    transit_lines = []
    for i, t in enumerate(active_transits, 1):
        orb_dir   = "入相" if t["applying"] else "出相"
        retro_note = f"（含逆行·{t['pass_count']} 次精确）" if t.get("retrograde_cycle") else ""
        category  = t.get("category", "")
        priority  = t.get("priority", 0)
        transit_lines.append(
            f"{i}. key={t['key']}  [分类:{category} 优先级:{priority}/14]\n"
            f"   行运 {t['transit_planet_zh']}（{t['transit_planet']}）"
            f" {t['aspect']} "
            f"本命 {t['natal_planet_zh']}（{t['natal_planet']}）\n"
            f"   容许度：{t['current_orb']}°/{t.get('effective_orb', '?')}°上限，{orb_dir}\n"
            f"   时段：{t['start_date']} 至 {t['end_date']}{retro_note}，精确日：{t['exact_date']}"
        )

    transit_block = "\n\n".join(transit_lines)

    prompt = f"""你是一位经验丰富的职业占星师，精通西方占星学的行运分析。

{chart_summary}

━━━ 当前活跃行运（{query_date}，按优先级排序，已预筛选） ━━━

{transit_block}

【分析要求】

**逐相位解读**（每个约 150-250 字）：
- 结合本命盘中该行星的星座、宫位和尊贵状态
- 说明此行运影响的具体生活领域（事业/感情/内在成长/健康等）
- 若为逆行周期，点明三次过境的主题演进节奏
- 优先级高（≥10）的相位应给予更深入的解析

**叠加验证（Method 3）**：
- 检查是否有多个相位同时指向同一生活主题（如两个以上相位都涉及事业/人际/内在转化）
- 若发现主题叠加，在整体综述中重点标注该主题"已获多重星象确认"
- 没有叠加时，综述聚焦最高优先级的 1-2 个相位

**整体行运综述**（约 300-400 字）：
- 识别当前星象的核心主题（1-3个）
- 指出叠加确认的主题（若有）
- 给出具体的时间节点建议（精确日前后如何行动）
- 语言自然流畅，避免机械罗列

以 JSON 格式返回：
{{
  "aspects": [
    {{"key": "<与上方 key 完全一致>", "analysis": "<该行运的详细解读>"}},
    ...
  ],
  "overall": "<整体行运综述，含主题叠加分析>"
}}
"""

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
        result = json.loads(response.text)
    except Exception as e:
        print(f"[RAG] JSON parse error: {e}")
        result = {"aspects": [], "overall": response.text}

    _TRANSIT_FULL_AI_CACHE[cache_key] = result
    return result


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
    _load_index()

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

    try:
        parsed = json.loads(response.text)
    except Exception:
        parsed = {"candidates": [], "overall": response.text}

    return {"candidates": parsed.get("candidates", []), "overall": parsed.get("overall", "")}
