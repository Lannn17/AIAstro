"""
占星骰子核心逻辑 — 含义字典 + 掷骰 + RAG 解读
"""
import random
from .chat import rag_generate
from .prompt_registry import PROMPTS

# 行星英文名（name_original）→ 中文
_PLANET_EN_TO_CN: dict[str, str] = {
    "Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星",
    "Mars": "火星", "Jupiter": "木星", "Saturn": "土星", "Uranus": "天王星",
    "Neptune": "海王星", "Pluto": "冥王星", "Chiron": "凯龙",
    "True_Node": "北交点", "True Node": "北交点",
    "North Node": "北交点", "Mean_Node": "北交点",
    "Lilith": "莉莉丝",
}

# 骰子行星 key → chart name_original（首字母大写）
_DICE_TO_CHART_PLANET: dict[str, str] = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury",
    "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter",
    "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune",
    "pluto": "Pluto", "north_node": "True_Node", "chiron": "Chiron",
}

# ── 行星：能量/主题 ────────────────────────────────────────────────
_PLANET_MEANINGS = {
    "sun":        {"name": "太阳",   "core": "核心自我与目标",   "keywords": ["自我实现", "方向感", "生命力"]},
    "moon":       {"name": "月亮",   "core": "情绪与内心需求",   "keywords": ["安全感", "本能反应", "情感习惯"]},
    "mercury":    {"name": "水星",   "core": "思维与沟通方式",   "keywords": ["信息处理", "表达", "学习"]},
    "venus":      {"name": "金星",   "core": "价值观与关系",     "keywords": ["吸引力", "美感", "和谐"]},
    "mars":       {"name": "火星",   "core": "行动力与欲望",     "keywords": ["主动出击", "竞争", "冲突"]},
    "jupiter":    {"name": "木星",   "core": "扩展与机遇",       "keywords": ["成长", "乐观", "丰盛"]},
    "saturn":     {"name": "土星",   "core": "限制与责任",       "keywords": ["纪律", "考验", "长期积累"]},
    "uranus":     {"name": "天王星", "core": "突变与革新",       "keywords": ["意外转变", "自由", "打破常规"]},
    "neptune":    {"name": "海王星", "core": "梦想与模糊",       "keywords": ["直觉", "幻象", "灵性"]},
    "pluto":      {"name": "冥王星", "core": "深层转化与权力",   "keywords": ["控制欲", "死亡与重生", "潜意识"]},
    "north_node": {"name": "北交点", "core": "命运方向与成长",   "keywords": ["人生使命", "需要发展的方向"]},
    "chiron":     {"name": "凯龙",   "core": "伤痛与疗愈",       "keywords": ["脆弱", "疗愈能力", "导师"]},
}

# ── 星座：方式/风格 ────────────────────────────────────────────────
_SIGN_MEANINGS = {
    "Aries":       {"name": "牡羊座", "style": "直接果断、充满冲劲",   "element": "火"},
    "Taurus":      {"name": "金牛座", "style": "稳定务实、耐心坚持",   "element": "土"},
    "Gemini":      {"name": "双子座", "style": "灵活多变、善于沟通",   "element": "风"},
    "Cancer":      {"name": "巨蟹座", "style": "感性细腻、重视安全感", "element": "水"},
    "Leo":         {"name": "狮子座", "style": "热情自信、渴望被看见", "element": "火"},
    "Virgo":       {"name": "处女座", "style": "分析严谨、注重细节",   "element": "土"},
    "Libra":       {"name": "天秤座", "style": "追求平衡、重视公平",   "element": "风"},
    "Scorpio":     {"name": "天蝎座", "style": "深入执着、洞察本质",   "element": "水"},
    "Sagittarius": {"name": "射手座", "style": "开阔自由、追求真理",   "element": "火"},
    "Capricorn":   {"name": "摩羯座", "style": "踏实进取、目标导向",   "element": "土"},
    "Aquarius":    {"name": "水瓶座", "style": "独立创新、突破框架",   "element": "风"},
    "Pisces":      {"name": "双鱼座", "style": "敏感直觉、顺流而动",   "element": "水"},
}

# ── 宫位：生活领域 ─────────────────────────────────────────────────
_HOUSE_MEANINGS = {
    "1":  {"domain": "自我与外在形象",   "life_area": "个人身份、第一印象、新的开始"},
    "2":  {"domain": "金钱与物质资源",   "life_area": "财务、自我价值感、所拥有的事物"},
    "3":  {"domain": "沟通与日常环境",   "life_area": "学习、表达、短途出行、兄弟姐妹"},
    "4":  {"domain": "家庭与内心根基",   "life_area": "原生家庭、居住环境、情感安全感"},
    "5":  {"domain": "创造与自我表达",   "life_area": "爱好、恋爱、子女、玩乐与创作"},
    "6":  {"domain": "日常工作与健康",   "life_area": "工作习惯、身体状况、服务与例行事务"},
    "7":  {"domain": "一对一关系",       "life_area": "伴侣、合作伙伴、公开的竞争对手"},
    "8":  {"domain": "深层转化与共享资源", "life_area": "亲密关系、遗产、危机与重生"},
    "9":  {"domain": "扩展与高等追求",   "life_area": "信仰、高等教育、长途旅行、哲学"},
    "10": {"domain": "事业与社会地位",   "life_area": "职业成就、公众形象、人生目标"},
    "11": {"domain": "群体与未来愿景",   "life_area": "朋友圈、社群、理想与长远目标"},
    "12": {"domain": "潜意识与隐藏领域", "life_area": "内心深处、隐秘事物、灵性与退隐"},
}

