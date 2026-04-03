"""
Centralized prompt registry — single source of truth for all AI prompt templates.
Each entry: caller_key → {prompt_template, system_instruction, temperature, description}

prompt_template uses {placeholder} syntax. Callers call:
    tmpl = PROMPTS["caller"]["prompt_template"]
    prompt = tmpl.format(var1=..., var2=...)

For prompts with dynamic appended sections (rag_context, json_template),
callers build those sections separately and concatenate:
    prompt = tmpl.format(...) + rag_context
"""
from .prompts import _SYSTEM_PROMPT_UNIFIED

PROMPTS: dict[str, dict] = {

    # ── 系统 prompt（共用）──────────────────────────────────────────
    "system": {
        "prompt_template": _SYSTEM_PROMPT_UNIFIED,
        "system_instruction": None,
        "temperature": None,
        "description": "全局系统 prompt（占星师人设）",
    },

    # ── 本命盘行星解读 ───────────────────────────────────────────────
    "interpret_planets": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.3,
        "description": "本命盘逐行星 + 四交点 AI 解读",
        # Placeholders: {asc_sign} {dsc_sign} {mc_sign} {ic_sign}
        #               {angles_section} {planet_list} {house_summary}
        #               {aspect_summary} {facts_section}
        # Caller appends: + json_template + rag_context  (not via .format)
        "prompt_template": (
            "请为以下本命盘行星位置分别生成占星解读，并在最后给出四交点解读和综合概述。\n\n"
            "上升星座：{asc_sign}\n"
            "{angles_section}\n"
            "行星位置：\n{planet_list}\n\n"
            "宫位起点星座（用于推算飞星/守护星落位）：\n{house_summary}\n\n"
            "主要相位：\n{aspect_summary}{facts_section}\n\n"
            "分析要求——每颗行星必须同时结合以下维度：\n"
            "1. 【星座特质】该行星在此星座的表达方式与能量底色\n"
            "2. 【宫位主题】该宫位代表的人生领域，以及行星如何在此显化\n"
            "3. 【飞星影响】该行星所在星座的守护星落在哪个宫位，形成何种能量流向；"
            "若行星本身也是某宫主星，一并说明其飞入他宫的含义\n"
            "4. 若有重要相位（容许度<4°），简述其对该行星能量的加强或挑战\n"
            "5. 逆行行星需特别说明内化/重新审视的主题\n\n"
            "每颗行星 80-120 字，风格专业简洁，直接指向对当事人的影响。\n\n"
            "四交点分析要求（asc/dsc/mc/ic）：\n"
            "- asc（上升 {asc_sign}）：外在气质、第一印象、身体与外貌特征，80-120 字\n"
            "- dsc（下降 {dsc_sign}）：理想伴侣特质、人际关系模式与吸引规律，80-120 字\n"
            "- mc（天顶 {mc_sign}）：职业方向、社会形象与人生志向，80-120 字\n"
            "- ic（天底 {ic_sign}）：家庭底色、童年环境与内心安全感来源，80-120 字\n\n"
            "综合概述（overall）为结构化对象，包含以下字段：\n"
            "- tags: 字符串数组，**必须优先使用上方【确定性事实】中列出的标签**，"
            "再补充 AI 判断的其他特征（如「命主星逆行」「日月形成对冲」等），共 3-6 个\n"
            "- summary: 主要人生命题、核心潜力与成长方向，100-150 字\n"
            "- career: 学业与事业领域分析，列出支持该结论的具体行星/宫位依据，80-100 字\n"
            "- love: 恋爱与家庭领域分析，附占星依据，80-100 字\n"
            "- wealth: 财富与物质领域分析，附占星依据，80-100 字\n"
            "- health: 健康与身体领域分析，附占星依据，60-80 字\n\n"
            "**必须为以上列出的每一颗行星（包括凯龙、北交点、南交点、莉莉丝等小行星）生成解读，不得遗漏任何一个。**\n"
            "**必须为四交点（asc/dsc/mc/ic）各生成解读，不得遗漏。**\n\n"
            "**严格禁止**在任何行星解读文字（JSON 值）中出现：英文引用原文、书名标注、"
            "「参考《...》」格式、或任何引用注记。行星解读必须是纯中文分析文字。"
            "引用信息只能通过 source_refs 字段以中文概括表达。\n\n"
            "以 JSON 格式返回（严格使用以下 key，每个 key 对应一段解读文字，"
            "overall 为嵌套对象；source_refs 仅填写实际引用的参考编号）："
        ),
    },

    # ── 单日行运解读 ────────────────────────────────────────────────
    "transits_single": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.5,
        "description": "单日行运综合解读",
        # Placeholders: {transit_date} {chart_summary} {planet_lines_str} {aspect_lines_str}
        # Caller appends rag_context via rag_generate() — not via .format
        "prompt_template": (
            "行运日期：{transit_date}\n\n"
            "{chart_summary}\n\n"
            "【行运行星位置】\n{planet_lines_str}\n\n"
            "【行运-本命相位】（按容许度排序）\n{aspect_lines_str}\n\n"
            "---\n"
            "请根据以上数据，对当日行运给出综合解读：\n"
            "1. 整体能量与基调\n"
            "2. 重点相位的具体影响（优先分析容许度≤2°的相位）\n"
            "3. 机遇与挑战\n"
            "4. 建议关注的事项"
        ),
    },

    # ── 行运完整分析（有新行运）──────────────────────────────────────
    "transits_full_new": {
        "system_instruction": None,
        "temperature": 0.5,
        "description": "行运完整分析 — 含需要新解读的行运",
        # Placeholders: {chart_summary} {query_date} {all_block} {new_block} {rag_context} {source_refs_schema}
        # Note: JSON braces escaped as {{ }} — caller uses .format()
        "prompt_template": (
            "你是一位经验丰富的职业占星师，精通西方占星学的行运分析。\n\n"
            "{chart_summary}\n\n"
            "━━━ 当前所有活跃行运（{query_date}，供整体分析参考） ━━━\n\n"
            "{all_block}\n\n"
            "━━━ 以下行运需要新的逐相位解读 ━━━\n\n"
            "{new_block}{rag_context}\n\n"
            "【分析要求】\n\n"
            "**对\"需要新解读\"的每条行运**（约 150-250 字/条）：\n"
            "- 结合本命盘中该行星的星座、宫位\n"
            "- 说明具体影响的生活领域\n"
            "- 若为逆行周期，点明三次过境节奏\n"
            "- 给出 tone（顺势/挑战/转化 之一）和 themes（从\"事业、感情、家庭、财务、健康、自我成长、人际关系、创意、精神\"中选 1-3 个）\n\n"
            "**整体行运综述**（约 300-400 字，基于所有活跃行运）：\n"
            "- 开头先点出当前阶段主要影响的人生命题（1-2 句）\n"
            "- 识别主题叠加（多个相位指向同一领域则标注\"已获多重星象确认\"）\n"
            "- 给出具体行动建议\n"
            "- 语言自然，避免机械罗列\n\n"
            "JSON 格式返回（aspects 只包含\"需要新解读\"的行运）：\n"
            "{{\n"
            "  \"aspects\": [\n"
            "    {{\n"
            "      \"key\": \"<与上方 key 完全一致>\",\n"
            "      \"analysis\": \"<150-250字解读>\",\n"
            "      \"tone\": \"<顺势|挑战|转化>\",\n"
            "      \"themes\": [\"<主题1>\", \"<主题2>\"]\n"
            "    }}\n"
            "  ],\n"
            "  \"overall\": \"<整体综述>\",\n"
            "  {source_refs_schema}\n"
            "}}\n"
        ),
    },

    # ── 行运完整分析（全部命中缓存）────────────────────────────────
    "transits_full_summary": {
        "system_instruction": None,
        "temperature": 0.5,
        "description": "行运完整分析 — 全部命中缓存，只生成综述",
        # Placeholders: {chart_summary} {query_date} {all_block} {rag_context} {source_refs_schema}
        "prompt_template": (
            "你是一位经验丰富的职业占星师，精通西方占星学的行运分析。\n\n"
            "{chart_summary}\n\n"
            "━━━ 当前所有活跃行运（{query_date}） ━━━\n\n"
            "{all_block}{rag_context}\n\n"
            "请提供整体行运综述（约 300-400 字）：\n"
            "- 开头先点出当前阶段主要影响的人生命题（1-2 句）\n"
            "- 识别主题叠加（多个相位指向同一领域则标注\"已获多重星象确认\"）\n"
            "- 给出具体行动建议\n"
            "- 语言自然，避免机械罗列\n\n"
            "{{\"overall\": \"<整体综述>\", {source_refs_schema}}}\n"
        ),
    },

    # ── RAG 基础问答 ────────────────────────────────────────────────
    "generate": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.4,
        "description": "RAG 基础问答（书籍片段 + 用户问题）",
        # Placeholders: {context} {query}
        "prompt_template": (
            "以下是来自占星书籍的相关片段：\n\n"
            "{context}\n\n"
            "---\n"
            "用户问题：{query}\n\n"
            "请根据以上片段回答问题。"
        ),
    },

    # ── 星盘对话 ────────────────────────────────────────────────────
    "chat_with_chart": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.5,
        "description": "基于星盘数据的占星对话",
        # Placeholders: {chart_summary} {transit_context}
        # transit_context is "" when not applicable
        # Caller appends rag section via _build_rag_section
        "prompt_template": (
            "以下是用户的本命盘信息：\n\n"
            "{chart_summary}\n"
            "{transit_context}\n\n"
            "请根据以上星盘数据回答用户的问题。"
        ),
    },

    # ── 合盘分析 ────────────────────────────────────────────────────
    "analyze_synastry": {
        "system_instruction": None,
        "temperature": 0.4,
        "description": "双人合盘关系分析",
        # Placeholders: {rag_context} {context_json}
        "prompt_template": (
            "你是专业占星师，请根据以下两人的完整星盘数据进行合盘分析。\n"
            "{rag_context}\n"
            "【数据】\n{context_json}\n\n"
            "【分析要求】\n"
            "1. 识别1-2个关系质感标签（从给定列表中选择），并用一句话说明依据\n"
            "2. 评估最可能自然形成的关系类型Top 3，给出0-100概率分，引用具体相位作为证据（最多3条），用2-3句话描述\n"
            "3. 对六个维度各给出0-100分和分析，分析中必须引用具体行星相位，使用普通用户能理解的语言\n\n"
            "注意：\n"
            "- 概率分反映\"这段关系的能量自然倾向\"，不是主观建议\n"
            "- 相位的星座背景很重要，请考虑星座特质对相位能量的调整\n"
            "- double whammy（双向命中）相位的权重更高\n"
            "- Top 3关系类型必须是三种不同的类型，不可重复\n"
            "- 请用中文回答"
        ),
    },

    # ── 太阳回归 ────────────────────────────────────────────────────
    "analyze_solar_return": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.35,
        "description": "太阳回归年度分析报告",
        # Placeholders: {sr_year} {name} {sr_summary} {natal_summary}
        #               {theme_scores_text} {facts_text} {modifiers_text}
        # Caller uses rag_generate(query, prompt) — rag appended internally
        "prompt_template": (
            "请为以下太阳回归盘生成详细的年度分析报告。\n\n"
            "【基本信息】\n"
            "分析对象：{name}\n"
            "太阳回归年份：{sr_year}\n\n"
            "【太阳回归盘】\n{sr_summary}\n\n"
            "【本命盘（参考背景）】\n{natal_summary}\n\n"
            "【规则引擎主题评分（0-100）】\n{theme_scores_text}\n\n"
            "【确定性事实】\n{facts_text}\n\n"
            "【修正因子】\n{modifiers_text}\n\n"
            "请生成结构化JSON报告，包含：\n"
            "- keywords: 年度关键词数组（3-5个）\n"
            "- summary: 年度主题总览（150-200字）\n"
            "- themes: 主题分析对象数组，每个包含 name/score/analysis\n"
            "- domains: 六大领域分析（事业/感情/家庭/财富/健康/个人成长），每个含 score(0-100) 和 analysis\n"
            "- suggestions: 年度行动建议数组（3-5条）\n"
            "- source_refs: 引用的参考编号及中文概括"
        ),
    },

    # ── 出生时间校正 ────────────────────────────────────────────────
    "analyze_rectification": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.5,
        "description": "出生时间校正候选分析",
        # Placeholders: {candidates_text} {life_events_text} {rag_context}
        "prompt_template": (
            "请分析以下出生时间候选方案，结合人生事件进行校正评估。\n\n"
            "【候选出生时间】\n{candidates_text}\n\n"
            "【人生重要事件】\n{life_events_text}\n\n"
            "{rag_context}\n\n"
            "请以JSON格式返回分析结果，包含：\n"
            "- candidates: [{{rank, reason}}, ...] 每个候选方案的排名和理由\n"
            "- overall: 综合推荐说明\n"
            "- ai_recommended_rank: AI推荐的候选方案编号（1-based）"
        ),
    },

    # ── 上升星座辨别测验 ────────────────────────────────────────────
    "generate_asc_quiz": {
        "system_instruction": None,
        "temperature": 0.6,
        "description": "生成区分上升星座的多选题",
        # Placeholders: {candidates_str} {rag_context}
        "prompt_template": (
            "请生成5道选择题，帮助区分以下上升星座候选方案：{candidates_str}\n\n"
            "{rag_context}\n\n"
            "每道题应该能有效区分这些上升星座的典型特征。\n"
            "以JSON格式返回：{{\"questions\": [{{\"question\": \"...\", \"options\": [\"A...\", \"B...\", \"C...\", \"D...\"], \"key\": \"A\"}}]}}"
        ),
    },

    # ── 占星骰子：主解读 ────────────────────────────────────────────
    "astro_dice": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.6,
        "description": "占星骰子主解读（三骰 + 用户问题 → 个性化指引）",
        # Placeholders: {question} {category} {planet_name} {sign_name}
        #               {house_number} {core_sentence} {keywords}
        # Caller appends rag_context via rag_generate()
        "prompt_template": (
            "用户问题：{question}\n"
            "问题类别：{category}\n\n"
            "骰子结果：{planet_name} ＋ {sign_name} ＋ 第{house_number}宫\n"
            "核心含义：{core_sentence}\n"
            "关键词：{keywords}\n\n"
            "请根据以上占星骰子结果，针对用户问题给出解读。\n"
            "要求：\n"
            "- 核心解读 100-150 字，结合骰子三要素（能量/方式/领域）与问题本身\n"
            "- 给出一条具体可执行的行动建议（以【建议：】开头）\n"
            "- 语气温和、使用概率性表达（如：可能、倾向于），避免绝对断言\n"
            "- 严禁脱离骰子结果泛泛而谈"
        ),
    },

    # ── 占星骰子：追问解读 ──────────────────────────────────────────
    "astro_dice_followup": {
        "system_instruction": _SYSTEM_PROMPT_UNIFIED,
        "temperature": 0.6,
        "description": "占星骰子追问解读（新行星+宫位，原星座作背景，结合原始问题）",
        # Placeholders: {original_question} {followup_question} {category}
        #               {original_core} {original_planet} {original_sign}
        #               {new_planet} {new_house} {new_core} {keywords}
        "prompt_template": (
            "原始问题：{original_question}\n"
            "追问方向：{followup_question}\n"
            "问题类别：{category}\n\n"
            "原始骰子背景：{original_core}\n"
            "（原始能量：{original_planet} ＋ {original_sign}）\n\n"
            "追问新骰子：{new_planet} ＋ 第{new_house}宫（星座风格沿用原始）\n"
            "新核心含义：{new_core}\n"
            "关键词：{keywords}\n\n"
            "请在原始解读背景下，针对追问方向给出进一步解读。\n"
            "要求：\n"
            "- 明确呼应追问方向，不重复原始解读\n"
            "- 核心解读 80-120 字\n"
            "- 给出一条针对追问的具体建议（以【进一步建议：】开头）\n"
            "- 语气温和，使用概率性表达"
        ),
    },

    # ── 出生时间置信度 ──────────────────────────────────────────────
    "calc_confidence": {
        "system_instruction": None,
        "temperature": 0.4,
        "description": "计算出生时间校正置信度",
        # Placeholders: {candidate_text} {quiz_results_text} {rag_context}
        "prompt_template": (
            "请根据以下信息评估出生时间候选方案的置信度：\n\n"
            "【候选方案】\n{candidate_text}\n\n"
            "【测验结果】\n{quiz_results_text}\n\n"
            "{rag_context}\n\n"
            "以JSON格式返回：{{\"score\": <0-100>, \"label\": \"<high|mid|low>\", \"analysis\": \"<分析说明>\"}}"
        ),
    },
}
