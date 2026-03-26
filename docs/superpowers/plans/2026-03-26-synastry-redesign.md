# Synastry AI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the basic 4-dimension text analysis with a full AI-driven synastry analysis that identifies relationship texture, ranks the top 3 most likely relationship types (with evidence), and provides 6-dimension structured analysis — all enforced via Gemini response_schema.

**Architecture:** The `/api/synastry` endpoint is unchanged (computes raw aspects). The `/api/interpret/synastry` endpoint is redesigned: it now accepts full planet data alongside aspects, calls a rewritten `analyze_synastry()` that sends rich context to Gemini with enforced JSON schema, and returns the structured result directly. Cache layer continues using the `synastry_cache.answer` TEXT column — now storing serialised JSON instead of plain text.

**Tech Stack:** Python FastAPI, google-genai>=1.0.0 (Gemini), Pydantic, SQLite/Turso cache, React/Vite frontend (minimal shim only).

---

## File Map

| File | Change |
|---|---|
| `astrology_api/app/rag.py` | Rewrite `analyze_synastry()` — new signature, enriched payload, response_schema, returns structured dict |
| `astrology_api/app/api/interpret_router.py` | Add `chart1_planets`/`chart2_planets` to request model; fix cache read/write for new format |
| `frontend/src/pages/Synastry.jsx` | (a) Pass planet data in `handleInterpret`; (b) minimal structured display shim |

---

## Task 1: Rewrite `analyze_synastry()` in `rag.py`

**Files:**
- Modify: `astrology_api/app/rag.py` (around line 1459)

### Background

Current function sends a flat list of aspects to Gemini with a basic prompt. New version sends full planet data (name, sign, degree, house) + enriched aspects (with sign context + double_whammy) and enforces output via `response_schema`.

The `google-genai` SDK (1.x) supports `response_schema` as a dict in `GenerateContentConfig`. No prompt-injection needed — the schema is enforced at the API level.

### Steps

- [ ] **Step 1: Replace the `analyze_synastry` function**

Find the function at line ~1459 in `astrology_api/app/rag.py`. Replace the entire function body (lines 1459–1507) with:

```python
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

    # ── 1. 构建行星列表 ──────────────────────────────────────────────
    # chart1_planets is a plain dict (deserialised from JSON request body),
    # so use .get() not getattr().
    def _planet_list(planets_dict: dict) -> list[dict]:
        result = []
        for name, p in planets_dict.items():
            try:
                p_dict = p if isinstance(p, dict) else vars(p)
                longitude = float(p_dict.get('longitude', 0))
                result.append({
                    "planet": name,
                    "sign": p_dict.get('sign', ''),
                    "degree": round(longitude % 30, 1),
                    "house": p_dict.get('house', None),
                })
            except Exception:
                pass
        return result

    planets1 = _planet_list(chart1_planets)
    planets2 = _planet_list(chart2_planets)

    # ── 2. 构建富化相位列表（补充星座信息）────────────────────────────
    def _sign(p) -> str:
        return p.get('sign', '') if isinstance(p, dict) else getattr(p, 'sign', '')

    sign_lookup1 = {name: _sign(p) for name, p in chart1_planets.items()}
    sign_lookup2 = {name: _sign(p) for name, p in chart2_planets.items()}

    enriched_aspects = []
    for a in aspects:
        p1_name = a.get('p1_name', a.get('p1', ''))
        p2_name = a.get('p2_name', a.get('p2', ''))
        enriched_aspects.append({
            "p1": p1_name,
            "p1_sign": sign_lookup1.get(p1_name, '') or sign_lookup2.get(p1_name, ''),
            "aspect": a.get('aspect', ''),
            "p2": p2_name,
            "p2_sign": sign_lookup2.get(p2_name, '') or sign_lookup1.get(p2_name, ''),
            "orb": round(float(a.get('orbit', a.get('orb', 0))), 1),
            "double_whammy": bool(a.get('double_whammy', False)),
        })

    # ── 3. 构建 Gemini payload ───────────────────────────────────────
    context = {
        "person1": {"name": chart1_name, "planets": planets1},
        "person2": {"name": chart2_name, "planets": planets2},
        "cross_aspects": enriched_aspects,
    }

    prompt = f"""你是专业占星师，请根据以下两人的完整星盘数据进行合盘分析。

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

    # ── 4. 调用 Gemini（强制 JSON schema）────────────────────────────
    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_SYNASTRY_OUTPUT_SCHEMA,
            temperature=0.4,
        ),
    )

    try:
        result = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError) as e:
        raise RuntimeError(f"Gemini synastry schema parse failed: {e}\nRaw: {getattr(response, 'text', '')[:200]}")

    return result
```

