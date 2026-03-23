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


# ── 星盘摘要格式化 ────────────────────────────────────────────────

def format_chart_summary(chart_data: dict) -> str:
    """把 NatalChartResponse dict 转成可读文本，作为 LLM 上下文。"""
    lines = []

    inp = chart_data.get("input_data", {})
    name = inp.get("name") or "此人"
    lines.append(f"【本命盘】姓名: {name}")
    lines.append(f"出生: {inp.get('year')}/{inp.get('month')}/{inp.get('day')} "
                 f"{str(inp.get('hour', 0)).zfill(2)}:{str(inp.get('minute', 0)).zfill(2)}")

    asc = chart_data.get("ascendant", {})
    mc  = chart_data.get("midheaven", {})
    if asc:
        lines.append(f"上升点: {asc.get('sign_original') or asc.get('sign')}")
    if mc:
        lines.append(f"中天(MC): {mc.get('sign_original') or mc.get('sign')}")

    lines.append("\n【行星位置】")
    for _, p in chart_data.get("planets", {}).items():
        name_en  = p.get("name_original") or p.get("name")
        sign_en  = p.get("sign_original") or p.get("sign")
        house    = p.get("house")
        retro    = " (逆行)" if p.get("retrograde") else ""
        lines.append(f"  {name_en}: {sign_en}, 第{house}宫{retro}")

    aspects = chart_data.get("aspects", [])
    if aspects:
        lines.append("\n【主要相位】")
        for asp in aspects[:15]:
            p1     = asp.get("p1_name_original") or asp.get("p1_name")
            p2     = asp.get("p2_name_original") or asp.get("p2_name")
            aspect = asp.get("aspect_original") or asp.get("aspect")
            orb    = asp.get("orbit", 0)
            lines.append(f"  {p1} {aspect} {p2} (容许度 {orb:.1f}°)")

    return "\n".join(lines)


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


def rag_query_with_chart(query: str, chart_data: dict, k: int = 5) -> dict:
    """带星盘上下文的 RAG：把星盘数据注入 prompt，再检索+生成。"""
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

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
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


def interpret_with_chart(query: str, chart_data: dict, k: int = 5) -> dict:
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

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
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
