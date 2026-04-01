"""
app/rag/chat.py — 对话、RAG 生成入口（rag_generate, chat_with_chart, rag_query）
"""
from google.genai import types

from .client import client, GENERATE_MODEL, get_last_model_used
from .retrieval import retrieve, _load, _index_source
from .prompts import (
    _SYSTEM_PROMPT_UNIFIED,
    _build_rag_section,
    _parse_answer_with_refs,
    _detect_citations,
)
from .chart_summary import format_chart_summary


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
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            temperature=0.4,
        ),
    )
    return response.text


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


def rag_query(query: str, k: int = 5) -> dict:
    """
    完整 RAG：检索 + 生成。

    返回:
    {
        "answer": str,
        "sources": [{text, source, score}, ...],
        "index_used": str
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