- [ ] **Step 2: Verify the function is syntactically correct**

```bash
cd C:/personal/AIAstro/astrology_api
python -c "from app.rag import analyze_synastry; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 3: Commit**

```bash
cd C:/personal/AIAstro
git add astrology_api/app/rag.py
git commit -m "feat(synastry): rewrite analyze_synastry with full chart context + response_schema"
```

---

## Task 2: Update `interpret_router.py` — request model + cache

**Files:**
- Modify: `astrology_api/app/api/interpret_router.py` (lines 214–253)

### Steps

- [ ] **Step 1: Update `SynastryInterpretRequest` to include planet data**

Replace lines 214–217:
```python
class SynastryInterpretRequest(BaseModel):
    chart1_summary: Dict[str, Any]   # {name, ...} 用于 prompt 中称呼
    chart2_summary: Dict[str, Any]
    aspects: List[Dict[str, Any]]    # 来自 /api/synastry 返回的 aspects 列表
```

With:
```python
class SynastryInterpretRequest(BaseModel):
    chart1_summary: Dict[str, Any]      # {name, ...}
    chart2_summary: Dict[str, Any]
    aspects: List[Dict[str, Any]]       # from /api/synastry response
    chart1_planets: Dict[str, Any] = {} # from /api/synastry response
    chart2_planets: Dict[str, Any] = {} # from /api/synastry response
