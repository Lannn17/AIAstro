"""
app/rag/chart_summary.py — 星盘摘要格式化 + 占星常量
"""

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
    "Sun":     {"domicile": ["Leo"],               "exalt": "Aries",      "detriment": ["Aquarius"],              "fall": "Libra"},
    "Moon":    {"domicile": ["Cancer"],             "exalt": "Taurus",     "detriment": ["Capricorn"],             "fall": "Scorpio"},
    "Mercury": {"domicile": ["Gemini", "Virgo"],   "exalt": "Virgo",      "detriment": ["Sagittarius", "Pisces"], "fall": "Pisces"},
    "Venus":   {"domicile": ["Taurus", "Libra"],   "exalt": "Pisces",     "detriment": ["Aries", "Scorpio"],      "fall": "Virgo"},
    "Mars":    {"domicile": ["Aries", "Scorpio"],  "exalt": "Capricorn",  "detriment": ["Taurus", "Libra"],       "fall": "Cancer"},
    "Jupiter": {"domicile": ["Sagittarius", "Pisces"], "exalt": "Cancer", "detriment": ["Gemini", "Virgo"],       "fall": "Capricorn"},
    "Saturn":  {"domicile": ["Capricorn", "Aquarius"], "exalt": "Libra",  "detriment": ["Cancer", "Leo"],         "fall": "Aries"},
}

_DIGNITY_LABEL = {"domicile": "入庙", "exalt": "入旺", "detriment": "失势", "fall": "陷落"}

# 用于元素/模式统计的主要行星列表（按 name_original 匹配，首字母大写）
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
