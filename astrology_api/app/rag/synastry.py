"""
app/rag/synastry.py — 合盘 AI 解读
"""
import json

from google.genai import types

from .client import client, GENERATE_MODEL, get_last_model_used
from .retrieval import retrieve, _load, _parse_json
from .prompts import _clean_source_name
from ..interpretations.translations import translate_planet, translate_sign

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

    # ── 1. 构建行星列表 ──
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
            except Exception:
                continue
        return result

    planets1 = _planet_list(chart1_planets)
    planets2 = _planet_list(chart2_planets)

    # ── 2. 构建相位列表（含星座背景）──
    sign_lookup1 = {
        (translate_planet(n, 'zh') if n else n): (translate_sign(p.get('sign','') if isinstance(p,dict) else getattr(p,'sign',''), 'zh'))
        for n, p in chart1_planets.items()
    }
    sign_lookup2 = {
        (translate_planet(n, 'zh') if n else n): (translate_sign(p.get('sign','') if isinstance(p,dict) else getattr(p,'sign',''), 'zh'))
        for n, p in chart2_planets.items()
    }

    enriched_aspects = []
    for a in aspects:
        p1_name = translate_planet(a.get('p1_name', ''), 'zh')
        p2_name = translate_planet(a.get('p2_name', ''), 'zh')
        enriched_aspects.append({
            "p1": p1_name,
            "p1_sign": sign_lookup1.get(p1_name, '') or sign_lookup2.get(p1_name, ''),
            "aspect": a.get('aspect', ''),
            "p2": p2_name,
            "p2_sign": sign_lookup2.get(p2_name, '') or sign_lookup1.get(p2_name, ''),
            "orb": round(float(a.get('orbit', a.get('orb', 0))), 1),
            "double_whammy": bool(a.get('double_whammy', False)),
        })

    # ── 3. RAG 检索 ──
    rag_query = f"synastry relationship compatibility aspects {' '.join(a.get('aspect','') for a in aspects[:5])}"
    rag_chunks = retrieve(rag_query, k=4)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = "\n\n【参考书籍片段（可参考相位解读，无需在 JSON 中注明）】\n" + "\n\n".join(parts) + "\n\n"

    # ── 4. 构建 Gemini payload ──
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

    # ── 5. 调用 Gemini（强制 JSON schema）──
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
