# Synastry Redesign — Design Spec
Date: 2026-03-26

## Problem

The current synastry feature has three core issues:
1. **Raw data dump**: The aspect table shows 30+ rows of technical data (direction, planet names, orb angles) with no context for non-professional users.
2. **Misused AI**: `analyze_synastry()` sends a flat aspect list to Gemini with a basic 4-dimension prompt. AI is used as a text formatter, not a reasoner.
3. **Romantic-only framing**: All analysis implicitly assumes a romantic relationship, ignoring the full range of relationship types.

---

## Goals

- Surface the most important insight first: what kind of relationship is most likely to form between these two people.
- Give non-professionals a readable, structured analysis with clear evidence.
- Let AI reason holistically from full chart data rather than translating pre-scored numbers.
- Ensure output consistency via enforced JSON schema (not prompt-only instructions).

---

## Design

### Architecture

```
/api/synastry  (unchanged)
  → calculates raw cross-aspects (existing, keep as-is)

/api/interpret/synastry  (redesigned)
  → accepts: chart1 full planet data + chart2 full planet data + cross_aspects
  → builds rich context payload (planet signs, degrees, houses included)
  → calls Gemini with response_schema enforcement
  → returns structured JSON consumed directly by frontend
```

### Data Sent to AI

Full context payload (not pre-scored). `analyze_synastry()` receives:
- `chart1_planets: dict` — the `chart1_planets` field from `SynastryResponse` (keyed by planet name, each a `PlanetData` with `.sign`, `.longitude`, `.house`)
- `chart2_planets: dict` — same for chart2
- `aspects: list[dict]` — the raw `aspects` list from `SynastryResponse`, already containing `double_whammy: bool`

`analyze_synastry()` builds the AI payload internally by:
1. Converting each `PlanetData` to `{"planet": name, "sign": p.sign, "degree": round(p.longitude % 30, 1), "house": p.house}`
2. Enriching each aspect with `p1_sign` / `p2_sign` by looking up the planet name in `chart1_planets` / `chart2_planets`

```python
# Payload shape sent to Gemini
{
  "person1": {
    "name": "...",
    "planets": [
      {"planet": "太阳", "sign": "天蝎", "degree": 15.3, "house": 7},
      ...
    ]
  },
  "person2": { ... },
  "cross_aspects": [
    {
      "p1": "金星", "p1_sign": "天蝎",
      "aspect": "刑",
      "p2": "火星", "p2_sign": "水瓶",
      "orb": 1.2, "double_whammy": true
    },
    ...
  ]
}
```

No pre-scoring. No domain weighting. The algorithm's job is only to calculate aspects accurately (it already does this well).

### Enforced Output Schema

Applied via Gemini `response_mime_type="application/json"` + `response_schema`. The model cannot produce output that violates this schema.

```python
OUTPUT_SCHEMA = {
  "type": "object",
  "properties": {
    "texture_labels": {
      "type": "array",
      "items": {"type": "string", "enum": [
        "激情拉扯", "灵魂安栖", "头脑风暴", "相互成就",
        "命运纠缠", "温暖守护", "创意共振", "对立成长"
      ]},
      "minItems": 1, "maxItems": 2
    },
    "texture_reasoning": {"type": "string"},
    "relationship_rankings": {
      "type": "array",
      "minItems": 3, "maxItems": 3,
      "items": {
        "type": "object",
        "properties": {
          "type": {"type": "string", "enum": [
            "浪漫伴侣", "深度友谊", "心智共鸣",
            "职场搭档", "师徒引路", "创意灵感", "宿命牵绊"
          ]},
          "score": {"type": "integer", "minimum": 0, "maximum": 100},
          "key_aspects": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
          "summary": {"type": "string"}
        },
        "required": ["type", "score", "key_aspects", "summary"]
      }
    },
    "dimensions": {
      "type": "object",
      "properties": {
        "attraction":    {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score","analysis"]},
        "emotional":     {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score","analysis"]},
        "communication": {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score","analysis"]},
        "stability":     {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score","analysis"]},
        "growth":        {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score","analysis"]},
        "friction":      {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "analysis": {"type": "string"}}, "required": ["score","analysis"]}
      },
      "required": ["attraction","emotional","communication","stability","growth","friction"]
    }
  },
  "required": ["texture_labels","texture_reasoning","relationship_rankings","dimensions"]
}
```

