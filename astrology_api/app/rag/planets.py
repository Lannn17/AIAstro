"""
app/rag/planets.py — 本命盘行星逐一解读 + 确定性事实提取
"""
from google.genai import types

from .client import client, GENERATE_MODEL, get_last_model_used
from .retrieval import retrieve, _load, _parse_json
from .prompts import _clean_source_name, _SYSTEM_PROMPT_UNIFIED
from .chart_summary import _SIGN_ELEMENT, _SIGN_MODALITY
from ..interpretations.translations import translate_planet, translate_sign

_SKIP_PLANETS = {'true_node', 'true_lilith', 'true_south_node'}

# 用于 _compute_chart_facts 的行星集合（按 planets dict 的 key 匹配，小写）
_CORE_PLANETS = {'sun', 'moon', 'mercury', 'venus', 'mars',
                 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'}


def _compute_chart_facts(natal_chart: dict) -> list[str]:
    """从星盘数据中用规则提取确定性事实标签，供 AI prompt 使用。"""
    planets = natal_chart.get('planets', {})
    aspects = natal_chart.get('aspects', [])

    sign_planets: dict[str, list] = {}
    house_planets: dict[int, list] = {}
    elem_count = {'火': 0, '土': 0, '风': 0, '水': 0}
    mode_count = {'开创': 0, '固定': 0, '变动': 0}
    retro_names = []

    for key, p in planets.items():
        sign_raw = p.get('sign_original') or p.get('sign', '')
        sign_zh = translate_sign(sign_raw, 'zh') if sign_raw else sign_raw
        house = p.get('house') or 0
        name_raw = p.get('name_original') or p.get('name', key)
        name_zh = translate_planet(name_raw, 'zh') if name_raw else name_raw
        if key in _CORE_PLANETS:
            sign_planets.setdefault(sign_zh, []).append(name_zh)
            if house:
                house_planets.setdefault(house, []).append(name_zh)
            if sign_raw in _SIGN_ELEMENT:
                elem_count[_SIGN_ELEMENT[sign_raw]] += 1
            if sign_raw in _SIGN_MODALITY:
                mode_count[_SIGN_MODALITY[sign_raw]] += 1
        if p.get('retrograde') and key in _CORE_PLANETS:
            retro_names.append(name_zh)

    facts = []

    # 星座群星（含具体行星名）
    for s, planets_list in sign_planets.items():
        if len(planets_list) >= 3:
            planet_str = '·'.join(planets_list)
            facts.append(f"群星{s}（{planet_str}）")

    # 宫位强势（含具体行星名）
    for h, planets_list in house_planets.items():
        if len(planets_list) >= 3:
            planet_str = '·'.join(planets_list)
            facts.append(f"第{h}宫强势（{planet_str}）")

    # 元素主导
    dom_elem = max(elem_count, key=elem_count.get)
    if elem_count[dom_elem] >= 4:
        facts.append(f"多{dom_elem}象行星（{elem_count[dom_elem]}颗）")

    # 模式主导
    dom_mode = max(mode_count, key=mode_count.get)
    if mode_count[dom_mode] >= 4:
        facts.append(f"多{dom_mode}星（{mode_count[dom_mode]}颗）")

    # 逆行
    if retro_names:
        facts.append(f"逆行行星：{'、'.join(retro_names)}")

    # 相位格局检测
    trine_pairs: set[tuple] = set()
    opp_pairs: list[tuple] = []
    sq_map: dict[str, set] = {}

    for a in aspects:
        asp = (a.get('aspect_original') or a.get('aspect', '')).lower()
        orb = a.get('orbit', 99)
        p1, p2 = a.get('p1_name', ''), a.get('p2_name', '')
        if not p1 or not p2:
            continue
        if 'trine' in asp and orb < 8:
            trine_pairs.add((p1, p2))
            trine_pairs.add((p2, p1))
        if 'opposition' in asp and orb < 8:
            opp_pairs.append((p1, p2))
        if 'square' in asp and orb < 8:
            sq_map.setdefault(p1, set()).add(p2)
            sq_map.setdefault(p2, set()).add(p1)

    # 大三角：三颗行星互相形成三分相
    tp_list = list({p for pair in trine_pairs for p in pair})
    gt_found = False
    for i in range(len(tp_list)):
        for j in range(i + 1, len(tp_list)):
            for k in range(j + 1, len(tp_list)):
                a, b, c = tp_list[i], tp_list[j], tp_list[k]
                if (a, b) in trine_pairs and (a, c) in trine_pairs and (b, c) in trine_pairs:
                    facts.append(f"大三角格局（{a}·{b}·{c}）")
                    gt_found = True
                    break
            if gt_found:
                break
        if gt_found:
            break

    # T三角：一对对冲 + 一颗行星分别四分两端
    for (a, b) in opp_pairs:
        sq_a = sq_map.get(a, set())
        sq_b = sq_map.get(b, set())
        apex_set = sq_a & sq_b
        if apex_set:
            apex = next(iter(apex_set))
            facts.append(f"T三角格局（顶点：{apex}，对冲：{a}·{b}）")

    return facts


def analyze_planets(natal_chart: dict, language: str = 'zh') -> dict:
    """
    为本命盘每颗行星生成简洁解读（单次 Gemini 调用，返回全部结果）。
    返回: {"sun": "解读文字", "moon": "...", ...}
    """
    planets = natal_chart.get('planets', {})
    asc = natal_chart.get('ascendant', {})
    mc  = natal_chart.get('midheaven', {})
    asc_sign_raw = asc.get('sign_original') or asc.get('sign', '')
    mc_sign_raw  = mc.get('sign_original')  or mc.get('sign', '')
    asc_sign = translate_sign(asc_sign_raw, 'zh') if asc_sign_raw else ''
    mc_sign  = translate_sign(mc_sign_raw,  'zh') if mc_sign_raw  else ''

    # 推算 DSC/IC 对点星座
    _OPPOSITE = {
        'Aries':'Libra','Taurus':'Scorpio','Gemini':'Sagittarius','Cancer':'Capricorn',
        'Leo':'Aquarius','Virgo':'Pisces','Libra':'Aries','Scorpio':'Taurus',
        'Sagittarius':'Gemini','Capricorn':'Cancer','Aquarius':'Leo','Pisces':'Virgo',
    }
    dsc_sign_raw = _OPPOSITE.get(asc_sign_raw, '')
    ic_sign_raw  = _OPPOSITE.get(mc_sign_raw,  '')
    dsc_sign = translate_sign(dsc_sign_raw, 'zh') if dsc_sign_raw else ''
    ic_sign  = translate_sign(ic_sign_raw,  'zh') if ic_sign_raw  else ''

    # 行星列表（含逆行标注），同时记录 key 顺序用于生成 JSON 模板
    lines = []
    planet_keys = []
    for key, p in planets.items():
        if key in _SKIP_PLANETS:
            continue
        name_raw = p.get('name_original') or p.get('name', key)
        sign_raw = p.get('sign_original') or p.get('sign', '')
        name = translate_planet(name_raw, 'zh') if name_raw else name_raw
        sign = translate_sign(sign_raw, 'zh') if sign_raw else sign_raw
        house = p.get('house', '')
        retro = '（逆行）' if p.get('retrograde') else ''
        lines.append(f"{name}（key: {key}）: {sign} 第{house}宫{retro}")
        planet_keys.append(key)
    planet_list = '\n'.join(lines)
    # 动态生成 JSON 模板，确保 AI 为每颗行星（包括小行星）返回分析
    planet_entries = ',\n  '.join(f'"{k}": "..."' for k in planet_keys)
    json_template = (
        '{\n  ' + planet_entries + ',\n'
        '  "asc": "...",\n'
        '  "dsc": "...",\n'
        '  "mc": "...",\n'
        '  "ic": "...",\n'
        '  "overall": {\n'
        '    "tags": ["...", "..."],\n'
        '    "summary": "...",\n'
        '    "career": "...",\n'
        '    "love": "...",\n'
        '    "wealth": "...",\n'
        '    "health": "..."\n'
        '  },\n'
        '  "source_refs": {"<参考编号>": "<20-40字中文概括>"}  // 仅填写实际引用的编号\n'
        '}'
    )

    # 宫位守星表
    houses = natal_chart.get('houses', {})
    house_lines = []
    for num in range(1, 13):
        h = houses.get(str(num), {})
        hsign_raw = h.get('sign_original') or h.get('sign', '')
        if hsign_raw:
            hsign = translate_sign(hsign_raw, 'zh')
            house_lines.append(f"第{num}宫: {hsign}")
    house_summary = '\n'.join(house_lines)

    # 主要相位摘要（合/对/四分/三分/六分，容许度<6°）
    aspects = natal_chart.get('aspects', [])
    aspect_lines = []
    for a in aspects:
        p1 = a.get('p1_name', '')
        p2 = a.get('p2_name', '')
        asp = a.get('aspect', '')
        orbit = a.get('orbit', 99)
        if orbit < 6 and p1 and p2 and asp:
            aspect_lines.append(f"{p1} {asp} {p2}（容许度{round(orbit,1)}°）")
    aspect_summary = '\n'.join(aspect_lines) if aspect_lines else '（无数据）'

    # 规则提取确定性事实
    chart_facts = _compute_chart_facts(natal_chart)
    facts_section = ''
    if chart_facts:
        facts_section = '\n\n【规则检测到的确定性事实（必须体现在 tags 中）】\n' + '\n'.join(f'- {f}' for f in chart_facts)

    # RAG 检索
    _load()
    try:
        rag_chunks = retrieve(f"行星星座宫位解读 {asc_sign}上升", k=3)
    except Exception:
        rag_chunks = []
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = (
            "\n\n---\n参考书籍片段（仅供内部参考，不得在行星解读文字中引用英文原文或标注书名；"
            "若引用，请只在 source_refs 字段中填写编号和中文概括，不得在解读正文中出现任何英文或引用格式）：\n\n"
            + "\n\n".join(parts)
        )

    # 四交点信息
    angles_section = ""
    if asc_sign or mc_sign:
        angles_section = f"""
四交点轴线：
上升 ASC（第1宫起点）: {asc_sign}  |  下降 DSC（第7宫起点）: {dsc_sign}
天顶 MC（第10宫起点）: {mc_sign}   |  天底 IC（第4宫起点）: {ic_sign}
"""

    prompt = f"""请为以下本命盘行星位置分别生成占星解读，并在最后给出四交点解读和综合概述。

上升星座：{asc_sign}
{angles_section}
行星位置：
{planet_list}

宫位起点星座（用于推算飞星/守护星落位）：
{house_summary}

主要相位：
{aspect_summary}{facts_section}

分析要求——每颗行星必须同时结合以下维度：
1. 【星座特质】该行星在此星座的表达方式与能量底色
2. 【宫位主题】该宫位代表的人生领域，以及行星如何在此显化
3. 【飞星影响】该行星所在星座的守护星落在哪个宫位，形成何种能量流向；若行星本身也是某宫主星，一并说明其飞入他宫的含义
4. 若有重要相位（容许度<4°），简述其对该行星能量的加强或挑战
5. 逆行行星需特别说明内化/重新审视的主题

每颗行星 80-120 字，风格专业简洁，直接指向对当事人的影响。

四交点分析要求（asc/dsc/mc/ic）：
- asc（上升 {asc_sign}）：外在气质、第一印象、身体与外貌特征，80-120 字
- dsc（下降 {dsc_sign}）：理想伴侣特质、人际关系模式与吸引规律，80-120 字
- mc（天顶 {mc_sign}）：职业方向、社会形象与人生志向，80-120 字
- ic（天底 {ic_sign}）：家庭底色、童年环境与内心安全感来源，80-120 字

综合概述（overall）为结构化对象，包含以下字段：
- tags: 字符串数组，**必须优先使用上方【确定性事实】中列出的标签**，再补充 AI 判断的其他特征（如「命主星逆行」「日月形成对冲」等），共 3-6 个
- summary: 主要人生命题、核心潜力与成长方向，100-150 字
- career: 学业与事业领域分析，列出支持该结论的具体行星/宫位依据，80-100 字
- love: 恋爱与家庭领域分析，附占星依据，80-100 字
- wealth: 财富与物质领域分析，附占星依据，80-100 字
- health: 健康与身体领域分析，附占星依据，60-80 字

**必须为以上列出的每一颗行星（包括凯龙、北交点、南交点、莉莉丝等小行星）生成解读，不得遗漏任何一个。**
**必须为四交点（asc/dsc/mc/ic）各生成解读，不得遗漏。**

**严格禁止**在任何行星解读文字（JSON 值）中出现：英文引用原文、书名标注、「参考《...》」格式、或任何引用注记。行星解读必须是纯中文分析文字。引用信息只能通过 source_refs 字段以中文概括表达。

以 JSON 格式返回（严格使用以下 key，每个 key 对应一段解读文字，overall 为嵌套对象；source_refs 仅填写实际引用的参考编号）：
{json_template}{rag_context}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )
    model_used = get_last_model_used()
    try:
        parsed = _parse_json(response.text)
    except Exception as e:
        print(f"[planets] JSON parse error: {e}")
        return {"analyses": {}, "sources": [], "model_used": model_used}

    print(f"[planets] parsed keys: {list(parsed.keys())}", flush=True)
    # Detect any planet/angle keys Gemini silently dropped (output token pressure)
    _angle_sign_map = {'asc': asc_sign, 'dsc': dsc_sign, 'mc': mc_sign, 'ic': ic_sign}
    angle_keys = [k for k, s in _angle_sign_map.items() if s]
    missing_keys = [k for k in planet_keys + angle_keys if k not in parsed]
    if missing_keys:
        print(f"[planets] Gemini dropped {missing_keys}, retrying", flush=True)
        missing_planet_lines = [l for l in lines if any(f"(key: {k})" in l for k in missing_keys)]
        _angle_desc = {
            'asc': f"上升 ASC（key: asc）: {asc_sign} — 外在气质、第一印象、外貌特征",
            'dsc': f"下降 DSC（key: dsc）: {dsc_sign} — 理想伴侣特质、人际关系模式",
            'mc':  f"天顶 MC（key: mc）: {mc_sign} — 职业方向、社会形象与志向",
            'ic':  f"天底 IC（key: ic）: {ic_sign} — 家庭底色、童年环境与安全感来源",
        }
        missing_angle_lines = [_angle_desc[k] for k in missing_keys if k in _angle_desc]
        all_missing_lines = missing_planet_lines + missing_angle_lines
        missing_entries = ',\n  '.join(f'"{k}": "..."' for k in missing_keys)
        retry_prompt = f"""请为以下本命盘位置生成占星解读，仅针对列出的条目。

上升星座：{asc_sign}

位置列表：
{chr(10).join(all_missing_lines)}

宫位起点星座：
{house_summary}

主要相位：
{aspect_summary}

每项 80-120 字，专业简洁。以 JSON 格式返回：
{{\n  {missing_entries}\n}}"""
        try:
            retry_resp = client.models.generate_content(
                model=GENERATE_MODEL,
                contents=retry_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT_UNIFIED,
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            retry_parsed = _parse_json(retry_resp.text)
            parsed.update(retry_parsed)
        except Exception as e:
            print(f"[planets] retry for missing planets failed: {e}", flush=True)

    source_refs = parsed.pop("source_refs", {}) or {}
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
    return {"analyses": parsed, "sources": rag_sources, "model_used": model_used}
