"""
app/rag/rectification.py — 出生时间校对 AI 解读 + 问卷生成 + 置信度评分
"""
from google.genai import types

from .client import client, GENERATE_MODEL
from .retrieval import retrieve, _load, _parse_json
from .prompts import _clean_source_name, _SYSTEM_PROMPT_UNIFIED
from .chart_summary import format_chart_summary

_EVENT_TYPE_ZH = {
    'marriage':    '结婚',
    'divorce':     '离婚',
    'career_up':   '升职/事业突破',
    'career_down': '失业/事业受挫',
    'bereavement': '亲人离世',
    'illness':     '重大疾病',
    'relocation':  '搬迁',
    'accident':    '意外事故',
    'other':       '其他重大事件',
}


def analyze_rectification(
    natal_chart: dict,
    top3: list[dict],
    events: list[dict],
) -> dict:
    """
    AI解读出生时间校对结果：
    - 每个候选时间的上升星座特征与事件模式是否相符
    - 算法选出这些时间的占星依据
    - 推荐哪个候选，以及如何进一步验证
    """
    _load()

    chart_summary = format_chart_summary(natal_chart, max_aspects=5) if natal_chart else "（无本命盘数据）"

    event_lines = []
    for ev in events:
        etype = _EVENT_TYPE_ZH.get(ev.get('event_type', 'other'), ev.get('event_type', ''))
        w = int(ev.get('weight', 1))
        wlabel = ['', '一般', '重要', '非常重要'][min(w, 3)]
        m = ev.get('month')
        d = ev.get('day')
        date_str = (
            f"{ev['year']}/{m:02d}/{d:02d}" if m and d
            else f"{ev['year']}/{m:02d}/xx" if m
            else f"{ev['year']}/xx/xx"
        )
        event_lines.append(f"  {date_str}  {etype}（{wlabel}）")

    top3_lines = []
    for i, t in enumerate(top3, 1):
        asc = t.get('asc_sign', '')
        asc_str = f"，上升 {asc}" if asc else ''
        top3_lines.append(
            f"  候选{i}：{t['hour']:02d}:{t['minute']:02d}{asc_str}  评分 {t['score']}"
        )

    query = "birth time rectification ascendant secondary progressions life events"
    chunks = retrieve(query, k=3)
    rag_section = ""
    if chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        rag_section = (
            "\n\n---\n以下为相关占星书籍参考（可按需引用，注明书名）：\n\n"
            + "\n\n".join(parts)
        )

    candidates_list = ",\n".join(
        f'    {{"rank": {i}, "reason": "..."}}'
        for i in range(1, len(top3) + 1)
    )

    prompt = f"""出生时间校对结果：

{chart_summary}

用户提供的重大人生事件：
{chr(10).join(event_lines)}

算法评分 Top3 候选出生时间（rank 1 为算法评分最高）：
{chr(10).join(top3_lines)}

---
分析要求：
- 对每个候选时间（rank 1/2/3），在 reason 字段中单独分析：该上升星座的性格特征、哪些宫位或角点在用户事件日期被行运激活、与事件模式的吻合或不吻合之处（100-150字）
- 每个 reason 只分析自身对应的候选，不提及其他候选
- overall 给出综合推荐与验证建议（150-200字）
- ai_recommended_rank：根据你的占星理论分析，哪个候选最符合用户的人生事件模式？填写该候选的 rank 编号（1、2 或 3）

返回 JSON：
{{
  "candidates": [
{candidates_list}
  ],
  "overall": "...",
  "ai_recommended_rank": 1
}}{rag_section}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            response_mime_type="application/json",
            temperature=0.5,
        ),
    )

    print(f"[rectify] raw response ({len(response.text)} chars): {response.text[:300]}")
    try:
        parsed = _parse_json(response.text)
    except Exception as e:
        print(f"[rectify] JSON parse error: {e}")
        parsed = {"candidates": [], "overall": response.text}

    ai_rank = parsed.get("ai_recommended_rank")
    sources = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in chunks]

    return {
        "candidates":           parsed.get("candidates", []),
        "overall":              parsed.get("overall", ""),
        "ai_recommended_rank":  ai_rank,
        "sources":              sources,
    }


def generate_asc_quiz(asc_signs: list[str]) -> dict:
    """
    根据 Top3 的上升星座动态生成 5 道鉴别性选择题。
    返回: {"questions": [...], "sources": [...]}
    """
    _load()
    signs_str = "、".join(asc_signs)

    rag_chunks = retrieve(f"上升星座性格特征外貌体态 {signs_str}", k=3)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = "\n\n【参考书籍片段（可用于增强题目描述的准确性）】\n" + "\n\n".join(parts) + "\n\n"

    prompt = f"""你是一位专业占星师，需要设计一套用于区分以下三种上升星座的性格/外貌选择题：{signs_str}
{rag_context}
请生成5道选择题，每道题4个选项（A/B/C/D），从以下5个维度各出1题：
1. 外貌与体态特征
2. 他人对你的第一印象
3. 面对压力或冲突时的本能反应
4. 日常行为与做事风格
5. 最能描述你早年经历的模式

