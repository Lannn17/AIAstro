# Prompt Log Persistence — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract all AI prompts into a central registry, persist every AI call to Turso, and build admin API endpoints for prompt versioning, test runs, and evaluation.

**Architecture:** `prompt_registry.py` is the single source of truth for all prompt templates; each business function imports from it. `db.py` gains 4 new tables and helper functions. `client.py` fires an async best-effort write to `prompt_logs` after every AI call. Admin endpoints live in `admin_router.py`; user-facing endpoints in a new `user_router.py`.

**Tech Stack:** FastAPI, Turso HTTP (`_turso_exec` + `_to_dicts` pattern from `db.py`), `uuid`, existing `require_auth` dependency.

> **Turso query pattern:** `db.py` uses `_to_dicts(_turso_exec(sql, params))` for SELECT and `_turso_exec(sql, params)` for INSERT/UPDATE. Task 6 adds a thin `_turso_query` wrapper to reduce repetition — all new helpers call it. This project is Turso-only; no SQLite branch needed.

**Spec:** `docs/superpowers/specs/2026-04-01-prompt-log-persistence-design.md`

---

### Task 1: Create `prompt_registry.py` with all prompt templates

**Files:**
- Create: `astrology_api/app/rag/prompt_registry.py`

> Key rule: templates use named `{placeholder}` syntax filled via `.format(**kwargs)` in the calling function. Sections containing raw JSON braces (the `transits_full` prompts) already escape them as `{{` / `}}` in the original f-strings — preserve that. Dynamic computed strings (like `chr(10).join(lines)`) become simple `{variable_name}` placeholders; callers pre-compute them.

- [ ] **Step 1: Create the file with the PROMPTS dict**

```python
# astrology_api/app/rag/prompt_registry.py
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
            "**对"需要新解读"的每条行运**（约 150-250 字/条）：\n"
            "- 结合本命盘中该行星的星座、宫位\n"
            "- 说明具体影响的生活领域\n"
            "- 若为逆行周期，点明三次过境节奏\n"
            "- 给出 tone（顺势/挑战/转化 之一）和 themes（从"事业、感情、家庭、财务、健康、自我成长、人际关系、创意、精神"中选 1-3 个）\n\n"
            "**整体行运综述**（约 300-400 字，基于所有活跃行运）：\n"
            "- 开头先点出当前阶段主要影响的人生命题（1-2 句）\n"
            "- 识别主题叠加（多个相位指向同一领域则标注"已获多重星象确认"）\n"
            "- 给出具体行动建议\n"
            "- 语言自然，避免机械罗列\n\n"
            "JSON 格式返回（aspects 只包含"需要新解读"的行运）：\n"
            "{{\n"
            '  "aspects": [\n'
            "    {{\n"
            '      "key": "<与上方 key 完全一致>",\n'
            '      "analysis": "<150-250字解读>",\n'
            '      "tone": "<顺势|挑战|转化>",\n'
            '      "themes": ["<主题1>", "<主题2>"]\n'
            "    }}\n"
            "  ],\n"
            '  "overall": "<整体综述>",\n'
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
            "- 识别主题叠加（多个相位指向同一领域则标注"已获多重星象确认"）\n"
            "- 给出具体行动建议\n"
            "- 语言自然，避免机械罗列\n\n"
            '{{"overall": "<整体综述>", {source_refs_schema}}}\n'
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
            "- 概率分反映"这段关系的能量自然倾向"，不是主观建议\n"
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
            "- candidates: [{rank, reason}, ...] 每个候选方案的排名和理由\n"
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
```

- [ ] **Step 2: Verify the file imports without error**

```bash
cd astrology_api && python -c "from app.rag.prompt_registry import PROMPTS; print(list(PROMPTS.keys()))"
```

Expected output: list of 12 caller keys without ImportError

- [ ] **Step 3: Commit**

```bash
git add astrology_api/app/rag/prompt_registry.py
git commit -m "feat(prompts): add central prompt_registry with all 12 caller templates"
```

---

### Task 2: Refactor `planets.py` to use registry

**Files:**
- Modify: `astrology_api/app/rag/planets.py` (around lines 238-281)

- [ ] **Step 1: Replace inline prompt construction with registry import**

At top of `planets.py`, add:
```python
from .prompt_registry import PROMPTS as _PROMPTS
```

Find the block starting at line 238 (`prompt = f"""请为以下本命盘行星位置...`). Replace the entire `prompt = f"""..."""` block with:

```python
_tmpl = _PROMPTS["interpret_planets"]["prompt_template"]
prompt = _tmpl.format(
    asc_sign=asc_sign,
    dsc_sign=dsc_sign,
    mc_sign=mc_sign,
    ic_sign=ic_sign,
    angles_section=angles_section,
    planet_list=planet_list,
    house_summary=house_summary,
    aspect_summary=aspect_summary,
    facts_section=facts_section,
) + json_template + rag_context
```

The `json_template` and `rag_context` variables are still computed in the function body above — they are just concatenated instead of interpolated.

- [ ] **Step 2: Test that planet analysis still works**

Start the backend and call:
```bash
curl -X POST http://127.0.0.1:8001/api/interpret_planets \
  -H "Content-Type: application/json" \
  -d '{"chart_id": 1}'
```
Expected: JSON response with planet analyses (same as before refactor)

- [ ] **Step 3: Commit**

```bash
git add astrology_api/app/rag/planets.py
git commit -m "refactor(planets): use prompt_registry for interpret_planets template"
```

---

### Task 3: Refactor `transit.py` to use registry

**Files:**
- Modify: `astrology_api/app/rag/transit.py` (lines 76-91 and 201-259)

- [ ] **Step 1: Add import at top of transit.py**

```python
from .prompt_registry import PROMPTS as _PROMPTS
```

- [ ] **Step 2: Replace `analyze_transits` inline prompt (lines 76-91)**

