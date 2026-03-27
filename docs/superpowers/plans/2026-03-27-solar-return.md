# Solar Return Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fully functional Solar Return page that lets users select a saved natal chart, input current location, display a bi-wheel SVG, and generate a RAG-backed AI annual report using a 6-layer rule engine.

**Architecture:** Rule engine (`_compute_sr_theme_scores`) extracts 8-theme scores from SR chart data → `analyze_solar_return()` calls `rag_generate(k=5)` → results cached in new `solar_return_cache` DB table → new `POST /api/interpret/solar-return` endpoint → React `SolarReturn.jsx` calls existing `/api/solar-return` (calculation) + `/api/svg_chart` (bi-wheel) + new interpret endpoint.

**Tech Stack:** FastAPI, Python 3.12, Kerykeion 4.x, Qdrant RAG, Gemini, SQLite/Turso, React/Vite

**Spec:** `docs/superpowers/specs/2026-03-27-solar-return-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `astrology_api/app/db.py` | Modify | Add `_CREATE_SR_CACHE` DDL, `db_get_sr_cache()`, `db_save_sr_cache()`, update `create_tables()` |
| `astrology_api/app/rag.py` | Modify | Add `_compute_sr_theme_scores()` rule engine + `analyze_solar_return()` AI function |
| `astrology_api/app/api/interpret_router.py` | Modify | Add `POST /api/interpret/solar-return` endpoint |
| `astrology_api/tests/test_solar_return.py` | Create | Unit tests for rule engine + DB helpers + endpoint |
| `frontend/src/pages/SolarReturn.jsx` | Rewrite | Full UI: chart selector, location search, SVG bi-wheel, AI report |

---

## Task 1: DB Cache Table + Helpers

**Files:**
- Modify: `astrology_api/app/db.py:220-228` (create_tables loop)

- [ ] **Step 1: Write the failing test**

Create `astrology_api/tests/test_solar_return.py`:

```python
"""Tests for solar return DB cache helpers."""
import os, sys, pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force SQLite mode for tests
os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)

from app.db import db_get_sr_cache, db_save_sr_cache, create_tables

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    import app.db as db_module
    monkeypatch.setattr(db_module, "_db_path", db_file)
    monkeypatch.setattr(db_module, "USE_TURSO", False)
    create_tables()

def test_sr_cache_miss():
    result = db_get_sr_cache(1, 2026, "abc123")
    assert result is None

def test_sr_cache_save_and_hit():
    db_save_sr_cache(1, 2026, "abc123", '{"keywords": ["test"]}')
    result = db_get_sr_cache(1, 2026, "abc123")
    assert result is not None
    assert result["keywords"] == ["test"]

