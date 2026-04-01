"""
app/rag/prompts.py — System prompt + RAG prompt 构建辅助
"""
import re

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


_REFS_DELIMITER = "===引用概括==="

_REFS_INSTRUCTION = (
    "\n\n如引用了上述参考，请在正文末尾另起一行写 ===引用概括===，"
    "然后每行一条 [参考N] 一句简洁中文（20-40字）说明从该参考获取的核心观点，"
    "未引用的参考无需列出。"
)


def _clean_source_name(raw: str) -> str:
    """提取书名关键部分，用于引用检测。"""
    name = raw.replace("[EN]", "").split("(")[0].strip().lstrip("_").rstrip("_")
    name = re.sub(r'\.[a-z]{2,4}$', '', name)
    # camelCase → 空格分隔（如 WhatAreWinningTransits → What Are Winning Transits）
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    return name.strip()


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
    策略2：检测"参考{i}"模式。
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