Pre-compute joined strings before the prompt:
```python
planet_lines_str = chr(10).join(planet_lines) or '（无数据）'
aspect_lines_str = chr(10).join(aspect_lines) or '（无相位）'
_tmpl = _PROMPTS["transits_single"]["prompt_template"]
prompt = _tmpl.format(
    transit_date=transit_date,
    chart_summary=chart_summary,
    planet_lines_str=planet_lines_str,
    aspect_lines_str=aspect_lines_str,
)
```

- [ ] **Step 3: Replace `analyze_active_transits_full` new-transits prompt (around line 201)**

```python
_tmpl_new = _PROMPTS["transits_full_new"]["prompt_template"]
prompt = _tmpl_new.format(
    chart_summary=chart_summary,
    query_date=query_date,
    all_block=all_block,
    new_block=new_block,
    rag_context=rag_context,
    source_refs_schema=source_refs_schema,
)
```

- [ ] **Step 4: Replace cached-only prompt (around line 243)**

```python
_tmpl_sum = _PROMPTS["transits_full_summary"]["prompt_template"]
prompt = _tmpl_sum.format(
    chart_summary=chart_summary,
    query_date=query_date,
    all_block=all_block,
    rag_context=rag_context,
    source_refs_schema=source_refs_schema,
)
```

- [ ] **Step 5: Test transit endpoints**

```bash
curl -X POST http://127.0.0.1:8001/api/transit_chart \
  -H "Content-Type: application/json" \
  -d '{"chart_id": 1, "transit_date": "2026-04-01"}'
```
Expected: transit analysis JSON, same output format as before

- [ ] **Step 6: Commit**

```bash
git add astrology_api/app/rag/transit.py
git commit -m "refactor(transit): use prompt_registry for transits_single and transits_full templates"
```

---

### Task 4: Refactor `chat.py`, `synastry.py`, `solar_return.py`, `rectification.py`

**Files:**
- Modify: `astrology_api/app/rag/chat.py`
- Modify: `astrology_api/app/rag/synastry.py`
- Modify: `astrology_api/app/rag/solar_return.py`
- Modify: `astrology_api/app/rag/rectification.py`

- [ ] **Step 1: Refactor `chat.py` — `generate()` function (lines 17-33)**

Add import, replace inline prompt:
```python
from .prompt_registry import PROMPTS as _PROMPTS

# In generate():
context = "\n\n".join(context_parts)
_tmpl = _PROMPTS["generate"]["prompt_template"]
prompt = _tmpl.format(context=context, query=query)
```

- [ ] **Step 2: Refactor `chat.py` — `chat_with_chart()` base_prompt (lines ~169-189)**

```python
_tmpl = _PROMPTS["chat_with_chart"]["prompt_template"]
base_prompt = _tmpl.format(
    chart_summary=chart_summary,
    transit_context=transit_context,  # "" if not applicable
)
```
The rag section is still appended via `_build_rag_section(chunks)` after this.

- [ ] **Step 3: Refactor `synastry.py`**

```python
from .prompt_registry import PROMPTS as _PROMPTS

# In analyze_synastry():
import json as _json
context_json = _json.dumps(context, ensure_ascii=False, indent=2)
_tmpl = _PROMPTS["analyze_synastry"]["prompt_template"]
prompt = _tmpl.format(rag_context=rag_context, context_json=context_json)
```

- [ ] **Step 4: Refactor `solar_return.py`**

```python
from .prompt_registry import PROMPTS as _PROMPTS

# In analyze_solar_return():
_tmpl = _PROMPTS["analyze_solar_return"]["prompt_template"]
prompt = _tmpl.format(
    name=name,
    sr_year=sr_year,
    sr_summary=sr_summary,
    natal_summary=natal_summary,
    theme_scores_text=theme_scores_text,
    facts_text=facts_text,
    modifiers_text=modifiers_text,
)
# prompt is then passed to rag_generate(rag_query, prompt)
```

- [ ] **Step 5: Refactor `rectification.py` (3 functions)**

```python
from .prompt_registry import PROMPTS as _PROMPTS

# analyze_rectification():
_tmpl = _PROMPTS["analyze_rectification"]["prompt_template"]
prompt = _tmpl.format(
    candidates_text=candidates_text,
    life_events_text=life_events_text,
    rag_context=rag_context,
)

# generate_asc_quiz():
_tmpl = _PROMPTS["generate_asc_quiz"]["prompt_template"]
prompt = _tmpl.format(candidates_str=candidates_str, rag_context=rag_context)

# calc_confidence():
_tmpl = _PROMPTS["calc_confidence"]["prompt_template"]
prompt = _tmpl.format(
    candidate_text=candidate_text,
    quiz_results_text=quiz_results_text,
    rag_context=rag_context,
)
```

- [ ] **Step 6: Smoke-test affected endpoints**

```bash
curl -X POST http://127.0.0.1:8001/api/synastry -H "Content-Type: application/json" \
  -d '{"chart_id1": 1, "chart_id2": 2}'
```
Expected: response in same format as before (no 500 errors)

- [ ] **Step 7: Commit**

```bash
git add astrology_api/app/rag/chat.py astrology_api/app/rag/synastry.py \
        astrology_api/app/rag/solar_return.py astrology_api/app/rag/rectification.py
git commit -m "refactor(rag): use prompt_registry in chat, synastry, solar_return, rectification"
```

---

### Task 5: Add 4 new DB tables to `db.py`

**Files:**
- Modify: `astrology_api/app/db.py`

- [ ] **Step 1: Add DDL constants after `_CREATE_SR_CACHE` (after line 102)**