_PLANETS = list(_PLANET_MEANINGS.keys())
_SIGNS = list(_SIGN_MEANINGS.keys())
_HOUSES = [str(i) for i in range(1, 13)]


def roll_dice() -> dict:
    """随机掷三颗骰子，返回 {planet, sign, house}"""
    return {
        "planet": random.choice(_PLANETS),
        "sign":   random.choice(_SIGNS),
        "house":  random.choice(_HOUSES),
    }


def roll_two_dice() -> dict:
    """追问模式：只掷行星 + 宫位（星座沿用原始结果）"""
    return {
        "planet": random.choice(_PLANETS),
        "house":  random.choice(_HOUSES),
    }


def roll_one_planet() -> dict:
    """补充能量模式：只掷行星骰"""
    return {"planet": random.choice(_PLANETS)}


def get_dice_display(planet: str, sign: str, house: str) -> dict:
    """返回三骰的中文展示信息"""
    p = _PLANET_MEANINGS[planet]
    s = _SIGN_MEANINGS[sign]
    h = _HOUSE_MEANINGS[house]
    return {
        "planet": {"key": planet, "name": p["name"], "core": p["core"]},
        "sign":   {"key": sign,   "name": s["name"], "style": s["style"], "element": s["element"]},
        "house":  {"key": house,  "number": house, "domain": h["domain"], "life_area": h["life_area"]},
    }


def build_core_sentence(planet: str, sign: str, house: str) -> str:
    p = _PLANET_MEANINGS[planet]
    s = _SIGN_MEANINGS[sign]
    h = _HOUSE_MEANINGS[house]
    return (
        f"在【{h['domain']}】领域，"
        f"以【{s['style']}】的方式，"
        f"处理与【{p['core']}】相关的议题。"
    )


def extract_natal_context(chart_data: dict, planet: str, sign: str, house: str) -> str:
    """
    从本命盘数据提取与骰子结果直接相关的6个字段，返回可注入 prompt 的中文文本。
    ① 上升 ② 太阳 ③ 月亮（固定基础）
    ④ 骰子行星在本命盘的位置 ⑤ 骰子星座内有哪些行星 ⑥ 骰子宫位宫首+宫内行星
    """
    if not chart_data:
        return ""

    # 建立 planet_info: name_original → {sign, house, retrograde}
    planet_info: dict[str, dict] = {}
    for _, p in chart_data.get("planets", {}).items():
        pname = p.get("name_original") or p.get("name", "")
        psign = p.get("sign_original") or p.get("sign", "")
        planet_info[pname] = {
            "sign": psign,
            "house": p.get("house"),
            "retrograde": p.get("retrograde", False),
        }

    # 建立 house_info: str(number) → sign_original
    house_info: dict[str, str] = {}
    for _, h in chart_data.get("houses", {}).items():
        if isinstance(h, dict):
            hnum = str(h.get("number", ""))
            hsign = h.get("sign_original") or h.get("sign", "")
            house_info[hnum] = hsign

    def _cn(pname: str) -> str:
        return _PLANET_EN_TO_CN.get(pname, pname)

    def _pi_str(pi: dict, label: str) -> str:
        retro = "（逆）" if pi.get("retrograde") else ""
        return f"{label}{pi['sign']}{pi['house']}宫{retro}"

    parts: list[str] = []

    # ① 上升
    asc = chart_data.get("ascendant", {})
    asc_sign = asc.get("sign_original") or asc.get("sign", "")
    if asc_sign:
        parts.append(f"上升{asc_sign}")

    # ② 太阳  ③ 月亮
    for en_name, label in [("Sun", "太阳"), ("Moon", "月亮")]:
        pi = planet_info.get(en_name)
        if pi:
            parts.append(_pi_str(pi, label))

    # ④ 骰子行星在本命盘的位置
    chart_pname = _DICE_TO_CHART_PLANET.get(planet)
    if chart_pname and chart_pname not in planet_info and planet == "north_node":
        for alt in ["True Node", "North Node", "Mean_Node"]:
            if alt in planet_info:
                chart_pname = alt
                break
    if chart_pname:
        pi = planet_info.get(chart_pname)
        if pi:
            pname_cn = _PLANET_MEANINGS[planet]["name"]
            parts.append(_pi_str(pi, f"本命{pname_cn}在"))

    # ⑤ 骰子星座内的行星
    in_sign = [_cn(pn) for pn, pi in planet_info.items() if pi["sign"] == sign]
    sign_cn = _SIGN_MEANINGS[sign]["name"]
    parts.append(f"本命{sign_cn}内{'有' + '/'.join(in_sign) if in_sign else '无行星'}")

    # ⑥ 骰子宫位的宫首星座 + 宫内行星
    h_sign = house_info.get(house, "")
    in_house = [_cn(pn) for pn, pi in planet_info.items() if str(pi.get("house", "")) == house]
    h_line = f"第{house}宫宫首{h_sign}" if h_sign else f"第{house}宫"
    h_line += f"，宫内{'有' + '/'.join(in_house) if in_house else '无行星'}"
    parts.append(h_line)

    return "；".join(parts)


