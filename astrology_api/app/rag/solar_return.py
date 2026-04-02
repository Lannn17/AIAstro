"""
app/rag/solar_return.py — Solar Return 规则引擎 + AI 年度报告生成
"""
from .client import get_last_model_used
from .retrieval import _parse_json
from .chat import rag_generate
from .prompt_registry import PROMPTS as _PROMPTS  # noqa: F401 — registry ref; prompt migration pending
from ..interpretations.translations import translate_planet

# 权重三档：强=3 / 中=2 / 弱=1，避免细粒度数字导致伪精度排名翻转

_SR_ASC_NATAL_HOUSE_WEIGHTS = {
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

    # ── Layer 1: SR ASC in natal house ──
    natal_house = _sr_find_natal_house(sr_asc_degree, natal_houses)
    if natal_house and natal_house in _SR_ASC_NATAL_HOUSE_WEIGHTS:
        add(_SR_ASC_NATAL_HOUSE_WEIGHTS[natal_house], f"SR上升落本命第{natal_house}宫")

    # ── Layer 2: SR Sun house ──
    sun = sr_planets.get("sun", {})
    sun_house = str(sun.get("house", 0)) if sun.get("house", 0) > 0 else ""
    if sun_house in _SR_SUN_HOUSE_WEIGHTS:
        add(_SR_SUN_HOUSE_WEIGHTS[sun_house], f"SR太阳落第{sun_house}宫")

    # ── Layer 3: SR Moon house ──
    moon = sr_planets.get("moon", {})
    moon_house = str(moon.get("house", 0)) if moon.get("house", 0) > 0 else ""
    if moon_house in _SR_MOON_HOUSE_WEIGHTS:
        add(_SR_MOON_HOUSE_WEIGHTS[moon_house], f"SR月亮落第{moon_house}宫")

    # ── Layer 4: SR ASC ruler house (+1 per theme, +1 bonus if angular) ──
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

    # ── Layer 5: Angular house emphasis ──
    house_planet_count: dict[str, int] = {}
    for key, p in sr_planets.items():
        h = str(p.get("house", ""))
        if h in _SR_ANGULAR_THEMES:
            house_planet_count[h] = house_planet_count.get(h, 0) + 1
    for h, cnt in house_planet_count.items():
        if cnt >= 2:
            theme = _SR_ANGULAR_THEMES[h]
            bonus = min(cnt - 1, 2)
            scores[theme] = scores.get(theme, 0) + bonus
            facts.append(f"第{h}宫角宫强调（{cnt}颗行星）")

    # ── Layer 6: Jupiter / Saturn / Venus / Mars house ──
    for planet_key, house_map in _SR_PLANET_HOUSE_WEIGHTS.items():
        p = sr_planets.get(planet_key, {})
        p_house = str(p.get("house", ""))
        if p_house in house_map:
            add(house_map[p_house], f"{translate_planet(planet_key, 'zh')}落SR第{p_house}宫")

    # ── Modifier aspects (orb ≤ 3°) ──
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

    # ── Compile output ──
    top_themes = sorted(
        [{"theme": k, "score": int(v)} for k, v in scores.items()],
        key=lambda x: -x["score"]
    )[:3]

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
- themes 的 score 字段必须是 0-100 的百分制整数（最强主题接近100，其余按相对强度换算），不要直接复制 theme_scores 的原始数值
- themes 必须按得分从高到低排列，且顺序与 theme_scores 一致
- 对健康、财务等敏感主题避免确定性建议
"""

    answer, sources = rag_generate(rag_query, prompt, k=5, temperature=0.35)
    model_used = get_last_model_used()

    try:
        parsed = _parse_json(answer)
    except Exception:
        parsed = {}

    themes_out = parsed.get("themes", [])

    # 兜底归一化：若 Gemini 仍输出了原始小分（最高值 < 20），换算为百分制
    if themes_out:
        max_t = max((t.get("score", 0) for t in themes_out), default=0)
        if 0 < max_t < 20:
            for t in themes_out:
                t["score"] = round(t.get("score", 0) / max_t * 100)

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