```

Note: `= {}` default ensures backwards compatibility with any existing callers that don't pass planet data yet.

- [ ] **Step 2: Update `interpret_synastry` handler — call + cache**

Replace lines 220–253 (the entire handler):

```python
@router.post("/interpret/synastry")
async def interpret_synastry(body: SynastryInterpretRequest):
    """合盘 AI 解读：Gemini 全量数据推理 + response_schema 强制结构，带 DB 缓存。"""
    import hashlib, json
    from ..db import db_get_synastry_cache, db_save_synastry_cache
    try:
        # ── 缓存键：所有相位按 key 排序后 hash ──────────────────────────
        aspects_str = json.dumps(
            sorted([f"{a.get('p1_name','')}{a.get('aspect','')}{a.get('p2_name','')}" for a in body.aspects])
        )
        aspects_hash = hashlib.md5(aspects_str.encode()).hexdigest()

        cached = db_get_synastry_cache(aspects_hash)
        if cached:
            answer_val = cached.get("answer", "")
            # Try to deserialise as new structured JSON
            try:
                parsed = json.loads(answer_val) if isinstance(answer_val, str) else answer_val
                if isinstance(parsed, dict) and "texture_labels" in parsed:
                    return parsed  # new-format cache hit
                # Old-format text entry — fall through to regenerate
            except (json.JSONDecodeError, TypeError):
                pass  # Old-format — regenerate

        from ..rag import analyze_synastry
        result = analyze_synastry(
            chart1_name=body.chart1_summary.get("name", "甲"),
            chart2_name=body.chart2_summary.get("name", "乙"),
            chart1_planets=body.chart1_planets,
            chart2_planets=body.chart2_planets,
            aspects=body.aspects,
        )
        # Serialise full structured JSON into the answer column
        db_save_synastry_cache(aspects_hash, json.dumps(result, ensure_ascii=False), [])

        query = " ".join(
            f"{a.get('p1_name','')} {a.get('aspect','')} {a.get('p2_name','')}"
            for a in body.aspects[:5]
        )
        asyncio.create_task(_log_analytics(query, result))
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synastry interpretation error: {e}")
```

- [ ] **Step 3: Verify import-level syntax**

```bash
cd C:/personal/AIAstro/astrology_api
python -c "from app.api.interpret_router import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd C:/personal/AIAstro
git add astrology_api/app/api/interpret_router.py
git commit -m "feat(synastry): update interpret endpoint — full planet data + structured cache"
```

---

## Task 3: Frontend shim — pass planet data + display new response

**Files:**
- Modify: `frontend/src/pages/Synastry.jsx`

This task makes the backend testable. The full UI redesign is deferred. We only need:
1. `handleInterpret` to pass `chart1_planets`/`chart2_planets` from the `/api/synastry` response
2. A minimal display that renders the structured response (so we can verify the AI output visually)

### Steps

- [ ] **Step 1: Update `handleInterpret` to pass planet data**

Find `handleInterpret` (around line 336):

```javascript
function handleInterpret() {
  if (!result?.aspects) return
  interp.run({
    chart1_summary: { name: col1.formData.name },
    chart2_summary: { name: col2.formData.name },
    aspects: result.aspects,
  })
}
```

Replace with:

```javascript
function handleInterpret() {
  if (!result?.aspects) return
  interp.run({
    chart1_summary: { name: col1.formData.name },
    chart2_summary: { name: col2.formData.name },
    aspects: result.aspects,
    chart1_planets: result.chart1_planets || {},
    chart2_planets: result.chart2_planets || {},
  })
}
```

- [ ] **Step 2: Replace `AIPanel` usage with minimal structured display shim**

Find the AI interpretation section (around line 453):

```jsx
{/* AI interpretation */}
{result && (
  <AIPanel
    onGenerate={handleInterpret}
    loading={interp.loading}
    result={interp.result}
    error={interp.error}
  />
)}
```

Replace with:

```jsx
{/* AI interpretation */}
{result && (
  <div style={{ marginTop: '24px' }}>
    <button
      onClick={handleInterpret}
      disabled={interp.loading}
      style={{
        padding: '8px 20px', borderRadius: '8px',
        cursor: interp.loading ? 'not-allowed' : 'pointer',
        backgroundColor: '#2a2a5a', border: '1px solid #4a4a8a',
        color: interp.loading ? '#5a5a8a' : '#c9a84c', fontSize: '0.85rem',
      }}
    >
      {interp.loading ? '生成中…' : '生成 AI 解读'}
    </button>

    {interp.error && (
      <div style={{ color: '#cc4444', fontSize: '0.82rem', marginTop: '8px' }}>
        {interp.error}
      </div>
    )}

    {interp.result && !interp.result.texture_labels && (
      /* Old-format fallback */
      <pre style={{ marginTop: '16px', color: '#ccc', whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
        {interp.result.answer}
      </pre>
    )}

    {interp.result?.texture_labels && (
      <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Texture */}
        <div style={{ padding: '12px 14px', backgroundColor: '#12122a', borderRadius: '8px', border: '1px solid #2a2a5a' }}>
          <div style={{ color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '6px' }}>关系质感</div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
            {interp.result.texture_labels.map(label => (
              <span key={label} style={{ padding: '3px 10px', backgroundColor: '#2a2a5a', borderRadius: '12px', color: '#c9a84c', fontSize: '0.82rem' }}>
                {label}
              </span>
            ))}
          </div>
          <div style={{ color: '#a0a0cc', fontSize: '0.82rem' }}>{interp.result.texture_reasoning}</div>
        </div>

        {/* Relationship rankings */}
        <div style={{ padding: '12px 14px', backgroundColor: '#12122a', borderRadius: '8px', border: '1px solid #2a2a5a' }}>
          <div style={{ color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px' }}>最可能形成的关系</div>
          {interp.result.relationship_rankings.map((r, i) => (
            <div key={i} style={{ marginBottom: '12px', paddingBottom: '12px', borderBottom: i < 2 ? '1px solid #1a1a3a' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                <span style={{ color: '#c9a84c', fontWeight: 600 }}>{r.type}</span>
                <span style={{ color: '#6666aa', fontSize: '0.78rem' }}>{r.score} / 100</span>
              </div>
              <div style={{ color: '#6666aa', fontSize: '0.75rem', marginBottom: '4px' }}>
                {r.key_aspects.join(' · ')}
              </div>
              <div style={{ color: '#a0a0cc', fontSize: '0.82rem', lineHeight: 1.6 }}>{r.summary}</div>
            </div>
          ))}
        </div>

        {/* Dimensions */}
        <div style={{ padding: '12px 14px', backgroundColor: '#12122a', borderRadius: '8px', border: '1px solid #2a2a5a' }}>
          <div style={{ color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px' }}>各维度分析</div>
          {Object.entries({
            attraction: '吸引力', emotional: '情感连结', communication: '沟通',
            stability: '稳定性', growth: '成长激励', friction: '摩擦张力',
          }).map(([key, label]) => {
            const d = interp.result.dimensions[key]
            if (!d) return null
            return (
              <div key={key} style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                  <span style={{ color: '#8888cc', fontSize: '0.8rem' }}>{label}</span>
                  <span style={{ color: '#c9a84c', fontSize: '0.8rem' }}>{d.score}</span>
                </div>
                <div style={{ height: '4px', backgroundColor: '#1a1a3a', borderRadius: '2px', marginBottom: '6px' }}>
                  <div style={{ width: `${d.score}%`, height: '100%', backgroundColor: '#4a4a9a', borderRadius: '2px' }} />
                </div>
                <div style={{ color: '#a0a0cc', fontSize: '0.8rem', lineHeight: 1.6 }}>{d.analysis}</div>
              </div>
            )
          })}
        </div>
      </div>
    )}
  </div>
)}
```

- [ ] **Step 3: Remove unused `AIPanel` import**

At the top of `frontend/src/pages/Synastry.jsx`, find and remove the `AIPanel` import line:

```javascript
import AIPanel from '../components/AIPanel'
```

Delete that line entirely. `AIPanel` is no longer used after the shim replacement.

- [ ] **Step 4: Verify frontend builds**

```bash
cd C:/personal/AIAstro/frontend
npm run build 2>&1 | tail -5
```

Expected: build success, no errors.

- [ ] **Step 5: Commit**

```bash
cd C:/personal/AIAstro
git add frontend/src/pages/Synastry.jsx
git commit -m "feat(synastry): pass planet data to interpret + minimal structured result display"
```

---

## Task 4: End-to-End Test + Push

### Steps

- [ ] **Step 1: Start backend and verify endpoint accepts new request shape**

```bash
cd C:/personal/AIAstro/astrology_api
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Open `http://127.0.0.1:8001/docs` → `POST /api/interpret/synastry` → try with:
```json
{
  "chart1_summary": {"name": "测试甲"},
  "chart2_summary": {"name": "测试乙"},
  "aspects": [],
  "chart1_planets": {},
  "chart2_planets": {}
}
```

Expected: returns structured JSON with `texture_labels`, `relationship_rankings`, `dimensions` (may use fallback values for empty input).

- [ ] **Step 2: Full flow test via frontend**

Start frontend (`npm run dev` in `frontend/`). Navigate to 合盘 tab. Select two saved charts (or fill manually). Click 计算合盘 → then 生成 AI 解读.

Expected:
- 关系质感 section appears with 1-2 tags + reasoning
- 最可能形成的关系 shows 3 distinct types with scores + evidence
- 各维度分析 shows 6 dimensions with score bars + text

- [ ] **Step 3: Push both remotes**

```bash
cd C:/personal/AIAstro
git push origin main && git push hf main
```
