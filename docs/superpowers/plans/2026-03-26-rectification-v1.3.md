# Rectification v1.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement rectification algorithm v1.3 (turning point normalization + slow planet detection + dynamic chart weights + score indicators) and add a `/api/rectify/compare` endpoint for multi-version validation.

**Architecture:** All algorithm changes live in `rectification.py`. The router gains one new endpoint (`/compare`). The frontend shows two new indicator labels above Top3 results.

**Tech Stack:** Python/FastAPI backend, Kerykeion AstrologicalSubject, React/JSX frontend.

**Spec:** `docs/superpowers/specs/2026-03-26-rectification-v1.3-design.md`

---

## File Map

| File | Change |
|---|---|
| `astrology_api/app/core/rectification.py` | Add constants, 2 new functions, modify `_score_candidate` + `rectify_birth_time` |
| `astrology_api/app/api/rectification_router.py` | Add `/compare` endpoint; thread `gap_ratio`/`evidence_score` through existing `/rectify` response |
| `frontend/src/pages/NatalChart.jsx` | Show 分辨力/证据强度 labels above Top3 |
| `ARCHITECTURE.md` | Document new endpoint |

---

## Task 1: Register v1.3 + add constants

**Files:**
- Modify: `astrology_api/app/core/rectification.py`

Read the file first (lines 1–170) to understand existing constant layout.

- [ ] **Step 1: Add `_SIGN_RULER` constant** after the existing `EVENT_HOUSE_MAP` dict (around line 166):

```python
# 宫主星映射（现代守护星）
_SIGN_RULER: dict[str, str] = {
    "Aries": "Mars",    "Taurus": "Venus",   "Gemini": "Mercury",
    "Cancer": "Moon",   "Leo": "Sun",         "Virgo": "Mercury",
    "Libra": "Venus",   "Scorpio": "Pluto",   "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}
```

- [ ] **Step 2: Add `EVENT_KEY_PLANETS` constant** after `_SIGN_RULER`:

```python
# 每种事件类型对应的关键行星（用于动态星盘赋权）
_EVENT_KEY_PLANETS: dict[str, list[str]] = {
    'marriage':                   ['Venus', 'Moon', 'Jupiter'],
    'new_relationship':           ['Venus', 'Moon', 'Jupiter'],
    'divorce':                    ['Saturn', 'Pluto', 'Mars'],
    'breakup':                    ['Saturn', 'Pluto', 'Mars'],
    'career_up':                  ['Sun', 'Jupiter', 'Mars'],
    'business_start':             ['Sun', 'Jupiter', 'Mars'],
    'retirement':                 ['Sun', 'Jupiter', 'Mars'],
    'career_down':                ['Saturn', 'Pluto'],
    'business_end':               ['Saturn', 'Pluto'],
    'career_change':              ['Uranus', 'Jupiter'],
    'childbirth':                 ['Moon', 'Jupiter', 'Sun'],
    'bereavement_parent':         ['Saturn', 'Pluto'],
    'bereavement_spouse':         ['Saturn', 'Pluto'],
    'bereavement_child':          ['Saturn', 'Pluto'],
    'bereavement_other':          ['Saturn', 'Pluto'],
    'bereavement':                ['Saturn', 'Pluto'],
    'serious_illness':            ['Mars', 'Saturn', 'Pluto'],
    'mental_health_crisis':       ['Mars', 'Saturn', 'Pluto'],
    'illness':                    ['Mars', 'Saturn', 'Pluto'],
    'accident':                   ['Mars', 'Uranus'],
    'surgery':                    ['Mars', 'Uranus'],
    'relocation_international':   ['Jupiter', 'Uranus'],
    'study_abroad':               ['Jupiter', 'Uranus'],
    'relocation_domestic':        ['Moon', 'Saturn'],
    'relocation':                 ['Moon', 'Saturn'],
    'financial_gain':             ['Venus', 'Jupiter'],
    'inheritance':                ['Venus', 'Jupiter'],
    'major_investment':           ['Venus', 'Jupiter'],
    'financial_loss':             ['Saturn', 'Pluto'],
    'bankruptcy':                 ['Saturn', 'Pluto'],
    'graduation':                 ['Jupiter', 'Mercury'],
    'major_exam':                 ['Jupiter', 'Mercury'],
    'legal_win':                  ['Jupiter', 'Saturn'],
    'legal_loss':                 ['Jupiter', 'Saturn'],
    'family_bond_change':         ['Moon', 'Saturn'],
    'spiritual_awakening':        ['Neptune', 'Pluto', 'Uranus'],
}
# 未列出的类型 → 空列表 → chart_affinity 保持 1.0
```