def test_sr_cache_insert_or_replace():
    db_save_sr_cache(1, 2026, "abc123", '{"v": 1}')
    db_save_sr_cache(1, 2026, "abc123", '{"v": 2}')  # should not raise
    result = db_get_sr_cache(1, 2026, "abc123")
    assert result["v"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py -v
```
Expected: `ImportError: cannot import name 'db_get_sr_cache'`

- [ ] **Step 3: Add DDL constant to `db.py`**

After the `_CREATE_LIFE_EVENTS` block (around line 96), add:

```python
_CREATE_SR_CACHE = """
CREATE TABLE IF NOT EXISTS solar_return_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id      INTEGER NOT NULL,
    return_year   INTEGER NOT NULL,
    location_hash TEXT    NOT NULL,
    result_json   TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(chart_id, return_year, location_hash)
)
"""
```

- [ ] **Step 4: Add `_CREATE_SR_CACHE` to the `create_tables()` DDL loop**

In `create_tables()` (line ~221), change:
```python
for ddl in [_CREATE_TABLE, _CREATE_TRANSIT_CACHE, _CREATE_TRANSIT_OVERALL,
            _CREATE_PLANET_CACHE, _CREATE_SYNASTRY_CACHE, _CREATE_QUERY_ANALYTICS,
            _CREATE_LIFE_EVENTS]:
```
to:
```python
for ddl in [_CREATE_TABLE, _CREATE_TRANSIT_CACHE, _CREATE_TRANSIT_OVERALL,
            _CREATE_PLANET_CACHE, _CREATE_SYNASTRY_CACHE, _CREATE_QUERY_ANALYTICS,
            _CREATE_LIFE_EVENTS, _CREATE_SR_CACHE]:
```

- [ ] **Step 5: Add DB helper functions to `db.py`**

Add after the existing `db_save_synastry_cache` function:

```python
def db_get_sr_cache(chart_id: int, return_year: int, location_hash: str) -> dict | None:
    """Return cached solar return result (json.loads'd), or None on miss."""
    sql = "SELECT result_json FROM solar_return_cache WHERE chart_id=? AND return_year=? AND location_hash=?"
    if USE_TURSO:
        rows = _to_dicts(_turso_exec(sql, [chart_id, return_year, location_hash]))
        if not rows:
            return None
        return json.loads(rows[0]["result_json"])
    row = _sqlite_fetchone(sql, [chart_id, return_year, location_hash])
    if not row:
        return None
    return json.loads(row["result_json"])


def db_save_sr_cache(chart_id: int, return_year: int, location_hash: str, result_json: str) -> None:
    """INSERT OR REPLACE solar return cache row."""
    sql = """
    INSERT OR REPLACE INTO solar_return_cache (chart_id, return_year, location_hash, result_json)
    VALUES (?, ?, ?, ?)
    """
    if USE_TURSO:
        _turso_exec(sql, [chart_id, return_year, location_hash, result_json])
    else:
        _sqlite_write(sql, [chart_id, return_year, location_hash, result_json])
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py::test_sr_cache_miss tests/test_solar_return.py::test_sr_cache_save_and_hit tests/test_solar_return.py::test_sr_cache_insert_or_replace -v
```
Expected: 3 PASSED

- [ ] **Step 7: Commit**

```bash
git add astrology_api/app/db.py astrology_api/tests/test_solar_return.py
git commit -m "feat(db): add solar_return_cache table and DB helpers"
```

---

## Task 2: Rule Engine `_compute_sr_theme_scores()`

**Files:**
- Modify: `astrology_api/app/rag.py` (add after `_compute_chart_facts`)
- Modify: `astrology_api/tests/test_solar_return.py` (add rule engine tests)

- [ ] **Step 1: Write failing tests for the rule engine**

Append to `astrology_api/tests/test_solar_return.py`:

```python
"""Tests for _compute_sr_theme_scores rule engine."""
# Note: import after DB fixture so RAG module isn't loaded yet
def _import_rule_engine():
    from app.rag import _compute_sr_theme_scores
    return _compute_sr_theme_scores

def _make_planets(sun_house=10, moon_house=7, jupiter_house=9,
                  saturn_house=2, venus_house=7, mars_house=1,
                  sun_lon=280.0):
    """Build minimal sr_planets dict for testing."""
    def p(house, lon=0.0, name_orig="Sun", sign="Capricorn"):
        return {"house": house, "longitude": lon,
                "name_original": name_orig, "sign_original": sign,
                "sign": sign, "retrograde": False}
    return {
        "sun":     p(sun_house, sun_lon, "Sun", "Capricorn"),
        "moon":    p(moon_house, 100.0, "Moon", "Libra"),
        "jupiter": p(jupiter_house, 50.0, "Jupiter", "Gemini"),
        "saturn":  p(saturn_house, 310.0, "Saturn", "Aquarius"),
        "venus":   p(venus_house, 270.0, "Venus", "Sagittarius"),
        "mars":    p(mars_house, 20.0, "Mars", "Aries"),
    }

def _make_houses(asc_sign="Capricorn"):
    """Build minimal sr_houses dict."""
    return {
        "1": {"sign_original": asc_sign, "sign": asc_sign, "longitude": 280.0},
        "2": {"sign_original": "Aquarius", "sign": "Aquarius", "longitude": 310.0},
        "3": {"sign_original": "Pisces", "sign": "Pisces", "longitude": 340.0},
        "4": {"sign_original": "Aries", "sign": "Aries", "longitude": 10.0},
        "5": {"sign_original": "Taurus", "sign": "Taurus", "longitude": 40.0},
        "6": {"sign_original": "Gemini", "sign": "Gemini", "longitude": 70.0},
        "7": {"sign_original": "Cancer", "sign": "Cancer", "longitude": 100.0},
        "8": {"sign_original": "Leo", "sign": "Leo", "longitude": 130.0},
        "9": {"sign_original": "Virgo", "sign": "Virgo", "longitude": 160.0},
        "10": {"sign_original": "Libra", "sign": "Libra", "longitude": 190.0},
        "11": {"sign_original": "Scorpio", "sign": "Scorpio", "longitude": 220.0},
        "12": {"sign_original": "Sagittarius", "sign": "Sagittarius", "longitude": 250.0},
    }

def _make_natal_houses():
    """Natal houses: ASC at 10° Aries (lon=10). SR ASC at 280° = Capricorn = natal 10th house."""
    return {
        "1":  {"sign_original": "Aries",       "longitude": 10.0},
        "2":  {"sign_original": "Taurus",       "longitude": 40.0},
        "3":  {"sign_original": "Gemini",       "longitude": 70.0},
        "4":  {"sign_original": "Cancer",       "longitude": 100.0},
        "5":  {"sign_original": "Leo",          "longitude": 130.0},
        "6":  {"sign_original": "Virgo",        "longitude": 160.0},
        "7":  {"sign_original": "Libra",        "longitude": 190.0},
        "8":  {"sign_original": "Scorpio",      "longitude": 220.0},
        "9":  {"sign_original": "Sagittarius",  "longitude": 250.0},
        "10": {"sign_original": "Capricorn",    "longitude": 280.0},
        "11": {"sign_original": "Aquarius",     "longitude": 310.0},
        "12": {"sign_original": "Pisces",       "longitude": 340.0},
    }

def test_rule_engine_returns_required_keys():
    fn = _import_rule_engine()
    result = fn(
        sr_planets=_make_planets(),
        sr_houses=_make_houses(),
        natal_planets={},
        natal_houses=_make_natal_houses(),
        sr_asc_degree=280.0,
    )
    assert "core_facts" in result
    assert "theme_scores" in result
    assert "top_themes" in result
    assert "modifiers" in result
    assert "confidence" in result
    for theme in ["self_identity", "relationships", "career_public", "home_family",
                  "money_resources", "health_routine", "learning_expansion", "inner_healing"]:
        assert theme in result["theme_scores"]

def test_sun_in_10th_boosts_career():
    fn = _import_rule_engine()
    result = fn(
        sr_planets=_make_planets(sun_house=10),
        sr_houses=_make_houses(),
        natal_planets={},
        natal_houses=_make_natal_houses(),
        sr_asc_degree=280.0,
    )
    assert result["theme_scores"]["career_public"] > result["theme_scores"]["home_family"]

def test_sr_asc_in_natal_4th_boosts_home():
    fn = _import_rule_engine()
    # SR ASC at 100.0° = natal 4th house (100-130)
    result = fn(
        sr_planets=_make_planets(sun_house=1),
        sr_houses=_make_houses(),
        natal_planets={},
        natal_houses=_make_natal_houses(),
        sr_asc_degree=100.0,
    )
    assert result["theme_scores"]["home_family"] >= 6  # Layer 1 alone gives 6

def test_top_themes_sorted_descending():
    fn = _import_rule_engine()
    result = fn(
        sr_planets=_make_planets(),
        sr_houses=_make_houses(),
        natal_planets={},
        natal_houses=_make_natal_houses(),
        sr_asc_degree=280.0,
    )
    scores = [t["score"] for t in result["top_themes"]]
    assert scores == sorted(scores, reverse=True)

def test_modifier_sun_conjunct_saturn():
    fn = _import_rule_engine()
    # Sun at 280°, Saturn at 281° → conjunct within 3°
    planets = _make_planets(sun_house=10)
    planets["saturn"]["longitude"] = 281.0
    planets["sun"]["longitude"] = 280.0
    result = fn(
        sr_planets=planets,
        sr_houses=_make_houses(),
        natal_planets={},
        natal_houses=_make_natal_houses(),
        sr_asc_degree=280.0,
    )
    assert "restructuring" in result["modifiers"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py -k "rule_engine or sun_in or sr_asc or top_themes or modifier" -v
```
Expected: `ImportError: cannot import name '_compute_sr_theme_scores'`

- [ ] **Step 3: Implement `_compute_sr_theme_scores()` in `rag.py`**

Add after the `_compute_chart_facts()` function (around line 1385). Insert the following:

```python
# ── Solar Return Rule Engine ───────────────────────────────────────────────

_SR_ASC_NATAL_HOUSE_WEIGHTS = {
    "1":  {"self_identity": 6},
    "2":  {"money_resources": 5},
    "3":  {"learning_expansion": 4},
    "4":  {"home_family": 6},
    "5":  {"relationships": 3},
    "6":  {"health_routine": 5},
    "7":  {"relationships": 5},
    "8":  {"inner_healing": 4, "money_resources": 2},
    "9":  {"learning_expansion": 5},
    "10": {"career_public": 6},
    "11": {"career_public": 2, "learning_expansion": 2},
    "12": {"inner_healing": 5},
}

_SR_SUN_HOUSE_WEIGHTS = {
    "1":  {"self_identity": 5},
    "2":  {"money_resources": 5},
    "3":  {"learning_expansion": 3},
    "4":  {"home_family": 5, "inner_healing": 1},
    "5":  {"self_identity": 2, "relationships": 2},
    "6":  {"health_routine": 5},
    "7":  {"relationships": 5},
    "8":  {"money_resources": 2, "inner_healing": 4},
    "9":  {"learning_expansion": 5},
    "10": {"career_public": 5},
    "11": {"career_public": 1, "learning_expansion": 2, "relationships": 1},
    "12": {"inner_healing": 5, "health_routine": 1},
}

_SR_MOON_HOUSE_WEIGHTS = {
    "1":  {"self_identity": 3},
    "2":  {"money_resources": 2},
    "3":  {"learning_expansion": 2},
    "4":  {"home_family": 4},
    "5":  {"relationships": 2, "self_identity": 1},
    "6":  {"health_routine": 4},
    "7":  {"relationships": 4},
    "8":  {"inner_healing": 3, "money_resources": 1},
    "9":  {"learning_expansion": 4},
    "10": {"career_public": 4},
    "11": {"relationships": 2, "learning_expansion": 1},
    "12": {"inner_healing": 4},
}

_SR_PLANET_HOUSE_WEIGHTS = {
    "jupiter": {
        "2": {"money_resources": 2}, "4": {"home_family": 2},
        "7": {"relationships": 3},   "9": {"learning_expansion": 3},
        "10": {"career_public": 3},  "11": {"learning_expansion": 1, "career_public": 1},
    },
    "saturn": {
        "2": {"money_resources": 3}, "6": {"health_routine": 3},
        "7": {"relationships": 2},   "10": {"career_public": 3},
        "12": {"inner_healing": 3},
    },
    "venus": {
        "5": {"relationships": 2},   "7": {"relationships": 3},
        "2": {"money_resources": 1}, "10": {"career_public": 1},
    },
    "mars": {
        "1": {"self_identity": 2},   "6": {"health_routine": 2},
        "7": {"relationships": 1},   "10": {"career_public": 2},
        "8": {"inner_healing": 2, "money_resources": 1},
    },
}

_SR_ANGULAR_THEMES = {"1": "self_identity", "4": "home_family", "7": "relationships", "10": "career_public"}

_SR_TRADITIONAL_RULER = {
    "Aries": "mars",    "Taurus": "venus",   "Gemini": "mercury",
    "Cancer": "moon",   "Leo": "sun",        "Virgo": "mercury",
    "Libra": "venus",   "Scorpio": "mars",   "Sagittarius": "jupiter",
    "Capricorn": "saturn", "Aquarius": "saturn", "Pisces": "jupiter",
}

_SR_THEME_NAMES_ZH = {
    "self_identity": "自我身份",
    "relationships": "人际关系",
    "career_public": "事业公众",
    "home_family": "家庭居所",
    "money_resources": "财务资源",
    "health_routine": "健康日常",
    "learning_expansion": "学习扩展",
    "inner_healing": "内在疗愈",
}


def _sr_find_natal_house(asc_degree: float, natal_houses: dict) -> str | None:
    """Return the natal house number (str) that contains asc_degree."""
    house_cusps = []
    for num in range(1, 13):
        h = natal_houses.get(str(num), {})
        lon = h.get("longitude")
        if lon is not None:
            house_cusps.append((num, float(lon)))
    if not house_cusps:
        return None
    house_cusps.sort(key=lambda x: x[1])
    asc = float(asc_degree) % 360
    for i, (num, cusp) in enumerate(house_cusps):
        next_cusp = house_cusps[(i + 1) % 12][1]
        if next_cusp <= cusp:  # wraps around 0°
            if asc >= cusp or asc < next_cusp:
                return str(num)
        else:
            if cusp <= asc < next_cusp:
                return str(num)
    return str(house_cusps[0][0])


def _compute_sr_theme_scores(
    sr_planets: dict,
    sr_houses: dict,
    natal_planets: dict,
    natal_houses: dict,
    sr_asc_degree: float,
) -> dict:
    """
    6-layer SR theme scoring engine.
    Returns core_facts, theme_scores (8 themes), top_themes, modifiers, confidence.
    """
    scores: dict[str, float] = {
        "self_identity": 0, "relationships": 0, "career_public": 0,
        "home_family": 0, "money_resources": 0, "health_routine": 0,
        "learning_expansion": 0, "inner_healing": 0,
    }
    facts: list[str] = []
    modifiers: list[str] = []

    def add(weights: dict, label: str):
        for theme, pts in weights.items():
            scores[theme] = scores.get(theme, 0) + pts
        facts.append(label)

    # ── Layer 1: SR ASC in natal house ────────────────────────────────────
    natal_house = _sr_find_natal_house(sr_asc_degree, natal_houses)
    if natal_house and natal_house in _SR_ASC_NATAL_HOUSE_WEIGHTS:
        add(_SR_ASC_NATAL_HOUSE_WEIGHTS[natal_house], f"SR上升落本命第{natal_house}宫")

    # ── Layer 2: SR Sun house ──────────────────────────────────────────────
    sun = sr_planets.get("sun", {})
    sun_house = str(sun.get("house", "")) if sun.get("house") else ""
    if sun_house in _SR_SUN_HOUSE_WEIGHTS:
        add(_SR_SUN_HOUSE_WEIGHTS[sun_house], f"SR太阳落第{sun_house}宫")

    # ── Layer 3: SR Moon house ─────────────────────────────────────────────
    moon = sr_planets.get("moon", {})
    moon_house = str(moon.get("house", "")) if moon.get("house") else ""
    if moon_house in _SR_MOON_HOUSE_WEIGHTS:
        add(_SR_MOON_HOUSE_WEIGHTS[moon_house], f"SR月亮落第{moon_house}宫")

    # ── Layer 4: SR ASC ruler house ────────────────────────────────────────
    asc_sign_raw = sr_houses.get("1", {}).get("sign_original") or sr_houses.get("1", {}).get("sign")
    if asc_sign_raw:
        ruler_key = _SR_TRADITIONAL_RULER.get(asc_sign_raw)
        if ruler_key and ruler_key in sr_planets:
            ruler_planet = sr_planets[ruler_key]
            ruler_house = str(ruler_planet.get("house", ""))
            if ruler_house in _SR_SUN_HOUSE_WEIGHTS:
                ruler_weights = {k: v * 2 // 5 if v * 2 // 5 > 0 else 1
                                 for k, v in _SR_SUN_HOUSE_WEIGHTS[ruler_house].items()}
                # Simplified: flat +2 per theme in that house, +1 if angular
                for theme in _SR_SUN_HOUSE_WEIGHTS[ruler_house]:
                    scores[theme] = scores.get(theme, 0) + 2
                if ruler_house in _SR_ANGULAR_THEMES:
                    theme = _SR_ANGULAR_THEMES[ruler_house]
                    scores[theme] = scores.get(theme, 0) + 1
                facts.append(f"上升守护星{translate_planet(ruler_key, 'zh')}落SR第{ruler_house}宫")

    # ── Layer 5: Angular house emphasis ───────────────────────────────────
    house_planet_count: dict[str, int] = {}
    for key, p in sr_planets.items():
        h = str(p.get("house", ""))
        if h in _SR_ANGULAR_THEMES:
            house_planet_count[h] = house_planet_count.get(h, 0) + 1
    for h, cnt in house_planet_count.items():
        if cnt >= 2:
            theme = _SR_ANGULAR_THEMES[h]
            bonus = min(cnt, 3)
            scores[theme] = scores.get(theme, 0) + bonus
            facts.append(f"第{h}宫角宫强调（{cnt}颗行星）")

    # ── Layer 6: Jupiter / Saturn / Venus / Mars house ─────────────────────
    for planet_key, house_map in _SR_PLANET_HOUSE_WEIGHTS.items():
        p = sr_planets.get(planet_key, {})
        p_house = str(p.get("house", ""))
        if p_house in house_map:
            add(house_map[p_house], f"{translate_planet(planet_key, 'zh')}落SR第{p_house}宫")

    # ── Modifier aspects (orb ≤ 3°) ────────────────────────────────────────
    _ASPECT_MODIFIERS = [
        ("sun", "saturn",  [0, 90, 180], "restructuring"),
        ("sun", "jupiter", [0, 90, 180], "expansion"),
        ("sun", "uranus",  [0],          "change"),
        ("sun", "neptune", [0],          "dissolution"),
        ("sun", "pluto",   [0],          "transformation"),
        ("moon", "saturn", [0],          "emotional_weight"),
    ]
    sun_lon  = float(sr_planets.get("sun",  {}).get("longitude", -999))
    moon_lon = float(sr_planets.get("moon", {}).get("longitude", -999))

    for p1_key, p2_key, aspect_angles, label in _ASPECT_MODIFIERS:
        p1_lon = float(sr_planets.get(p1_key, {}).get("longitude", -999))
        p2_lon = float(sr_planets.get(p2_key, {}).get("longitude", -999))
        if p1_lon < 0 or p2_lon < 0:
            continue
        diff = abs(p1_lon - p2_lon) % 360
        if diff > 180:
            diff = 360 - diff
        for angle in aspect_angles:
            if abs(diff - angle) <= 3.0:
                if label not in modifiers:
                    modifiers.append(label)
                break

    # ── Compile output ─────────────────────────────────────────────────────
    total = sum(scores.values()) or 1
    top_themes = sorted(
        [{"theme": k, "score": int(v)} for k, v in scores.items()],
        key=lambda x: -x["score"]
    )[:3]

    max_possible = 6 + 5 + 4 + 3 + 3 + 3  # rough ceiling per strongest path
    confidence = round(min(max(score for score in scores.values()) / max_possible, 1.0), 2)

    return {
        "core_facts": facts,
        "theme_scores": {k: int(v) for k, v in scores.items()},
        "top_themes": top_themes,
        "modifiers": modifiers,
        "confidence": confidence,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py -k "rule_engine or sun_in or sr_asc or top_themes or modifier" -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/rag.py astrology_api/tests/test_solar_return.py
git commit -m "feat(rag): add _compute_sr_theme_scores 6-layer rule engine"
```

---

## Task 3: `analyze_solar_return()` AI Function in `rag.py`

**Files:**
- Modify: `astrology_api/app/rag.py` (add after `_compute_sr_theme_scores`)

- [ ] **Step 1: Write failing test**

Append to `astrology_api/tests/test_solar_return.py`:

```python
def test_analyze_solar_return_returns_required_fields(monkeypatch):
    """analyze_solar_return() must return all required response fields."""
    from app import rag as rag_module

    # Stub rag_generate to avoid real API call
    def fake_rag_generate(query, prompt, *, k=5, temperature=0.5):
        return ("年度主轴：家庭是今年核心。[1]\n建议1：...\n建议2：...\n建议3：...", [
            {"source": "AtecnicadasRevolucoesSolares", "score": 0.85, "cited": True, "text": "..."}
        ])
    monkeypatch.setattr(rag_module, "rag_generate", fake_rag_generate)

    result = rag_module.analyze_solar_return(
        sr_planets=_make_planets(),
        sr_houses=_make_houses(),
        natal_chart_data={"planets": {}, "houses": _make_natal_houses(), "aspects": []},
        sr_asc_degree=280.0,
        return_year=2026,
    )
    for key in ["keywords", "summary", "themes", "domains", "suggestions",
                "sources", "model_used", "theme_scores"]:
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["sources"], list)
    assert isinstance(result["themes"], list)
    assert len(result["themes"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py::test_analyze_solar_return_returns_required_fields -v
```
Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Implement `analyze_solar_return()` in `rag.py`**

Add immediately after `_compute_sr_theme_scores()`:

```python
def analyze_solar_return(
    sr_planets: dict,
    sr_houses: dict,
    natal_chart_data: dict,
    sr_asc_degree: float,
    return_year: int,
    language: str = "zh",
) -> dict:
    """
    Generate AI annual report for a Solar Return chart.
    Returns: keywords, summary, themes (top3), domains (8), suggestions, sources,
             model_used, theme_scores.
    """
    natal_planets = natal_chart_data.get("planets", {})
    natal_houses  = natal_chart_data.get("houses", {})

    analysis = _compute_sr_theme_scores(
        sr_planets=sr_planets,
        sr_houses=sr_houses,
        natal_planets=natal_planets,
        natal_houses=natal_houses,
        sr_asc_degree=sr_asc_degree,
    )

    top3 = analysis["top_themes"][:3]
    top3_zh = "、".join(_SR_THEME_NAMES_ZH.get(t["theme"], t["theme"]) for t in top3)
    modifiers_zh = "、".join(analysis["modifiers"]) if analysis["modifiers"] else "无特别修正"
    facts_text = "\n".join(f"- {f}" for f in analysis["core_facts"])
    scores_text = "\n".join(
        f"  {_SR_THEME_NAMES_ZH.get(k, k)}: {v}"
        for k, v in sorted(analysis["theme_scores"].items(), key=lambda x: -x[1])
    )

    rag_query = (
        f"solar return {return_year} annual themes {top3_zh} "
        f"house interpretation yearly forecast"
    )

    prompt = f"""请根据以下太阳回归年度分析数据，生成一份面向普通用户的{return_year}年度报告（中文）。

【规则引擎分析结果】
确定性事实：
{facts_text}

年度主题得分（从高到低）：
{scores_text}

修正标签：{modifiers_zh}
置信度：{analysis["confidence"]}

【输出要求】
请严格按照以下 JSON 结构返回（不要在 JSON 外加任何解释文字）：
{{
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "summary": "100-150字的年度核心主轴段落",
  "themes": [
    {{
      "theme": "home_family",
      "score": 79,
      "name_zh": "家庭居所",
      "analysis": "80-120字分析",
      "evidence": ["依据1", "依据2"]
    }},
    ... (top 3)
  ],
  "domains": {{
    "career_public": "50-80字",
    "relationships": "50-80字",
    "money_resources": "50-80字",
    "home_family": "50-80字",
    "health_routine": "50-80字",
    "learning_expansion": "50-80字",
    "inner_healing": "50-80字",
    "self_identity": "50-80字"
  }},
  "suggestions": ["建议1（具体行动）", "建议2", "建议3"],
  "source_refs": {{"<参考编号>": "<20字中文概括>"}}
}}

规则：
- 只使用输入中给出的信息，不要杜撰相位或宫位
- 使用"倾向、重点、可能、容易"等概率性表达，不做绝对预言
- themes 必须按得分从高到低排列，且与 theme_scores 一致
- 对健康、财务等敏感主题避免确定性建议
"""

    answer, sources = rag_generate(rag_query, prompt, k=5, temperature=0.35)
    model_used = get_last_model_used()

    # Parse JSON from AI response
    try:
        parsed = _parse_json(answer)
    except Exception:
        parsed = {}

    # Build themes list from top3 if AI response missing
    themes_out = parsed.get("themes", [])
    if not themes_out:
        themes_out = [
            {
                "theme": t["theme"],
                "score": t["score"],
                "name_zh": _SR_THEME_NAMES_ZH.get(t["theme"], t["theme"]),
                "analysis": "",
                "evidence": [],
            }
            for t in top3
        ]

    return {
        "keywords":     parsed.get("keywords", []),
        "summary":      parsed.get("summary", answer[:200] if answer else ""),
        "themes":       themes_out,
        "domains":      parsed.get("domains", {}),
        "suggestions":  parsed.get("suggestions", []),
        "sources":      sources,
        "model_used":   model_used,
        "theme_scores": analysis["theme_scores"],
    }
```

- [ ] **Step 4: Run tests**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py::test_analyze_solar_return_returns_required_fields -v
```
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/rag.py astrology_api/tests/test_solar_return.py
git commit -m "feat(rag): add analyze_solar_return AI report function"
```

---

## Task 4: New API Endpoint `POST /api/interpret/solar-return`

**Files:**
- Modify: `astrology_api/app/api/interpret_router.py`
- Modify: `astrology_api/tests/test_solar_return.py`

- [ ] **Step 1: Write failing endpoint test**

Append to `astrology_api/tests/test_solar_return.py`:

```python
def test_solar_return_endpoint_requires_saved_chart():
    """chart_id=0 must be rejected."""
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    resp = client.post("/api/interpret/solar-return", json={
        "chart_id": 0,
        "natal_chart_data": {"planets": {}, "houses": {}, "aspects": []},
        "sr_planets": {},
        "sr_houses": {},
        "sr_asc_degree": 0.0,
        "return_year": 2026,
        "location_lat": 31.23,
        "location_lon": 121.47,
        "language": "zh",
        "force_refresh": False,
    })
    assert resp.status_code in (400, 403, 422)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py::test_solar_return_endpoint_requires_saved_chart -v
```
Expected: FAIL (404 - endpoint doesn't exist yet)

- [ ] **Step 3: Add the endpoint to `interpret_router.py`**

Add at the end of `astrology_api/app/api/interpret_router.py`:

```python
class SolarReturnInterpretRequest(BaseModel):
    chart_id: int
    natal_chart_data: Dict[str, Any]
    sr_planets: Dict[str, Any]
    sr_houses: Dict[str, Any]
    sr_asc_degree: float
    return_year: int
    location_lat: float
    location_lon: float
    language: str = "zh"
    force_refresh: bool = False


@router.post("/interpret/solar-return")
async def interpret_solar_return(body: SolarReturnInterpretRequest):
    """
    太阳回归年度报告：
    1. 规则引擎打分（_compute_sr_theme_scores）
    2. RAG + Gemini 生成报告（analyze_solar_return）
    3. DB 缓存（solar_return_cache）
    4. Analytics 记录
    """
    import hashlib, json
    from ..db import db_get_sr_cache, db_save_sr_cache

    if body.chart_id <= 0:
        raise HTTPException(status_code=400, detail="chart_id must be > 0 (guest mode not supported)")

    location_hash = hashlib.md5(
        f"{body.location_lat:.4f},{body.location_lon:.4f}".encode()
    ).hexdigest()[:12]

    # ── Cache check ────────────────────────────────────────────────────────
    if not body.force_refresh:
        cached = db_get_sr_cache(body.chart_id, body.return_year, location_hash)
        if cached:
            cached["model_used"] = "cached"
            return cached

    # ── Generate ───────────────────────────────────────────────────────────
    try:
        from ..rag import analyze_solar_return
        result = analyze_solar_return(
            sr_planets=body.sr_planets,
            sr_houses=body.sr_houses,
            natal_chart_data=body.natal_chart_data,
            sr_asc_degree=body.sr_asc_degree,
            return_year=body.return_year,
            language=body.language,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[SR INTERPRET ERROR]\n{traceback.format_exc()}", flush=True)
        raise HTTPException(status_code=500, detail=f"Solar return interpretation error: {e}")

    # ── Cache write ────────────────────────────────────────────────────────
    db_save_sr_cache(body.chart_id, body.return_year, location_hash,
                     json.dumps(result, ensure_ascii=False))

    # ── Analytics ──────────────────────────────────────────────────────────
    top_themes = result.get("theme_scores", {})
    top3 = sorted(top_themes.items(), key=lambda x: -x[1])[:3]
    query = f"solar_return {body.return_year} " + " ".join(t[0] for t in top3)
    asyncio.create_task(_log_analytics(query, result))

    return result
```

- [ ] **Step 4: Run test**

```bash
cd astrology_api
python -m pytest tests/test_solar_return.py::test_solar_return_endpoint_requires_saved_chart -v
```
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/api/interpret_router.py astrology_api/tests/test_solar_return.py
git commit -m "feat(api): add POST /api/interpret/solar-return endpoint"
```

---

## Task 5: Frontend — `SolarReturn.jsx`

**Files:**
- Rewrite: `frontend/src/pages/SolarReturn.jsx`

> No automated frontend tests. Manual testing steps are provided at the end.

- [ ] **Step 1: Implement `SolarReturn.jsx`**

Replace the entire content of `frontend/src/pages/SolarReturn.jsx`:

```jsx
import { useState, useEffect } from 'react'
import LocationSearch from '../components/LocationSearch'
import { SourcesSection } from '../components/AIPanel'
import { useAuth } from '../contexts/AuthContext'
import ReactMarkdown from 'react-markdown'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const SECTION_STYLE = {
  backgroundColor: '#0d0d22',
  border: '1px solid #1e1e4a',
  borderRadius: '12px',
  padding: '20px',
  marginBottom: '16px',
}

const LABEL = { color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: '4px' }
const INPUT = { backgroundColor: '#0d0d22', border: '1px solid #2a2a5a', color: '#e8e8ff', borderRadius: '6px', padding: '7px 10px', width: '100%', outline: 'none', fontSize: '0.875rem', boxSizing: 'border-box' }
const BTN_PRIMARY = { backgroundColor: '#c9a84c', color: '#0a0a1a', border: 'none', borderRadius: '8px', padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }
const BTN_SECONDARY = { backgroundColor: 'transparent', color: '#6666aa', border: '1px solid #2a2a5a', borderRadius: '6px', padding: '6px 14px', cursor: 'pointer', fontSize: '0.8rem' }

const THEME_NAMES = {
  home_family: '家庭居所', relationships: '人际关系',
  career_public: '事业公众', inner_healing: '内在疗愈',
  money_resources: '财务资源', health_routine: '健康日常',
  learning_expansion: '学习扩展', self_identity: '自我身份',
}

export default function SolarReturn() {
  const { isAuthenticated, authHeaders } = useAuth()
  const [savedCharts, setSavedCharts] = useState([])
  const [selectedChartId, setSelectedChartId] = useState('')
  const [selectedChart, setSelectedChart] = useState(null)
  const [location, setLocation] = useState({ latitude: '', longitude: '', locationName: '' })
  const [svgContent, setSvgContent] = useState('')
  const [srData, setSrData] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [error, setError] = useState('')
  const currentYear = new Date().getFullYear()

  // Load saved charts
  useEffect(() => {
    if (!isAuthenticated) return
    fetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      .then(r => r.json())
      .then(data => setSavedCharts(Array.isArray(data) ? data : []))
      .catch(() => setSavedCharts([]))
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleChartSelect(e) {
    const id = e.target.value
    setSelectedChartId(id)
    setSelectedChart(null)
    setSrData(null)
    setSvgContent('')
    setReport(null)
    if (!id) return
    try {
      const res = await fetch(`${API_BASE}/api/charts/${id}`, { headers: authHeaders() })
      if (res.ok) setSelectedChart(await res.json())
    } catch { /* ignore */ }
  }

  const canCalculate = selectedChart && location.latitude && location.longitude

  async function handleCalculate() {
    if (!canCalculate) return
    setLoading(true)
    setError('')
    setSrData(null)
    setSvgContent('')
    setReport(null)
    try {
      // 1. Calculate SR chart
      const srRes = await fetch(`${API_BASE}/api/solar-return`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          natal_chart: {
            name: selectedChart.name,
            year: selectedChart.birth_year, month: selectedChart.birth_month,
            day: selectedChart.birth_day,   hour: selectedChart.birth_hour,
            minute: selectedChart.birth_minute,
            latitude: selectedChart.latitude, longitude: selectedChart.longitude,
            tz_str: selectedChart.tz_str,     house_system: selectedChart.house_system,
            language: 'zh',
          },
          return_year: currentYear,
          location_latitude: parseFloat(location.latitude),
          location_longitude: parseFloat(location.longitude),
          location_tz_str: selectedChart.tz_str,
          language: 'zh',
          include_natal_comparison: false,
          include_interpretations: false,
        }),
      })
      if (!srRes.ok) throw new Error(`SR calculation failed: ${srRes.status}`)
      const sr = await srRes.json()
      setSrData(sr)

      // 2. Get bi-wheel SVG
      const svgRes = await fetch(`${API_BASE}/api/svg_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          natal_chart: {
            name: selectedChart.name,
            year: selectedChart.birth_year, month: selectedChart.birth_month,
            day: selectedChart.birth_day,   hour: selectedChart.birth_hour,
            minute: selectedChart.birth_minute,
            latitude: selectedChart.latitude, longitude: selectedChart.longitude,
            tz_str: selectedChart.tz_str,     house_system: selectedChart.house_system,
            language: 'zh',
          },
          chart_type: 'transit',
          transit_chart: {
            year: parseInt(sr.return_date?.slice(0, 4) || currentYear),
            month: parseInt(sr.return_date?.slice(5, 7) || 1),
            day: parseInt(sr.return_date?.slice(8, 10) || 1),
            hour: parseInt(sr.return_date?.slice(11, 13) || 0),
            minute: parseInt(sr.return_date?.slice(14, 16) || 0),
            latitude: parseFloat(location.latitude),
            longitude: parseFloat(location.longitude),
            tz_str: selectedChart.tz_str,
            house_system: selectedChart.house_system,
            language: 'zh',
          },
          language: 'zh',
        }),
      })
      if (svgRes.ok) {
        const svgText = await svgRes.text()
        setSvgContent(svgText)
      }
    } catch (err) {
      setError(err.message || '计算失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  async function handleGenerateReport(forceRefresh = false) {
    if (!srData || !selectedChart) return
    setReportLoading(true)
    setError('')
    try {
      const srPlanets = srData.return_planets || {}
      const srHouses  = srData.return_houses  || {}
      // Determine SR ASC degree from houses
      const srAscDegree = parseFloat(srHouses['1']?.longitude || 0)

      const natalRes = await fetch(`${API_BASE}/api/natal_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          name: selectedChart.name,
          year: selectedChart.birth_year, month: selectedChart.birth_month,
          day: selectedChart.birth_day,   hour: selectedChart.birth_hour,
          minute: selectedChart.birth_minute,
          latitude: selectedChart.latitude, longitude: selectedChart.longitude,
          tz_str: selectedChart.tz_str,   house_system: selectedChart.house_system,
          language: 'zh',
        }),
      })
      const natalData = natalRes.ok ? await natalRes.json() : {}

      const res = await fetch(`${API_BASE}/api/interpret/solar-return`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          chart_id: parseInt(selectedChartId),
          natal_chart_data: natalData,
          sr_planets: srPlanets,
          sr_houses: srHouses,
          sr_asc_degree: srAscDegree,
          return_year: currentYear,
          location_lat: parseFloat(location.latitude),
          location_lon: parseFloat(location.longitude),
          language: 'zh',
          force_refresh: forceRefresh,
        }),
      })
      if (!res.ok) throw new Error(`报告生成失败: ${res.status}`)
      setReport(await res.json())
    } catch (err) {
      setError(err.message || '报告生成失败')
    } finally {
      setReportLoading(false)
    }
  }

  // Auto-trigger report after SR data loads
  useEffect(() => {
    if (srData && selectedChartId && !report && !reportLoading) {
      handleGenerateReport(false)
    }
  }, [srData]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!isAuthenticated) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#8888aa' }}>
        请先登录并保存本命盘，方可使用太阳回归功能。
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', padding: '0 16px 40px' }}>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ☀ 太阳回归 {currentYear}
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          基于当年太阳回归盘分析年度主题与人生重点
        </p>
      </div>

      {/* ① Input Area */}
      <div style={SECTION_STYLE}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          <div>
            <label style={LABEL}>选择本命盘</label>
            <select style={INPUT} value={selectedChartId} onChange={handleChartSelect}>
              <option value="">-- 请选择已保存的星盘 --</option>
              {savedCharts.map(c => (
                <option key={c.id} value={c.id}>{c.label || c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={LABEL}>当前所在地</label>
            <LocationSearch
              initialValue={location.locationName}
              latitude={location.latitude}
              longitude={location.longitude}
              onSelect={({ latitude, longitude, locationName }) =>
                setLocation({ latitude, longitude, locationName })
              }
            />
          </div>
        </div>
        <button
          style={{ ...BTN_PRIMARY, opacity: canCalculate ? 1 : 0.5 }}
          disabled={!canCalculate || loading}
          onClick={handleCalculate}
        >
          {loading ? '计算中…' : `计算 ${currentYear} 年太阳回归盘`}
        </button>
        {error && <p style={{ color: '#ff6666', fontSize: '0.8rem', marginTop: '8px' }}>{error}</p>}
      </div>

      {/* ② SVG Bi-Wheel */}
      {svgContent && (
        <div style={SECTION_STYLE}>
          <p style={{ color: '#8888aa', fontSize: '0.75rem', marginBottom: '12px' }}>
            外圈：{currentYear} 太阳回归盘 &nbsp;|&nbsp; 内圈：本命盘
          </p>
          <div
            style={{ width: '100%', maxWidth: '700px', margin: '0 auto' }}
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </div>
      )}

      {/* ③ AI Annual Report */}
      {(reportLoading || report) && (
        <div style={SECTION_STYLE}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ color: '#c9a84c', fontSize: '1rem', fontWeight: 600, margin: 0 }}>
              {currentYear} 年度报告
            </h2>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {report?.model_used && (
                <span style={{ color: '#6666aa', fontSize: '0.7rem', border: '1px solid #2a2a5a', borderRadius: '4px', padding: '2px 8px' }}>
                  {report.model_used === 'cached' ? '缓存' : report.model_used}
                </span>
              )}
              <button style={BTN_SECONDARY} disabled={reportLoading} onClick={() => handleGenerateReport(true)}>
                {reportLoading ? '生成中…' : '重新生成'}
              </button>
            </div>
          </div>

          {reportLoading && !report ? (
            <div style={{ color: '#6666aa', fontSize: '0.85rem' }}>AI 正在分析年度星盘…</div>
          ) : report && (
            <>
              {/* Keywords */}
              {report.keywords?.length > 0 && (
                <div style={{ marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {report.keywords.map((kw, i) => (
                    <span key={i} style={{ backgroundColor: '#1a1a3a', color: '#c9a84c', borderRadius: '20px', padding: '4px 12px', fontSize: '0.82rem', border: '1px solid #2a2a5a' }}>
                      {kw}
                    </span>
                  ))}
                </div>
              )}

              {/* Summary */}
              {report.summary && (
                <div style={{ marginBottom: '16px', color: '#ccccee', fontSize: '0.88rem', lineHeight: 1.7 }}>
                  <ReactMarkdown>{report.summary}</ReactMarkdown>
                </div>
              )}

              {/* Top 3 Themes */}
              {report.themes?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: '#8888aa', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '12px' }}>年度核心主题</h3>
                  {report.themes.map((t, i) => (
                    <div key={i} style={{ backgroundColor: '#0a0a1e', border: '1px solid #1e1e4a', borderRadius: '8px', padding: '14px', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ color: '#c9a84c', fontWeight: 600, fontSize: '0.9rem' }}>
                          {i + 1}. {t.name_zh || THEME_NAMES[t.theme] || t.theme}
                        </span>
                        <span style={{ color: '#6666aa', fontSize: '0.75rem' }}>得分 {t.score}</span>
                      </div>
                      {/* Score bar */}
                      <div style={{ height: '4px', backgroundColor: '#1e1e4a', borderRadius: '2px', marginBottom: '10px' }}>
                        <div style={{ height: '100%', width: `${Math.min(t.score / 1.5, 100)}%`, backgroundColor: '#c9a84c', borderRadius: '2px' }} />
                      </div>
                      {t.analysis && (
                        <p style={{ color: '#aaaacc', fontSize: '0.84rem', lineHeight: 1.6, margin: 0 }}>{t.analysis}</p>
                      )}
                      {t.evidence?.length > 0 && (
                        <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {t.evidence.map((ev, j) => (
                            <span key={j} style={{ color: '#666688', fontSize: '0.72rem', backgroundColor: '#12122a', borderRadius: '4px', padding: '2px 8px', border: '1px solid #1e1e3a' }}>{ev}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Eight Domains */}
              {report.domains && Object.keys(report.domains).length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: '#8888aa', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '12px' }}>八大生活领域</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
                    {Object.entries(report.domains).map(([key, text]) => (
                      <div key={key} style={{ backgroundColor: '#0a0a1e', border: '1px solid #1e1e4a', borderRadius: '8px', padding: '12px' }}>
                        <div style={{ color: '#9999cc', fontSize: '0.75rem', fontWeight: 600, marginBottom: '6px' }}>
                          {THEME_NAMES[key] || key}
                        </div>
                        <p style={{ color: '#aaaacc', fontSize: '0.82rem', lineHeight: 1.6, margin: 0 }}>{text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Suggestions */}
              {report.suggestions?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: '#8888aa', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '10px' }}>实用建议</h3>
                  {report.suggestions.map((s, i) => (
                    <div key={i} style={{ display: 'flex', gap: '10px', marginBottom: '8px', alignItems: 'flex-start' }}>
                      <span style={{ color: '#c9a84c', fontWeight: 700, minWidth: '20px' }}>{i + 1}.</span>
                      <span style={{ color: '#aaaacc', fontSize: '0.84rem', lineHeight: 1.6 }}>{s}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Sources */}
              <SourcesSection sources={report.sources} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Restart backend without `--reload`**

```bash
# Kill existing backend (run in Windows CMD, not bash):
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8001') do taskkill /F /PID %a

# Start fresh (no --reload to avoid WinError 87):
cd astrology_api
uvicorn main:app --host 127.0.0.1 --port 8001
```

- [ ] **Step 3: Start frontend**

```bash
cd frontend
npm run dev
```

- [ ] **Step 4: Manual smoke test**

1. 登录后进入 `太阳回归` tab
2. 从下拉选择一张已保存星盘
3. 在地点搜索框输入 `Shanghai`，选择结果
4. 点击 `计算 202X 年太阳回归盘`
   - 预期：双轮盘 SVG 显示（外圈 SR，内圈本命）
   - 预期：AI 报告 loading 自动触发
5. 报告生成后验证：
   - 显示关键词 tags
   - 显示主轴段落
   - 显示 Top 3 主题卡片（有分数条）
   - 显示八大领域
   - 显示 3 条建议
   - `<SourcesSection>` 显示 RAG 来源
6. 点击 `重新生成`，验证 `force_refresh=true` 触发新生成
7. 再次计算同一组合，验证第二次秒返回（缓存命中，标签显示"缓存"）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SolarReturn.jsx
git commit -m "feat(ui): implement SolarReturn page with bi-wheel SVG and AI annual report"
```

---

## Task 6: Update `test.md` and `TODO.md`

- [ ] **Step 1: Append test checklist to `test.md`**

Add at end of `test.md`:

```markdown
---

# 太阳回归功能（2026-03-27）

> 前置条件：已登录用户，至少有一张已保存本命盘

## 1. 基础计算流程

- [ ] 登录 → 太阳回归 tab → 下拉有保存的星盘 → 选择一张
- [ ] 地点搜索输入 "Shanghai" → 选择结果 → 显示经纬度
- [ ] 点击计算 → 双轮盘 SVG 显示（外圈SR + 内圈本命）
- [ ] AI 报告自动触发 → loading 状态出现 → 报告显示

## 2. 报告内容验证

- [ ] 关键词 tags 显示（3-5 个）
- [ ] 主轴段落显示（100-150字）
- [ ] Top 3 主题卡片（含分数条 + 分析 + 依据标签）
- [ ] 八大生活领域折叠区域显示
- [ ] 三条建议显示
- [ ] SourcesSection RAG 来源显示

## 3. 缓存与重新生成

- [ ] 重新点击计算同一星盘+地点 → 报告秒返回，标签显示"缓存"
- [ ] 点击"重新生成"→ AI 重新调用，标签显示模型名

## 4. 访客/未登录

- [ ] 未登录进入太阳回归 tab → 显示"请先登录"提示，无表单
```

- [ ] **Step 2: Update `TODO.md`**

Change:
```
- 🚧 太阳回归 Solar Return（`/solar-return`）- 3.27排期开发
```
to:
```
- 🔨 太阳回归 Solar Return（`/solar-return`）— 实现中
```

- [ ] **Step 3: Commit**

```bash
git add test.md TODO.md
git commit -m "docs: add solar return test checklist and update TODO"
```