```python
_CREATE_PROMPT_VERSIONS = """
CREATE TABLE IF NOT EXISTS prompt_versions (
    id TEXT PRIMARY KEY,
    caller TEXT NOT NULL,
    version_tag TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    system_instruction TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    deployed_at TEXT,
    UNIQUE(caller, version_tag)
)
"""

_CREATE_PROMPT_LOGS = """
CREATE TABLE IF NOT EXISTS prompt_logs (
    id TEXT PRIMARY KEY,
    version_id TEXT,
    source TEXT NOT NULL,
    input_data TEXT,
    rag_query TEXT,
    rag_chunks TEXT,
    response_text TEXT,
    latency_ms INTEGER,
    model_used TEXT,
    temperature REAL,
    finish_reason TEXT,
    prompt_tokens_est INTEGER,
    response_tokens_est INTEGER,
    user_id TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_PROMPT_EVALUATIONS = """
CREATE TABLE IF NOT EXISTS prompt_evaluations (
    id TEXT PRIMARY KEY,
    log_id TEXT NOT NULL,
    version_id TEXT,
    compared_to_log_id TEXT,
    evaluator_type TEXT NOT NULL,
    score_overall REAL,
    dimensions TEXT,
    notes TEXT,
    suggestions TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_USER_FEEDBACK = """
CREATE TABLE IF NOT EXISTS user_feedback (
    id TEXT PRIMARY KEY,
    caller TEXT,
    content TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL
)
"""
```

- [ ] **Step 2: Add all 4 tables to `create_tables()`**

Find the `for ddl in [...]` loop in `create_tables()`. Add the 4 new DDL constants to that list:

```python
for ddl in [_CREATE_TABLE, _CREATE_TRANSIT_CACHE, _CREATE_TRANSIT_OVERALL,
            _CREATE_PLANET_CACHE, _CREATE_SYNASTRY_CACHE, _CREATE_QUERY_ANALYTICS,
            _CREATE_LIFE_EVENTS, _CREATE_SR_CACHE,
            _CREATE_PROMPT_VERSIONS, _CREATE_PROMPT_LOGS,
            _CREATE_PROMPT_EVALUATIONS, _CREATE_USER_FEEDBACK]:
    if USE_TURSO:
        _turso_exec(ddl)
    else:
        ...
```

- [ ] **Step 3: Restart backend and verify tables created**

Restart uvicorn. Check Turso console or run:
```bash
curl -s http://127.0.0.1:8001/docs | grep -c "200"
```
Backend should start without errors. Tables will be created on first run.

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/db.py
git commit -m "feat(db): add prompt_versions, prompt_logs, prompt_evaluations, user_feedback tables"
```

---

### Task 6: Add DB helper functions for `prompt_versions`

**Files:**
- Modify: `astrology_api/app/db.py`

Add these functions at the end of `db.py`:

- [ ] **Step 1: Add `_turso_query` convenience wrapper (add right after `_to_dicts`)**

```python
def _turso_query(sql: str, params: list = None) -> list[dict]:
    """SELECT helper: execute sql and return rows as list[dict]."""
    return _to_dicts(_turso_exec(sql, params or []))