- [ ] **Step 3: Register v1.3** in `SCORING_STRATEGIES` and `STRATEGY_DESCRIPTIONS`:

```python
# In SCORING_STRATEGIES dict, add:
"v1.3": {
    "transits":                    False,  # 由 cusp_hits 替代
    "solar_arc":                   True,
    "progressions":                True,
    "primary_directions":          True,
    "cusp_hits":                   True,
    "dynamic_chart_weights":       True,
    "slow_planet_turning_points":  True,
},

# In STRATEGY_DESCRIPTIONS dict, add:
"v1.3": (
    "v1.2 基础上加入动态星盘赋权（行星宫位+宫主星+相位）、"
    "转折点权重归一化、慢星相位检测，及分辨力/证据强度展示"
),
```

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/core/rectification.py
git commit -m "feat(rectify): register v1.3 strategy + add _SIGN_RULER and EVENT_KEY_PLANETS"
```

---

## Task 2: Implement `_compute_chart_affinity`

**Files:**
- Modify: `astrology_api/app/core/rectification.py` (insert after `_get_asc_sign`, before the main entry point)

- [ ] **Step 1: Add helper `_planet_house`** that safely reads a planet's house number from an `AstrologicalSubject`:

```python
def _planet_house(natal: AstrologicalSubject, attr: str) -> int:
    """Return the house number (1-12) of a planet, or 0 on failure."""
    try:
        p = getattr(natal, attr.lower(), None)
        if p is None:
            return 0
        h = getattr(p, 'house', 0)
        # Kerykeion may return int or string like "First_House"
        if isinstance(h, int):
            return h
        _house_name_map = {
            'First_House': 1, 'Second_House': 2, 'Third_House': 3,
            'Fourth_House': 4, 'Fifth_House': 5, 'Sixth_House': 6,
            'Seventh_House': 7, 'Eighth_House': 8, 'Ninth_House': 9,
            'Tenth_House': 10, 'Eleventh_House': 11, 'Twelfth_House': 12,
        }
        return _house_name_map.get(str(h), 0)
    except Exception:
        return 0
```

- [ ] **Step 2: Add `_has_tight_aspect` helper**:

```python
def _has_tight_aspect(pos1: float, pos2: float, orb: float = 5.0) -> bool:
    """True if two ecliptic positions form a major aspect within orb."""
    diff = abs(pos1 - pos2) % 360
    if diff > 180:
        diff = 360 - diff
    return any(abs(diff - t) <= orb for t in (0, 60, 90, 120, 180))
```

- [ ] **Step 3: Add `_compute_chart_affinity`**:

```python
_HOUSE_ATTR_TO_NUM: dict[str, int] = {
    'first_house': 1,   'second_house': 2,  'third_house': 3,
    'fourth_house': 4,  'fifth_house': 5,   'sixth_house': 6,
    'seventh_house': 7, 'eighth_house': 8,  'ninth_house': 9,
    'tenth_house': 10,  'eleventh_house': 11, 'twelfth_house': 12,
}
_ANGULAR_HOUSES = {1, 4, 7, 10}
_IMPORTANT_PLANETS = {'Sun', 'Moon', 'Jupiter', 'Saturn'}