### Relationship Types (7)

| Type | Core Driver | Distinct From |
|---|---|---|
| 浪漫伴侣 | Venus-Mars, Sun-Moon activation | Requires attraction domain |
| 深度友谊 | Moon-Moon, Sun-Sun emotional wavelength | Platonic, no attraction dependency |
| 心智共鸣 | Mercury-dominant connections | Thought-driven, not emotion-driven |
| 职场搭档 | Saturn-Jupiter, Mercury-Saturn | Goal-oriented, peer-level |
| 师徒引路 | Saturn as teacher, Jupiter expansion | Hierarchical power dynamic |
| 创意灵感 | Venus-Neptune, Jupiter-dominant | Aesthetic/imaginative, non-goal-oriented |
| 宿命牵绊 | Outer planets (Uranus/Neptune/Pluto) to personal | Transformative, feels fated |

### Relationship Texture Labels (8)

Determined by AI based on full context (not pre-calculated ratio):

| Label | Typical Pattern |
|---|---|
| 激情拉扯 | Venus-Mars squares, Mars-Pluto tension, high friction + high attraction |
| 灵魂安栖 | Sun-Moon harmonics, Moon-Venus trines, low friction |
| 头脑风暴 | Mercury dominant, mutual stimulation |
| 相互成就 | Jupiter-Saturn balance, mutual growth without dominance |
| 命运纠缠 | Outer planet conjunctions, nodes involved |
| 温暖守护 | Moon-Saturn protective aspects, Sun-Moon nurturing |
| 创意共振 | Venus-Neptune, Sun-Neptune, Neptune-Mercury |
| 对立成长 | Mars-Mars, Sun-Sun opposition/square, competitive tension |

### AI Prompt Structure

```
你是专业占星师，请根据以下两人的完整星盘数据进行合盘分析。

【数据】
{full_context_json}

【分析要求】
1. 识别1-2个关系质感标签（从给定列表选择），说明依据
2. 评估最可能形成的关系类型Top 3，给出0-100概率分，引用具体相位作为证据（最多3条），用2-3句话描述
3. 对六个维度各给出0-100分和分析，分析中必须引用具体行星相位，用普通用户能理解的语言

注意：
- 概率分反映"这段关系的能量自然倾向"，不是主观建议
- 相位的星座背景很重要，请考虑星座特质
- double whammy（★）相位权重更高
- Top 3关系类型必须是不同的三种类型，不可重复
- 请用中文回答
```

### Files Changed

| File | Change |
|---|---|
| `astrology_api/app/rag.py` | Rewrite `analyze_synastry(chart1_name, chart2_name, chart1_planets, chart2_planets, aspects)`: build full context payload, enrich aspects with sign data, call Gemini with response_schema, return structured JSON |
| `astrology_api/app/api/interpret_router.py` | Update `SynastryInterpretRequest` to add `chart1_planets: Dict[str, Any]` and `chart2_planets: Dict[str, Any]`; update `interpret_synastry` to pass them through; serialise cache hit/miss correctly |
| `frontend/src/pages/Synastry.jsx` | **Out of scope** — frontend redesign deferred |

### Caching

Cache key: MD5 of sorted cross_aspects (existing logic, unchanged — sorts by `p1_name+aspect+p2_name` string concatenation). Note: two couples with identical aspect angles but different signs/houses would share a cache entry; this is an acceptable edge-case limitation.

Cache storage: the existing `db_save_synastry_cache(hash, answer, sources)` stores `answer: str`. The new structured JSON response will be serialised to a string (`json.dumps(result)`) before saving, and deserialised (`json.loads`) on cache hit. No schema migration required — the `answer` column stores the JSON blob as text. `sources` will be passed as `[]` since the new response has no `sources` field.

### Analytics Logging

The existing `_log_analytics(query, result)` call reads `result.get("sources", [])`. Since the new response has no `sources` key, `sources` will always be `[]` (`any_cited=False`, `max_score=0.0`). This is acceptable — analytics tracks query patterns, not source quality, for this endpoint. No change needed.

Query string: top 5 tightest aspects joined as string (existing logic, unchanged).

---

## Out of Scope

- Frontend UI redesign (deferred)
- New relationship type additions beyond the 7 defined
- Streaming output