def interpret_dice(
    planet: str,
    sign: str,
    house: str,
    question: str,
    category: str,
    natal_context: str = "",
) -> dict:
    """
    主解读：三颗骰子 + 用户问题 → RAG + LLM 生成个性化解读
    返回 {dice_display, core_sentence, interpretation, keywords, sources}
    """
    p = _PLANET_MEANINGS[planet]
    s = _SIGN_MEANINGS[sign]
    h = _HOUSE_MEANINGS[house]

    core_sentence = build_core_sentence(planet, sign, house)
    keywords = p["keywords"] + [s["style"]] + [h["life_area"]]

    tmpl = PROMPTS["astro_dice"]["prompt_template"]
    temperature = PROMPTS["astro_dice"]["temperature"]
    natal_section = (
        f"\n用户本命盘参考（结合以下信息个性化解读）：{natal_context}"
        if natal_context else ""
    )
    prompt = tmpl.format(
        question=question,
        category=category,
        planet_name=p["name"],
        sign_name=s["name"],
        house_number=house,
        core_sentence=core_sentence,
        keywords=", ".join(keywords),
        natal_section=natal_section,
    )

    rag_query = f"{planet} {sign} house {house} divination question"
    answer, sources = rag_generate(rag_query, prompt, k=3, temperature=temperature)

    return {
        "dice_display": get_dice_display(planet, sign, house),
        "core_sentence": core_sentence,
        "interpretation": answer,
        "keywords": keywords,
        "sources": sources,
    }


def interpret_followup(
    original_planet: str,
    original_sign: str,
    original_house: str,
    original_question: str,
    new_planet: str,
    new_house: str,
    followup_question: str,
    category: str,
) -> dict:
    """
    追问模式：保留原始星座，掷新行星+宫位，结合原始背景生成追问解读
    """
    orig_core = build_core_sentence(original_planet, original_sign, original_house)
    op = _PLANET_MEANINGS[original_planet]
    os_data = _SIGN_MEANINGS[original_sign]

    np = _PLANET_MEANINGS[new_planet]
    nh = _HOUSE_MEANINGS[new_house]
    new_core = (
        f"在【{nh['domain']}】领域，"
        f"延续【{os_data['style']}】的底色，"
        f"聚焦【{np['core']}】的能量。"
    )

    tmpl = PROMPTS["astro_dice_followup"]["prompt_template"]
    temperature = PROMPTS["astro_dice_followup"]["temperature"]
    prompt = tmpl.format(
        original_question=original_question,
        followup_question=followup_question,
        category=category,
        original_core=orig_core,
        original_planet=op["name"],
        original_sign=os_data["name"],
        new_planet=np["name"],
        new_house=new_house,
        new_core=new_core,
        keywords=", ".join(np["keywords"] + [os_data["style"]] + [nh["life_area"]]),
    )

    rag_query = f"{new_planet} {original_sign} house {new_house} horary follow up"
    answer, sources = rag_generate(rag_query, prompt, k=3, temperature=temperature)

    return {
        "dice_display": {
            "planet": {"key": new_planet, "name": np["name"], "core": np["core"]},
            "sign":   {"key": original_sign, "name": os_data["name"],
                       "style": os_data["style"], "element": os_data["element"],
                       "inherited": True},
            "house":  {"key": new_house, "number": new_house,
                       "domain": nh["domain"], "life_area": nh["life_area"]},
        },
        "core_sentence": new_core,
        "interpretation": answer,
        "keywords": np["keywords"] + [os_data["style"]] + [nh["life_area"]],
        "sources": sources,
    }


def interpret_supplement(
    original_planet: str,
    original_sign: str,
    original_house: str,
    original_question: str,
    supplement_planet: str,
) -> dict:
    """
    补充能量模式：只掷行星骰，作为辅助星追加解读
    """
    orig_core = build_core_sentence(original_planet, original_sign, original_house)
    sp = _PLANET_MEANINGS[supplement_planet]

    prompt = (
        f"原始占卜背景：{orig_core}\n"
        f"用户问题：{original_question}\n\n"
        f"现在出现了辅助能量：【{sp['name']}】（{sp['core']}）\n"
        f"关键词：{', '.join(sp['keywords'])}\n\n"
        "请用 60-80 字说明这股辅助能量为原解读补充了什么视角或提示，"
        "语气简洁，以【另有一股……能量在侧】开头。"
    )

    rag_query = f"{supplement_planet} auxiliary energy astrology"
    answer, sources = rag_generate(rag_query, prompt, k=2, temperature=0.5)

    return {
        "supplement_planet": {"key": supplement_planet, "name": sp["name"], "core": sp["core"]},
        "interpretation": answer,
        "sources": sources,
    }