```

This wrapper is used by all new read helpers below.

- [ ] **Step 2: Add `db_insert_prompt_version`**

```python
def db_insert_prompt_version(
    id_: str, caller: str, version_tag: str,
    prompt_text: str, system_instruction: str | None,
    status: str = "draft", deployed_at: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = """INSERT INTO prompt_versions
             (id, caller, version_tag, prompt_text, system_instruction,
              status, created_at, deployed_at)
             VALUES (?,?,?,?,?,?,?,?)"""
    args = [id_, caller, version_tag, prompt_text, system_instruction,
            status, now, deployed_at]
    if USE_TURSO:
        _turso_exec(sql, args)
```

- [ ] **Step 2: Add `db_get_deployed_version`**

```python
def db_get_deployed_version(caller: str) -> dict | None:
    """Return the current deployed version for a caller, or None."""
    sql = "SELECT * FROM prompt_versions WHERE caller=? AND status='deployed' LIMIT 1"
    rows = _turso_query(sql, [caller])
    return rows[0] if rows else None
```

- [ ] **Step 3: Add `db_list_prompt_versions`**

```python
def db_list_prompt_versions(caller: str | None = None) -> list[dict]:
    if caller:
        sql = "SELECT * FROM prompt_versions WHERE caller=? ORDER BY created_at DESC"
        return _turso_query(sql, [caller])
    return _turso_query("SELECT * FROM prompt_versions ORDER BY created_at DESC", [])
```

- [ ] **Step 4: Add `db_get_prompt_version`**

```python
def db_get_prompt_version(id_: str) -> dict | None:
    rows = _turso_query("SELECT * FROM prompt_versions WHERE id=?", [id_])
    return rows[0] if rows else None
```

- [ ] **Step 5: Add `db_update_prompt_version`**

```python
def db_update_prompt_version(id_: str, **fields) -> None:
    """Update arbitrary fields on a prompt_version row. fields: status, version_tag, deployed_at, prompt_text, system_instruction."""
    allowed = {"status", "version_tag", "deployed_at", "prompt_text", "system_instruction"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    sql = f"UPDATE prompt_versions SET {set_clause} WHERE id=?"
    if USE_TURSO:
        _turso_exec(sql, list(updates.values()) + [id_])
```

- [ ] **Step 6: Add `db_get_all_deployed_versions`**

```python
def db_get_all_deployed_versions() -> list[dict]:
    """Used at startup to warm the _deployed_version_cache."""
    return _turso_query(
        "SELECT id, caller FROM prompt_versions WHERE status='deployed'", []
    )
```

- [ ] **Step 8: Verify the module still imports cleanly**

```bash
cd astrology_api && python -c "from app.db import db_insert_prompt_version, db_get_deployed_version; print('OK')"
```

- [ ] **Step 9: Commit**

```bash
git add astrology_api/app/db.py
git commit -m "feat(db): add _turso_query helper + prompt_versions CRUD helpers"
```

---

### Task 7: Add DB helpers for `prompt_logs`, `prompt_evaluations`, `user_feedback`

**Files:**
- Modify: `astrology_api/app/db.py`

- [ ] **Step 1: Add `db_insert_prompt_log`**

```python
def db_insert_prompt_log(
    id_: str, version_id: str | None, source: str,
    input_data: str | None, rag_query: str, rag_chunks: str,
    response_text: str, latency_ms: int, model_used: str,
    temperature: float, finish_reason: str,
    prompt_tokens_est: int, response_tokens_est: int,
    user_id: str | None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = """INSERT INTO prompt_logs
             (id, version_id, source, input_data, rag_query, rag_chunks,
              response_text, latency_ms, model_used, temperature, finish_reason,
              prompt_tokens_est, response_tokens_est, user_id, created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    args = [id_, version_id, source, input_data, rag_query, rag_chunks,
            response_text, latency_ms, model_used, temperature, finish_reason,
            prompt_tokens_est, response_tokens_est, user_id, now]
    if USE_TURSO:
        _turso_exec(sql, args)
```

- [ ] **Step 2: Add `db_query_prompt_logs`**

```python
def db_query_prompt_logs(
    version_id: str | None = None,
    caller: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions, args = [], []
    if version_id:
        conditions.append("pl.version_id=?"); args.append(version_id)
    if caller:
        conditions.append("pv.caller=?"); args.append(caller)
    if source:
        conditions.append("pl.source=?"); args.append(source)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""SELECT pl.* FROM prompt_logs pl
              LEFT JOIN prompt_versions pv ON pl.version_id=pv.id
              {where} ORDER BY pl.created_at DESC LIMIT ?"""
    args.append(limit)
    return _turso_query(sql, args)
```

- [ ] **Step 3: Add `db_get_recent_log_for_version`**

```python
def db_get_recent_log_for_version(version_id: str, source: str | None = None) -> dict | None:
    """Get most recent log for a version, optionally filtered by source."""
    if source:
        rows = _turso_query(
            "SELECT * FROM prompt_logs WHERE version_id=? AND source=? ORDER BY created_at DESC LIMIT 1",
            [version_id, source]
        )
    else:
        rows = _turso_query(
            "SELECT * FROM prompt_logs WHERE version_id=? ORDER BY created_at DESC LIMIT 1",
            [version_id]
        )
    return rows[0] if rows else None
```

- [ ] **Step 4: Add `db_insert_prompt_evaluation`**

```python
def db_insert_prompt_evaluation(
    id_: str, log_id: str, version_id: str | None,
    evaluator_type: str, score_overall: float | None,
    dimensions: str | None, notes: str | None,
    suggestions: str | None, compared_to_log_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = """INSERT INTO prompt_evaluations
             (id, log_id, version_id, compared_to_log_id, evaluator_type,
              score_overall, dimensions, notes, suggestions, created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?)"""
    args = [id_, log_id, version_id, compared_to_log_id, evaluator_type,
            score_overall, dimensions, notes, suggestions, now]
    if USE_TURSO:
        _turso_exec(sql, args)
```

- [ ] **Step 5: Add `db_get_evaluations_for_log` and `db_get_evaluations_for_version`**

```python
def db_get_evaluations_for_log(log_id: str) -> list[dict]:
    return _turso_query(
        "SELECT * FROM prompt_evaluations WHERE log_id=? ORDER BY created_at DESC",
        [log_id]
    )

def db_get_evaluations_for_version(version_id: str) -> list[dict]:
    return _turso_query(
        "SELECT * FROM prompt_evaluations WHERE version_id=? ORDER BY created_at DESC",
        [version_id]
    )
```

- [ ] **Step 6: Add `db_insert_user_feedback`**

```python
def db_insert_user_feedback(
    id_: str, caller: str | None, content: str, user_id: str | None
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = "INSERT INTO user_feedback (id, caller, content, user_id, created_at) VALUES (?,?,?,?,?)"
    if USE_TURSO:
        _turso_exec(sql, [id_, caller, content, user_id, now])
```

- [ ] **Step 7: Verify imports**

```bash
cd astrology_api && python -c "from app.db import db_insert_prompt_log, db_insert_prompt_evaluation, db_insert_user_feedback; print('OK')"
```

- [ ] **Step 8: Commit**

```bash
git add astrology_api/app/db.py
git commit -m "feat(db): add prompt_logs, prompt_evaluations, user_feedback helpers"
```

---

### Task 8: Add `_deployed_version_cache` + startup warm-up

**Files:**
- Create: `astrology_api/app/prompt_version_cache.py`
- Modify: `astrology_api/app/db.py` (add warm-up call in `create_tables`)

- [ ] **Step 1: Create `prompt_version_cache.py`**

```python
# astrology_api/app/prompt_version_cache.py
"""
In-memory cache: {caller: version_id} for the currently deployed prompt version.
Warmed at startup from DB. Updated on every deploy action.
"""
import threading

_cache: dict[str, str] = {}
_lock = threading.Lock()


def warm_cache(deployed_rows: list[dict]) -> None:
    """Called at startup with rows from db_get_all_deployed_versions()."""
    with _lock:
        _cache.clear()
        for row in deployed_rows:
            _cache[row["caller"]] = row["id"]


def get_version_id(caller: str) -> str | None:
    with _lock:
        return _cache.get(caller)


def set_version_id(caller: str, version_id: str) -> None:
    with _lock:
        _cache[caller] = version_id


def remove_caller(caller: str) -> None:
    with _lock:
        _cache.pop(caller, None)
```

- [ ] **Step 2: Call `warm_cache` in `create_tables()` in `db.py`**

At the end of `create_tables()`, add:
```python
    # Warm the deployed-version cache
    try:
        from .prompt_version_cache import warm_cache
        warm_cache(db_get_all_deployed_versions())
        print("[DB] prompt_version_cache warmed")
    except Exception as e:
        print(f"[WARN] Failed to warm prompt_version_cache: {e}")
```

- [ ] **Step 3: Verify warm-up works**

Restart backend. Check for `[DB] prompt_version_cache warmed` in stdout (will show empty cache until seed is done).

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/prompt_version_cache.py astrology_api/app/db.py
git commit -m "feat(cache): add deployed_version_cache with startup warm-up"
```

---

### Task 9: Add `db_seed.py` — auto-seed v1 from registry

**Files:**
- Create: `astrology_api/app/db_seed.py`
- Modify: `astrology_api/app/db.py` (`create_tables` calls seed)

- [ ] **Step 1: Create `db_seed.py`**

```python
# astrology_api/app/db_seed.py
"""
Seeds prompt_versions with v1 entries from prompt_registry.
Runs at startup (called from create_tables). Skips callers that already have a deployed version.
"""
import uuid
from datetime import datetime, timezone

from .db import db_get_deployed_version, db_insert_prompt_version


def seed_prompt_versions() -> None:
    from .rag.prompt_registry import PROMPTS

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for caller, cfg in PROMPTS.items():
        existing = db_get_deployed_version(caller)
        if existing:
            continue  # already seeded
        id_ = uuid.uuid4().hex[:16]
        db_insert_prompt_version(
            id_=id_,
            caller=caller,
            version_tag="v1",
            prompt_text=cfg["prompt_template"],
            system_instruction=cfg.get("system_instruction") or "",
            status="deployed",
            deployed_at=now,
        )
        print(f"[Seed] Seeded prompt_versions: {caller} v1")
```

- [ ] **Step 2: Call `seed_prompt_versions` in `create_tables()` after warm-up**

```python
    # Seed v1 from prompt_registry
    try:
        from .db_seed import seed_prompt_versions
        seed_prompt_versions()
    except Exception as e:
        print(f"[WARN] Seed failed: {e}")
    # Re-warm cache after seeding
    try:
        from .prompt_version_cache import warm_cache
        warm_cache(db_get_all_deployed_versions())
    except Exception as e:
        print(f"[WARN] Re-warm after seed failed: {e}")
```

- [ ] **Step 3: Restart backend and verify seed**

Check stdout for `[Seed] Seeded prompt_versions: interpret_planets v1` etc. (12 lines, one per caller).

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/db_seed.py astrology_api/app/db.py
git commit -m "feat(seed): auto-seed prompt_versions v1 from registry at startup"
```

---

### Task 10: Update `PromptLogEntry` + wire async persistence in `client.py`

**Files:**
- Modify: `astrology_api/app/prompt_log.py`
- Modify: `astrology_api/app/rag/client.py`

- [ ] **Step 1: Add `version_id` field to `PromptLogEntry` in `prompt_log.py`**

In the `PromptLogEntry` dataclass, after the `caller: str = ""` line, add:
```python
version_id: str = ""
```

- [ ] **Step 2: Populate `version_id` in `client.py` when building the log entry**

In `generate_content()` in `client.py`, after `entry = PromptLogEntry(...)` and `entry.caller = self._guess_caller()`:
```python
from ..prompt_version_cache import get_version_id as _get_version_id
entry.version_id = _get_version_id(entry.caller) or ""
```

- [ ] **Step 3: Add synchronous DB write after each `prompt_store.append(entry)` call**

> **Why synchronous, not async:** `generate_content()` is a regular sync method. `asyncio.create_task()` requires a running event loop and raises `RuntimeError` from a sync context. `_turso_exec` is already a blocking HTTP call (uses `requests.post`) — wrapping it in `async` adds no benefit. Use a plain try/except instead, matching the `_log_analytics` pattern used elsewhere in this codebase.

Add the helper at module level in `client.py`:
```python
def _persist_prompt_log(entry) -> None:
    """Best-effort sync write of PromptLogEntry to Turso prompt_logs."""
    try:
        import json as _json, uuid as _uuid
        from ..db import db_insert_prompt_log
        db_insert_prompt_log(
            id_=_uuid.uuid4().hex[:16],
            version_id=entry.version_id or None,
            source="production",
            input_data=None,
            rag_query=entry.rag_query,
            rag_chunks=_json.dumps(entry.rag_chunks, ensure_ascii=False)[:4000],
            response_text=entry.response_text[:5000],
            latency_ms=entry.latency_ms,
            model_used=entry.model_used,
            temperature=entry.temperature,
            finish_reason=entry.finish_reason,
            prompt_tokens_est=entry.prompt_tokens_est,
            response_tokens_est=entry.response_tokens_est,
            user_id=None,
        )
    except Exception as e:
        print(f"[PromptLog] persist failed: {e}", flush=True)
```

There are 4 places in `generate_content()` that call `prompt_store.append(entry)`. After **each one**, add:

```python
prompt_store.append(entry)
_persist_prompt_log(entry)
```

- [ ] **Step 4: Verify no regression**

Restart backend, make any AI analysis call. Check that:
1. Call returns normally (async write doesn't block)
2. No new error logs appear in stdout for prompt_log persistence

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/prompt_log.py astrology_api/app/rag/client.py
git commit -m "feat(log): persist prompt logs to Turso asynchronously after each AI call"
```

---

### Task 11: Admin router — prompt versions CRUD

**Files:**
- Modify: `astrology_api/app/api/admin_router.py`

- [ ] **Step 1: Add imports at top of `admin_router.py`**

```python
import uuid
import json
from datetime import datetime, timezone
from pydantic import BaseModel
from ..db import (
    db_list_prompt_versions, db_get_prompt_version,
    db_insert_prompt_version, db_update_prompt_version,
    db_get_deployed_version, db_get_chart,
)
from ..prompt_version_cache import set_version_id as _cache_set
```

- [ ] **Step 2: Add request schemas**

```python
class CreateDraftRequest(BaseModel):
    caller: str
    prompt_text: str
    system_instruction: str = ""

class PatchDraftRequest(BaseModel):
    prompt_text: str | None = None
    system_instruction: str | None = None
```

- [ ] **Step 3: Add `GET /api/admin/prompt-versions`**

```python
@router.get("/prompt-versions")
def list_prompt_versions(caller: str | None = None, _user: str = Depends(require_auth)):
    return db_list_prompt_versions(caller=caller)
```

- [ ] **Step 4: Add `POST /api/admin/prompt-versions` (create draft)**

```python
@router.post("/prompt-versions")
def create_draft(body: CreateDraftRequest, _user: str = Depends(require_auth)):
    deployed = db_get_deployed_version(body.caller)
    # Determine next draft tag: v1.1 if deployed is v1, etc.
    if deployed:
        base = deployed["version_tag"]  # e.g. "v1"
        # Find highest existing draft minor for this base
        all_versions = db_list_prompt_versions(caller=body.caller)
        prefix = base + "."
        minors = [
            int(v["version_tag"].split(".")[-1])
            for v in all_versions
            if v["version_tag"].startswith(prefix) and v["version_tag"].split(".")[-1].isdigit()
        ]
        next_minor = max(minors, default=0) + 1
        version_tag = f"{base}.{next_minor}"
    else:
        version_tag = "v1"

    id_ = uuid.uuid4().hex[:16]
    db_insert_prompt_version(
        id_=id_,
        caller=body.caller,
        version_tag=version_tag,
        prompt_text=body.prompt_text,
        system_instruction=body.system_instruction or None,
        status="draft" if deployed else "deployed",
        deployed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if not deployed else None,
    )
    if not deployed:
        _cache_set(body.caller, id_)
    return db_get_prompt_version(id_)
```

- [ ] **Step 5: Add `GET /api/admin/prompt-versions/{id}` and `PATCH`**

```python
@router.get("/prompt-versions/{id}")
def get_prompt_version(id: str, _user: str = Depends(require_auth)):
    v = db_get_prompt_version(id)
    if not v:
        raise HTTPException(404, "Not found")
    return v

@router.patch("/prompt-versions/{id}")
def patch_draft(id: str, body: PatchDraftRequest, _user: str = Depends(require_auth)):
    v = db_get_prompt_version(id)
    if not v:
        raise HTTPException(404, "Not found")
    if v["status"] != "draft":
        raise HTTPException(400, "Only draft versions can be edited")
    updates = {}
    if body.prompt_text is not None:
        updates["prompt_text"] = body.prompt_text
    if body.system_instruction is not None:
        updates["system_instruction"] = body.system_instruction
    if updates:
        db_update_prompt_version(id, **updates)
    return db_get_prompt_version(id)
```

- [ ] **Step 6: Verify via Swagger**

Visit `http://127.0.0.1:8001/docs`, authenticate, and call `GET /api/admin/prompt-versions`. Should return seeded v1 entries.

- [ ] **Step 7: Commit**

```bash
git add astrology_api/app/api/admin_router.py
git commit -m "feat(admin): add prompt-versions CRUD endpoints (list, create, get, patch)"
```

---

### Task 12: Admin router — `run-test` + AI evaluation

**Files:**
- Modify: `astrology_api/app/api/admin_router.py`

- [ ] **Step 1: Add imports and request schema**

```python
from ..db import (
    db_get_prompt_version, db_insert_prompt_log,
    db_insert_prompt_evaluation, db_get_evaluations_for_log,
    db_get_recent_log_for_version,
)
from .. import rag
from ..rag import GENERATE_MODEL
from google.genai import types as _gtypes
import asyncio

class RunTestRequest(BaseModel):
    chart_id: int
```

- [ ] **Step 2: Add the AI evaluation helper**

```python
def _run_ai_evaluation(
    test_log_id: str, test_response: str, version_id: str,
    deployed_log: dict | None,
) -> list[dict]:
    """
    Runs ai_absolute and (if deployed_log exists) ai_comparative evaluations.
    Returns list of inserted evaluation dicts.
    """
    results = []

    # 1. Absolute evaluation
    abs_prompt = f"""请对以下占星 AI 分析输出进行质量评估。

【输出内容】
{test_response[:3000]}

请以 JSON 格式返回：
{{
  "score_overall": <1-5的浮点数>,
  "dimensions": {{"accuracy": <1-5>, "readability": <1-5>, "astro_quality": <1-5>}},
  "notes": "<100字以内的综合评价>",
  "suggestions": ["<改进建议1>", "<改进建议2>"]
}}
suggestions 在 score_overall < 3.5 时必须填写至少2条。"""

    try:
        resp = rag.client.models.generate_content(
            model=GENERATE_MODEL,
            contents=abs_prompt,
            config=_gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        data = json.loads(resp.text)
        eval_id = uuid.uuid4().hex[:16]
        db_insert_prompt_evaluation(
            id_=eval_id, log_id=test_log_id, version_id=version_id,
            evaluator_type="ai_absolute",
            score_overall=data.get("score_overall"),
            dimensions=json.dumps(data.get("dimensions"), ensure_ascii=False),
            notes=data.get("notes"),
            suggestions=json.dumps(data.get("suggestions", []), ensure_ascii=False),
        )
        results.append({"type": "ai_absolute", **data})
    except Exception as e:
        print(f"[eval] ai_absolute failed: {e}")

    # 2. Comparative evaluation (if deployed log exists)
    if deployed_log:
        cmp_prompt = f"""请对比以下两个版本的占星 AI 分析输出质量。

【当前版本（草稿）输出】
{test_response[:2000]}

【上一版本（线上）输出】
{(deployed_log.get('response_text') or '')[:2000]}

请以 JSON 格式返回：
{{
  "score_overall": <1-5，草稿版本的综合评分>,
  "dimensions": {{"accuracy": <1-5>, "readability": <1-5>, "astro_quality": <1-5>}},
  "notes": "<100字以内，对比分析草稿相对上一版本的优劣>",
  "suggestions": ["<针对草稿的改进建议>"]
}}"""
        try:
            resp = rag.client.models.generate_content(
                model=GENERATE_MODEL,
                contents=cmp_prompt,
                config=_gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            data = json.loads(resp.text)
            eval_id = uuid.uuid4().hex[:16]
            db_insert_prompt_evaluation(
                id_=eval_id, log_id=test_log_id, version_id=version_id,
                evaluator_type="ai_comparative",
                score_overall=data.get("score_overall"),
                dimensions=json.dumps(data.get("dimensions"), ensure_ascii=False),
                notes=data.get("notes"),
                suggestions=json.dumps(data.get("suggestions", []), ensure_ascii=False),
                compared_to_log_id=deployed_log["id"],
            )
            results.append({"type": "ai_comparative", "compared_to_log_id": deployed_log["id"], **data})
        except Exception as e:
            print(f"[eval] ai_comparative failed: {e}")

    return results
```

- [ ] **Step 3: Add `POST /api/admin/prompt-versions/{id}/run-test`**

> The test runs the **draft's actual saved `prompt_text`** with real chart data. The chart summary is injected as `{chart_summary}` — the most universal placeholder across all callers. For callers that require additional variables (e.g. `planet_list`, `transit_date`), those placeholders are left unfilled and appear literally in the output; this is acceptable for a comparative quality test. The important thing is that both draft and deployed versions are tested identically, making the comparison valid.

```python
@router.post("/prompt-versions/{id}/run-test")
def run_test(id: str, body: RunTestRequest, _user: str = Depends(require_auth)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Version not found")
    if version["status"] != "draft":
        raise HTTPException(400, "Only draft versions can be tested")

    # Fetch chart data
    chart = db_get_chart(body.chart_id)
    if not chart:
        raise HTTPException(404, "Chart not found")

    chart_data = json.loads(chart.get("chart_data") or "{}")
    caller = version["caller"]

    try:
        from ..rag.prompt_registry import PROMPTS
        from ..rag.chart_summary import format_chart_summary
        cfg = PROMPTS.get(caller, {})
        chart_summary = format_chart_summary(chart_data)

        # Fill only {chart_summary}; remaining placeholders left as-is for test
        draft_prompt = version["prompt_text"]
        try:
            # Use format_map with a default-returning dict so unknown placeholders survive
            class _DefaultDict(dict):
                def __missing__(self, key): return "{" + key + "}"
            test_prompt = draft_prompt.format_map(_DefaultDict(chart_summary=chart_summary))
        except Exception:
            test_prompt = draft_prompt  # fallback: use raw template if format fails

        import time
        t0 = time.time()
        resp = rag.client.models.generate_content(
            model=GENERATE_MODEL,
            contents=test_prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=version.get("system_instruction") or None,
                temperature=cfg.get("temperature", 0.5),
            ),
        )
        latency_ms = int((time.time() - t0) * 1000)
        response_text = getattr(resp, "text", "") or ""
    except Exception as e:
        raise HTTPException(500, f"AI call failed: {e}")

    # Save test log
    log_id = uuid.uuid4().hex[:16]
    db_insert_prompt_log(
        id_=log_id, version_id=id, source="test",
        input_data=json.dumps({"chart_id": body.chart_id}, ensure_ascii=False),
        rag_query="", rag_chunks="[]",
        response_text=response_text[:5000],
        latency_ms=latency_ms, model_used=GENERATE_MODEL,
        temperature=cfg.get("temperature", 0.5),
        finish_reason="STOP", prompt_tokens_est=0, response_tokens_est=0,
        user_id=None,
    )

    # Find deployed version's most recent log for comparison
    deployed = db_get_deployed_version(caller)
    deployed_log = None
    if deployed:
        deployed_log = db_get_recent_log_for_version(deployed["id"], source="test")
        if not deployed_log:
            deployed_log = db_get_recent_log_for_version(deployed["id"])

    # Run AI evaluations
    evaluations = _run_ai_evaluation(log_id, response_text, id, deployed_log)

    return {
        "log_id": log_id,
        "response_text": response_text,
        "latency_ms": latency_ms,
        "evaluations": evaluations,
        "deployed_response": deployed_log.get("response_text") if deployed_log else None,
    }
```

- [ ] **Step 4: Add `GET /api/admin/prompt-logs` and `GET /api/admin/prompt-logs/{log_id}/evaluations`**

```python
@router.get("/prompt-logs")
def list_prompt_logs(
    version_id: str | None = None,
    caller: str | None = None,
    source: str | None = None,
    limit: int = 50,
    _user: str = Depends(require_auth),
):
    from ..db import db_query_prompt_logs
    return db_query_prompt_logs(version_id=version_id, caller=caller, source=source, limit=limit)

@router.get("/prompt-logs/{log_id}/evaluations")
def get_log_evaluations(log_id: str, _user: str = Depends(require_auth)):
    return db_get_evaluations_for_log(log_id)
```

- [ ] **Step 5: Add `POST /api/admin/prompt-evaluations` (admin manual evaluation)**

```python
class AdminEvalRequest(BaseModel):
    log_id: str
    score_overall: float | None = None
    dimensions: dict | None = None
    notes: str | None = None

@router.post("/prompt-evaluations")
def submit_admin_eval(body: AdminEvalRequest, _user: str = Depends(require_auth)):
    version_id = None
    try:
        from ..db import _turso_query
        rows = _turso_query("SELECT version_id FROM prompt_logs WHERE id=?", [body.log_id])
        version_id = rows[0]["version_id"] if rows else None
    except Exception:
        pass
    eval_id = uuid.uuid4().hex[:16]
    db_insert_prompt_evaluation(
        id_=eval_id, log_id=body.log_id, version_id=version_id,
        evaluator_type="admin",
        score_overall=body.score_overall,
        dimensions=json.dumps(body.dimensions, ensure_ascii=False) if body.dimensions else None,
        notes=body.notes,
        suggestions=None,
    )
    return {"id": eval_id, "status": "ok"}
```

- [ ] **Step 6: Verify via Swagger — run a test**

Call `POST /api/admin/prompt-versions/{draft_id}/run-test` with `{"chart_id": 1}`. Should return response_text + evaluations JSON.

- [ ] **Step 7: Commit**

```bash
git add astrology_api/app/api/admin_router.py
git commit -m "feat(admin): add run-test endpoint with AI absolute+comparative evaluation"
```

---

### Task 13: Admin router — `deploy`, `revise`, `compare`

**Files:**
- Modify: `astrology_api/app/api/admin_router.py`

- [ ] **Step 1: Add `POST /api/admin/prompt-versions/{id}/deploy`**

```python
@router.post("/prompt-versions/{id}/deploy")
def deploy_version(id: str, _user: str = Depends(require_auth)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Not found")
    if version["status"] != "draft":
        raise HTTPException(400, "Only draft can be deployed")

    caller = version["caller"]
    # Compute next major version tag
    all_versions = db_list_prompt_versions(caller=caller)
    major_tags = [
        int(v["version_tag"].lstrip("v"))
        for v in all_versions
        if v["version_tag"].startswith("v") and "." not in v["version_tag"]
        and v["version_tag"].lstrip("v").isdigit()
    ]
    next_major = max(major_tags, default=0) + 1
    new_tag = f"v{next_major}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Retire current deployed
    deployed = db_get_deployed_version(caller)
    if deployed:
        db_update_prompt_version(deployed["id"], status="retired")

    # Promote draft to deployed with new tag
    db_update_prompt_version(id, status="deployed", version_tag=new_tag, deployed_at=now)

    # Update cache
    _cache_set(caller, id)

    return db_get_prompt_version(id)
```

- [ ] **Step 2: Add `POST /api/admin/prompt-versions/{id}/revise`**

```python
@router.post("/prompt-versions/{id}/revise")
def revise_version(id: str, _user: str = Depends(require_auth)):
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Not found")
    if version["status"] != "draft":
        raise HTTPException(400, "Only draft can be revised")

    caller = version["caller"]
    current_tag = version["version_tag"]  # e.g. "v1.1"

    # Compute next minor tag
    parts = current_tag.split(".")
    base = parts[0]  # "v1"
    minor = int(parts[1]) if len(parts) > 1 else 0
    new_tag = f"{base}.{minor + 1}"

    # Supersede current draft
    db_update_prompt_version(id, status="superseded")

    # Create new draft
    new_id = uuid.uuid4().hex[:16]
    db_insert_prompt_version(
        id_=new_id,
        caller=caller,
        version_tag=new_tag,
        prompt_text=version["prompt_text"],
        system_instruction=version.get("system_instruction"),
        status="draft",
    )
    return db_get_prompt_version(new_id)
```

- [ ] **Step 3: Add `GET /api/admin/prompt-versions/{id}/compare`**

```python
@router.get("/prompt-versions/{id}/compare")
def compare_versions(id: str, _user: str = Depends(require_auth)):
    from ..db import db_get_evaluations_for_version
    version = db_get_prompt_version(id)
    if not version:
        raise HTTPException(404, "Not found")
    deployed = db_get_deployed_version(version["caller"])
    return {
        "draft": version,
        "deployed": deployed,
        "draft_evaluations": db_get_evaluations_for_version(id),
        "deployed_evaluations": db_get_evaluations_for_version(deployed["id"]) if deployed else [],
    }
```

- [ ] **Step 4: Test the deploy flow**

Call `POST /api/admin/prompt-versions/{draft_id}/deploy`. Verify:
1. Draft's version_tag changes to `v2`
2. Previous deployed version becomes `retired`
3. Cache is updated (check by calling `GET /api/admin/prompt-versions?caller=interpret_planets`)

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/api/admin_router.py
git commit -m "feat(admin): add deploy, revise, compare endpoints for prompt versioning"
```

---

### Task 14: Add `user_router.py` — user evaluations + feedback

**Files:**
- Create: `astrology_api/app/api/user_router.py`
- Modify: `astrology_api/main.py`

- [ ] **Step 1: Create `user_router.py`**

```python
# astrology_api/app/api/user_router.py
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ..db import db_insert_prompt_evaluation, db_insert_user_feedback
from ..security import get_optional_user

router = APIRouter(prefix="/api/user", tags=["user"])

# Valid internal caller keys (frontend sends these directly)
VALID_CALLERS = {
    "interpret_planets", "transits_full_new", "transits_full_summary",
    "analyze_synastry", "analyze_solar_return", "analyze_rectification",
    "chat_with_chart", "generate", "generate_asc_quiz", "calc_confidence", "system",
}

class UserEvalRequest(BaseModel):
    log_id: str
    score: int  # 1, 3, or 5
    notes: str = ""

class FeedbackRequest(BaseModel):
    caller_label: str  # Chinese display label
    content: str

@router.post("/prompt-evaluations")
def submit_user_eval(body: UserEvalRequest, user=Depends(get_optional_user)):
    if body.score not in (1, 3, 5):
        from fastapi import HTTPException
        raise HTTPException(400, "score must be 1, 3, or 5")
    eval_id = uuid.uuid4().hex[:16]
    db_insert_prompt_evaluation(
        id_=eval_id, log_id=body.log_id, version_id=None,
        evaluator_type="user",
        score_overall=float(body.score),
        dimensions=None,
        notes=body.notes or None,
        suggestions=None,
    )
    return {"id": eval_id, "status": "ok"}

@router.post("/feedback")
def submit_feedback(body: FeedbackRequest, user=Depends(get_optional_user)):
    caller = body.caller_label if body.caller_label in VALID_CALLERS else None
    fb_id = uuid.uuid4().hex[:16]
    user_id = str(user["user_id"]) if user and user.get("user_id") else None
    db_insert_user_feedback(
        id_=fb_id,
        caller=caller,
        content=body.content,
        user_id=user_id,
    )
    return {"id": fb_id, "status": "ok"}
```

- [ ] **Step 2: Register in `main.py`**

Add import and include_router:
```python
from app.api.user_router import router as user_router
# ... in router section:
app.include_router(user_router)
```

- [ ] **Step 3: Test both endpoints**

```bash
curl -X POST http://127.0.0.1:8001/api/user/feedback \
  -H "Content-Type: application/json" \
  -d '{"caller_label": "行运分析", "content": "分析很准确"}'
```
Expected: `{"id": "...", "status": "ok"}`

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/api/user_router.py astrology_api/main.py
git commit -m "feat(user): add user prompt-evaluations and feedback endpoints"
```

---
