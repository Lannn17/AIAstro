"""
app/rag/analytics.py — 问题分类（规则匹配，无 Gemini 调用）
"""

_QUERY_LABELS = (
    "planet_sign",
    "planet_house",
    "aspect",
    "life_area",
    "psychological",
    "prediction",
    "other",
)


def classify_query(query: str) -> str:
    """将占星问题分类为 7 个预定义标签之一（规则匹配）。"""
    q = query.lower()
    if any(w in q for w in [
        "太阳在", "月亮在", "水星在", "金星在", "火星在", "木星在",
        "土星在", "天王星在", "海王星在", "冥王星在", "凯龙在",
        "in aries", "in taurus", "in gemini", "in cancer",
        "in leo", "in virgo", "in libra", "in scorpio",
        "in sagittarius", "in capricorn", "in aquarius", "in pisces",
    ]):
        return "planet_sign"
    if any(w in q for w in [
        "第1宫", "第2宫", "第3宫", "第4宫", "第5宫", "第6宫",
        "第7宫", "第8宫", "第9宫", "第10宫", "第11宫", "第12宫",
        "宫位", "house",
    ]):
        return "planet_house"
    if any(w in q for w in [
        "合相", "对冲", "四分", "三分", "六分",
        "conjunction", "opposition", "square", "trine", "sextile",
        "相位", "aspect",
    ]):
        return "aspect"
    if any(w in q for w in [
        "感情", "爱情", "婚姻", "事业", "工作", "财运", "金钱",
        "健康", "家庭", "友情", "人际", "love", "career", "money",
    ]):
        return "life_area"
    if any(w in q for w in [
        "性格", "心理", "行为", "个性", "天性",
        "personality", "psychology", "behavior",
    ]):
        return "psychological"
    if any(w in q for w in [
        "运势", "预测", "什么时候", "几时", "未来", "趋势",
        "forecast", "prediction", "when",
    ]):
        return "prediction"
    return "other"
