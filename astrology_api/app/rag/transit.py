"""
app/rag/transit.py — 行运解读（单次 + 活跃行运完整缓存分析）
"""
import json
import hashlib

from google.genai import types

from .client import client, GENERATE_MODEL
from .retrieval import retrieve, _load, _parse_json, _index_source
from .prompts import _clean_source_name
from .chart_summary import format_chart_summary
from .chat import rag_generate
from .prompt_registry import PROMPTS as _PROMPTS


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

    planet_lines_str = chr(10).join(planet_lines) or '（无数据）'
    aspect_lines_str = chr(10).join(aspect_lines) or '（无相位）'
    _tmpl = _PROMPTS["transits_single"]["prompt_template"]
    prompt = _tmpl.format(
        transit_date=transit_date,
        chart_summary=chart_summary,
        planet_lines_str=planet_lines_str,
        aspect_lines_str=aspect_lines_str,
    )

    answer, sources = rag_generate(query, prompt)
    return {
        "answer":     answer,
        "sources":    sources,
        "index_used": _index_source,
    }


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
    from ..db import (
        db_get_transit_cache, db_save_transit_cache,
        db_get_overall_cache, db_save_overall_cache,
        db_delete_expired_transit_cache,
    )

    if not active_transits:
        return {"aspects": [], "overall": "当前没有在容许度内的活跃行运相位。"}

    # ── 0. 清理已过期的缓存条目 ──
    if chart_id:
        db_delete_expired_transit_cache(chart_id, query_date)

    # ── 1. 逐条检查 DB 缓存 ──
    cached_aspects: dict[str, dict] = {}
    new_transits: list[dict] = []

    for t in active_transits:
        if not force_refresh:
            cached = db_get_transit_cache(chart_id, t["key"], t["end_date"])
            if cached:
                cached_aspects[t["key"]] = {
                    "key":      t["key"],
                    "analysis": cached["analysis"],
                    "tone":     cached["tone"],
                    "themes":   json.loads(cached["themes_json"]) if cached.get("themes_json") else [],
                    "is_new":   False,
                }
                continue
        new_transits.append(t)

    # ── 2. 整体缓存键（所有行运 key 的有序集合 hash）──
    set_hash = hashlib.sha256(
        json.dumps(sorted(t["key"] for t in active_transits)).encode()
    ).hexdigest()[:16]

    # ── 3. 若没有新行运，检查 overall 缓存 ──
    if not new_transits:
        overall = db_get_overall_cache(chart_id, set_hash)
        if overall:
            aspects = [cached_aspects[t["key"]] for t in active_transits]
            return {"aspects": aspects, "overall": overall}
        # overall 未缓存 → 继续调用 AI（仅生成 overall）

    # ── 4. RAG 检索 ──
    _load()
    rag_query_parts = [
        f"transit {t['transit_planet_zh']} {t['aspect']} {t['natal_planet_zh']}"
        for t in sorted(active_transits, key=lambda x: -x.get("priority", 0))[:3]
    ]
    rag_query_str = ", ".join(rag_query_parts) if rag_query_parts else "transit aspects interpretation"
    rag_chunks = retrieve(rag_query_str, k=5)
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

    # ── 5. 构建 prompt ──
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
        _tmpl_new = _PROMPTS["transits_full_new"]["prompt_template"]
        prompt = _tmpl_new.format(
            chart_summary=chart_summary,
            query_date=query_date,
            all_block=all_block,
            new_block=new_block,
            rag_context=rag_context,
            source_refs_schema=source_refs_schema,
        )
    else:
        # 全部命中缓存，只需生成 overall
        _tmpl_sum = _PROMPTS["transits_full_summary"]["prompt_template"]
        prompt = _tmpl_sum.format(
            chart_summary=chart_summary,
            query_date=query_date,
            all_block=all_block,
            rag_context=rag_context,
            source_refs_schema=source_refs_schema,
        )

    # ── 6. 调用 Gemini ──
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

    # ── 7. 构建 RAG sources ──
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

    # ── 8. 写入 DB 缓存 ──
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

    # ── 9. 合并返回 ──
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