def _compute_chart_affinity(natal: AstrologicalSubject) -> dict[str, float]:
    """
    Compute per-event-type affinity multiplier from natal chart.
    Three layers: planet-in-house (+0.25/+0.15), house-ruler angular (+0.15),
    ruler-aspect-key-planet (+0.10).
    Returns dict[event_type -> float] clamped to [0.6, 2.0].
    """
    result: dict[str, float] = {}

    for ev_type, house_pairs in EVENT_HOUSE_MAP.items():
        affinity = 1.0
        key_planets = _EVENT_KEY_PLANETS.get(ev_type, [])

        for house_attr, _ in house_pairs[:2]:   # top 2 relevant houses
            house_num = _HOUSE_ATTR_TO_NUM.get(house_attr, 0)
            if not house_num:
                continue

            # ── Layer 1: planets in this house ──────────────────────
            for planet_attr in ['sun', 'moon', 'mercury', 'venus', 'mars',
                                 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']:
                ph = _planet_house(natal, planet_attr)
                if ph != house_num:
                    continue
                planet_name = planet_attr.capitalize()
                if planet_name == 'Sun':
                    planet_name = 'Sun'
                # capitalise properly
                cap_map = {
                    'sun': 'Sun', 'moon': 'Moon', 'mercury': 'Mercury',
                    'venus': 'Venus', 'mars': 'Mars', 'jupiter': 'Jupiter',
                    'saturn': 'Saturn', 'uranus': 'Uranus',
                    'neptune': 'Neptune', 'pluto': 'Pluto',
                }
                pname = cap_map[planet_attr]
                if pname in key_planets:
                    affinity += 0.25
                elif pname in _IMPORTANT_PLANETS:
                    affinity += 0.15

            # ── Layer 2: house ruler in angular house ────────────────
            try:
                house_obj = getattr(natal, house_attr, None)
                house_sign = getattr(house_obj, 'sign', '') if house_obj else ''
                ruler_name = _SIGN_RULER.get(house_sign, '')
                if ruler_name:
                    ruler_house = _planet_house(natal, ruler_name)
                    if ruler_house in _ANGULAR_HOUSES:
                        affinity += 0.15

                    # ── Layer 3: ruler tight aspect with key planets ──
                    ruler_obj = getattr(natal, ruler_name.lower(), None)
                    ruler_pos = getattr(ruler_obj, 'abs_pos', None) if ruler_obj else None
                    if ruler_pos is not None:
                        for kp in key_planets:
                            kp_obj = getattr(natal, kp.lower(), None)
                            kp_pos = getattr(kp_obj, 'abs_pos', None) if kp_obj else None
                            if kp_pos is not None and _has_tight_aspect(ruler_pos, kp_pos, orb=5.0):
                                affinity += 0.10
            except Exception:
                pass

        result[ev_type] = max(0.6, min(2.0, affinity))

    return result
```

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/core/rectification.py
git commit -m "feat(rectify): add _compute_chart_affinity with 3-layer activation"
```

---

## Task 3: Implement `_score_slow_planet_transits`

**Files:**
- Modify: `astrology_api/app/core/rectification.py` (insert after `_score_cusp_hits`)

- [ ] **Step 1: Add the function**:

```python
_SLOW_PLANET_COEF: dict[str, float] = {
    'pluto':   3.5,
    'saturn':  3.0,
    'uranus':  2.5,
    'neptune': 1.5,
    'jupiter': 1.5,
}
_NATAL_PLANET_ATTRS = [
    'sun', 'moon', 'mercury', 'venus', 'mars',
    'jupiter', 'saturn', 'uranus', 'neptune', 'pluto',
]
_SLOW_ASPECT_TARGETS = (0, 180, 90, 120)   # no sextile — only major


def _score_slow_planet_transits(
    natal: AstrologicalSubject,
    event_subj: AstrologicalSubject,
    event_weight: float,
    orb: float = 2.0,
) -> float:
    """
    Slow-planet transit score for turning-point events (Phase 2 only).
    Checks Saturn/Uranus/Pluto/Jupiter/Neptune in event_subj against
    ALL natal planets. Tighter orb (2°) than regular transits (5°).
    """
    score = 0.0
    for slow_attr, coef in _SLOW_PLANET_COEF.items():
        t_obj = getattr(event_subj, slow_attr, None)
        if t_obj is None:
            continue
        t_pos = getattr(t_obj, 'abs_pos', None)
        if t_pos is None:
            continue
        for natal_attr in _NATAL_PLANET_ATTRS:
            n_obj = getattr(natal, natal_attr, None)
            if n_obj is None:
                continue
            n_pos = getattr(n_obj, 'abs_pos', None)
            if n_pos is None:
                continue
            diff = abs(t_pos - n_pos) % 360
            if diff > 180:
                diff = 360 - diff
            for target in _SLOW_ASPECT_TARGETS:
                orbit = abs(diff - target)
                if orbit <= orb:
                    score += (orb - orbit) * coef * event_weight
                    break   # count each natal planet once per slow planet
    return score
```

- [ ] **Step 2: Commit**

```bash
git add astrology_api/app/core/rectification.py
git commit -m "feat(rectify): add _score_slow_planet_transits for turning point events"
```

---

## Task 4: Update `_score_candidate` for v1.3

**Files:**
- Modify: `astrology_api/app/core/rectification.py` (function `_score_candidate`, lines ~375–432)

Read the current `_score_candidate` function carefully before editing.

- [ ] **Step 1: Pre-count turning points + compute per-event multiplier**

Replace the turning-point block inside `_score_candidate`:

```python
# OLD (remove this):
if ev.get('is_turning_point', False):
    ew *= 2.0  # 人生转折点：权重翻倍

# NEW — compute BEFORE the event loop, outside it:
n_turning_points = sum(1 for e in events if e.get('is_turning_point', False))
_tp_mult_per = max(1.1, 1.5 / (n_turning_points ** 0.5)) if n_turning_points > 0 else 1.0
```

Then inside the loop, replace the old turning-point line:
```python
if ev.get('is_turning_point', False):
    ew *= _tp_mult_per
```

- [ ] **Step 2: Pre-compute chart_affinity when strategy enables it**

Add after `natal` is constructed, before the event loop:

```python
chart_affinity: dict[str, float] = {}
if strategy.get('dynamic_chart_weights'):
    try:
        chart_affinity = _compute_chart_affinity(natal)
    except Exception:
        chart_affinity = {}
```

- [ ] **Step 3: Apply chart_affinity in event weight calculation**

Change the `ew` calculation line:
```python
# OLD:
ew = ev.get('weight', 1.0) * EVENT_TYPE_WEIGHT.get(ev_type, 1.0)

# NEW:
ew = (ev.get('weight', 1.0)
      * EVENT_TYPE_WEIGHT.get(ev_type, 1.0)
      * chart_affinity.get(ev_type, 1.0))
```

- [ ] **Step 4: Add slow planet scoring in Phase 2 block**

Inside `if include_slow:`, after the existing slow dimensions:

```python
if strategy.get('slow_planet_turning_points') and ev.get('is_turning_point', False):
    # ev_subj already built above if needs_ev_subj; rebuild if not
    try:
        sp_subj = ev_subj if needs_ev_subj else AstrologicalSubject(
            'sp', ev_date.year, ev_date.month, ev_date.day,
            12, 0, lng=lng, lat=lat, tz_str=tz_str,
        )
        total += _score_slow_planet_transits(natal, sp_subj, ew)
    except Exception:
        pass
```

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/core/rectification.py
git commit -m "feat(rectify): update _score_candidate for v1.3 (tp normalization, chart affinity, slow planets)"
```

---

## Task 5: Compute gap_ratio + evidence_score in `rectify_birth_time`

**Files:**
- Modify: `astrology_api/app/core/rectification.py` (function `rectify_birth_time`, return value)

- [ ] **Step 1: Add helper `_compute_indicators`** (add near the end of the file, before the main entry):

```python
def _compute_indicators(top3: list[dict], raw_events: list[dict]) -> dict:
    """
    Compute gap_ratio (discrimination) and evidence_score (input quality).
    Uses raw (pre-expansion) events to avoid double-counting precision_weight.
    """
    # gap_ratio
    scores = [t['score'] for t in top3]
    top1 = scores[0] if scores else 0.0
    top2 = scores[1] if len(scores) > 1 else 0.0
    gap_ratio = 0.0 if top1 == 0 else (top1 - top2) / top1

    if gap_ratio >= 0.25:
        gap_label = '高'
    elif gap_ratio >= 0.10:
        gap_label = '中'
    else:
        gap_label = '低'

    # evidence_score — raw events, precision applied once
    n = len(raw_events)
    if n == 0:
        ev_score = 0.0
    else:
        total_w = 0.0
        for ev in raw_events:
            m, d = ev.get('month'), ev.get('day')
            if m and d:
                pw = 1.0
            elif m:
                pw = 0.7
            else:
                pw = 0.4
            total_w += ev.get('weight', 1.0) * pw
        ev_score = total_w / n

    if ev_score >= 1.5:
        ev_label = '强'
    elif ev_score >= 0.8:
        ev_label = '中'
    else:
        ev_label = '弱'

    return {
        'gap_ratio': round(gap_ratio, 3),
        'gap_label': gap_label,
        'evidence_score': round(ev_score, 3),
        'evidence_label': ev_label,
    }
```

- [ ] **Step 2: Update `rectify_birth_time` return value**

After the Top3 selection loop (just before `return top3`), replace `return top3` with:

```python
indicators = _compute_indicators(top3, events)   # events = raw, pre-expansion
return top3, indicators
```

Also update the function signature docstring to note the new return type: `tuple[list[dict], dict]`.

- [ ] **Step 3: Update callers of `rectify_birth_time` in the router**

In `rectification_router.py`, the existing `/rectify` endpoint calls `rectify_birth_time(...)`. Update:

```python
top3, indicators = rectify_birth_time(...)
```

And add to the return dict:
```python
return {
    "top3": top3,
    "overall": ai.get("overall", ""),
    "version": version,
    "version_description": STRATEGY_DESCRIPTIONS.get(version, ""),
    "gap_label": indicators["gap_label"],
    "evidence_label": indicators["evidence_label"],
}
```

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/core/rectification.py astrology_api/app/api/rectification_router.py
git commit -m "feat(rectify): compute and return gap_ratio + evidence_score indicators"
```

---

## Task 6: Add `/api/rectify/compare` endpoint

**Files:**
- Modify: `astrology_api/app/api/rectification_router.py`

- [ ] **Step 1: Add request model**:

```python
class CompareRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    latitude: float
    longitude: float
    tz_str: str
    house_system: str = "Placidus"
    events: List[EventInput]
    approx_hour: Optional[int] = None
    approx_minute: Optional[int] = None
    time_range_hours: Optional[float] = None
    known_hour: int          # true birth hour for error calculation
    known_minute: int        # true birth minute
```

- [ ] **Step 2: Add the endpoint**:

```python
@router.post("/rectify/compare")
async def compare_versions(body: CompareRequest):
    """
    Run all registered versions against the same events and known birth time.
    Returns per-version Top1 result with error_minutes vs known time.
    """
    try:
        from ..core.rectification import (
            rectify_birth_time, SCORING_STRATEGIES, STRATEGY_DESCRIPTIONS,
        )

        events = [e.model_dump() for e in body.events]
        known_total = body.known_hour * 60 + body.known_minute
        results = []

        for version in SCORING_STRATEGIES:
            top3, indicators = rectify_birth_time(
                birth_year=body.birth_year,
                birth_month=body.birth_month,
                birth_day=body.birth_day,
                lat=body.latitude,
                lng=body.longitude,
                tz_str=body.tz_str,
                events=events,
                approx_hour=body.approx_hour,
                approx_minute=body.approx_minute,
                time_range_hours=body.time_range_hours,
                version=version,
            )
            if not top3:
                continue
            t = top3[0]
            candidate_total = t['hour'] * 60 + t['minute']
            error_minutes = abs(candidate_total - known_total)
            # Handle wrap-around midnight
            error_minutes = min(error_minutes, 1440 - error_minutes)
            results.append({
                'version': version,
                'description': STRATEGY_DESCRIPTIONS.get(version, ''),
                'top1_hour': t['hour'],
                'top1_minute': t['minute'],
                'asc_sign': t.get('asc_sign', ''),
                'score': t['score'],
                'error_minutes': error_minutes,
                'gap_label': indicators['gap_label'],
                'evidence_label': indicators['evidence_label'],
            })

        # Sort by error_minutes ascending
        results.sort(key=lambda x: x['error_minutes'])
        known_time = f"{body.known_hour:02d}:{body.known_minute:02d}"
        return {'known_time': known_time, 'results': results}

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compare error: {e}")
```

- [ ] **Step 3: Commit**

```bash
git add astrology_api/app/api/rectification_router.py
git commit -m "feat(rectify): add /api/rectify/compare endpoint for multi-version validation"
```

---

## Task 7: Frontend — show indicators

**Files:**
- Modify: `frontend/src/pages/NatalChart.jsx`

The `/rectify` response now includes `gap_label` and `evidence_label`. Show them above the Top3 cards.

- [ ] **Step 1: Store indicators in state**

Find `const [rectifyResult, setRectifyResult] = useState(null)` — `rectifyResult` already holds the full API response including the new fields.

In `handleRectify`, `setRectifyResult(data)` already stores the whole response, so `rectifyResult.gap_label` and `rectifyResult.evidence_label` are available automatically.

- [ ] **Step 2: Add indicator row above the Top3 list**

Find the section starting with:
```jsx
<div style={{ color: '#9a8acc', fontSize: '0.75rem', ... }}>
  Top 3 候选时间
</div>
```

Add immediately after that heading div:

```jsx
{(rectifyResult.gap_label || rectifyResult.evidence_label) && (
  <div style={{ display: 'flex', gap: '16px', marginBottom: '12px', fontSize: '0.72rem', color: '#7a7a9a' }}>
    {rectifyResult.gap_label && (
      <span>分辨力：<span style={{ color: rectifyResult.gap_label === '高' ? '#66cc88' : rectifyResult.gap_label === '中' ? '#c9a84c' : '#ff7070' }}>{rectifyResult.gap_label}</span></span>
    )}
    {rectifyResult.evidence_label && (
      <span>证据强度：<span style={{ color: rectifyResult.evidence_label === '强' ? '#66cc88' : rectifyResult.evidence_label === '中' ? '#c9a84c' : '#ff7070' }}>{rectifyResult.evidence_label}</span></span>
    )}
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/NatalChart.jsx
git commit -m "feat(rectify): show gap_label and evidence_label indicators above Top3 results"
```

---

## Task 8: Update ARCHITECTURE.md + push

**Files:**
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Add `/api/rectify/compare` to the API endpoints table** in the rectification section.

- [ ] **Step 2: Push both remotes**

```bash
git push origin main && git push hf main
```

---

## Testing Checklist (for human review after completion)

1. **v1.3 appears in version selector** — open rectification panel, confirm v1.3 is in the dropdown
2. **Indicators show** — run rectification with any events, confirm 分辨力/证据强度 appear above Top3
3. **Compare endpoint** — call `POST /api/rectify/compare` with a known birth time, confirm all 4 versions appear in results sorted by `error_minutes`
4. **Turning point normalization** — mark 3 events as turning points; confirm the run completes without the 5-hour error regression
5. **Default version unchanged** — confirm the frontend defaults to v1.0, not v1.3