要求：
- 选项必须能有效区分这3个上升星座
- 描述具体生动，不直接提及星座名称
- 每个选项标注它最符合哪个/哪些上升星座（用英文名，如 Aries）
- 可以有一个"都不太符合"选项，signs 为空数组

以JSON格式返回（只返回JSON，不要其他文字）：
{{
  "questions": [
    {{
      "id": "q1",
      "text": "题目",
      "options": [
        {{"id": "a", "text": "选项描述", "signs": ["Aries"]}},
        {{"id": "b", "text": "选项描述", "signs": ["Taurus"]}},
        {{"id": "c", "text": "选项描述", "signs": ["Gemini"]}},
        {{"id": "d", "text": "以上都不太符合", "signs": []}}
      ]
    }}
  ]
}}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.6,
        ),
    )
    sources = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in rag_chunks]
    try:
        data = _parse_json(response.text)
        return {"questions": data.get("questions", []), "sources": sources}
    except Exception:
        return {"questions": [], "sources": sources}


def calc_confidence(
    candidate: dict,
    birth_year: int, birth_month: int, birth_day: int,
    lat: float, lng: float, tz_str: str,
    theme_answers: list[dict],
) -> dict:
    """
    根据生命主题问卷答案，评估候选出生时间的置信度。
    返回: {score: 0-100, label: "高/中/低", analysis: str}
    """
    _load()

    h, m = candidate["hour"], candidate["minute"]
    try:
        from kerykeion import AstrologicalSubject
        subj = AstrologicalSubject(
            "conf", birth_year, birth_month, birth_day,
            h, m, lng=lng, lat=lat, tz_str=tz_str,
        )
        natal_data = {
            "asc_sign": candidate.get("asc_sign", ""),
            "sun_sign": subj.sun.sign,
            "moon_sign": subj.moon.sign,
            "mc_sign": subj.tenth_house.sign,
            "stelliums": [],
        }
        house_count = {}
        for attr in ['sun','moon','mercury','venus','mars','jupiter','saturn','uranus','neptune','pluto']:
            if hasattr(subj, attr):
                p = getattr(subj, attr)
                if p:
                    house_count[p.house] = house_count.get(p.house, 0) + 1
        for house, cnt in house_count.items():
            if cnt >= 3:
                natal_data["stelliums"].append(f"{house}宫{cnt}星")
    except Exception:
        natal_data = {"asc_sign": candidate.get("asc_sign", ""), "error": "chart calc failed"}

    answers_text = "\n".join(
        f"Q{i+1}（{a['question']}）→ {a['answer']}" for i, a in enumerate(theme_answers)
    )

    asc_sign = natal_data.get('asc_sign', '')
    rag_chunks = retrieve(f"birth time rectification ascendant life themes {asc_sign}", k=3)
    rag_context = ""
    if rag_chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(rag_chunks, 1)
        ]
        rag_context = "\n\n【参考书籍片段（供评估时参考）】\n" + "\n\n".join(parts) + "\n\n"

    prompt = f"""候选出生时间：{h:02d}:{m:02d}，上升星座：{asc_sign}
太阳星座：{natal_data.get('sun_sign','')}，月亮星座：{natal_data.get('moon_sign','')}，天顶：{natal_data.get('mc_sign','')}
宫位聚集：{natal_data.get('stelliums', []) or '无明显聚集'}

用户生命主题问卷回答：
{answers_text}
{rag_context}
请综合评估以上出生时间与用户生命主题的匹配程度，给出：
1. 置信度分数（0-100整数）
2. 置信度标签（高 ≥70 / 中 40-69 / 低 <40）
3. 简短分析（150字以内）：哪些宫位/行星配置与回答吻合，哪些存在出入

以JSON返回（只返回JSON）：
{{"score": 75, "label": "中", "analysis": "..."}}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    sources = [{"source": c["source"], "score": c["score"], "cited": False, "text": c["text"]} for c in rag_chunks]
    try:
        result = _parse_json(response.text)
        result["sources"] = sources
        return result
    except Exception:
        return {"score": 0, "label": "低", "analysis": response.text, "sources": sources}
