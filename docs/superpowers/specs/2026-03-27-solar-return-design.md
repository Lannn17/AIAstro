# Solar Return Feature Design Spec
**Date:** 2026-03-27
**Version:** MVP v1.0

---

## Overview

实现太阳回归（Solar Return）功能，让用户选择一张已保存的本命盘，输入当前所在地，计算当年太阳回归盘，展示 SR+本命叠加双轮盘 SVG，并由规则引擎打分后调用 RAG+Gemini 生成年度主题报告。

---

## Decisions Summary

| 决策点 | 结论 |
|---|---|
| 回归地点 | 用户输入当前所在地（Nominatim 地名搜索） |
| SR 年份 | 默认当年，固定不可改（MVP） |
| 星盘图 | SR 外圈 + 本命内圈叠加双轮盘（复用现有 SVG 生成器） |
| 本命盘来源 | 从用户已保存星盘下拉选择（chart_id 必须 > 0） |
| 规则引擎 | Python 硬编码，与 `_compute_chart_facts()` 同风格 |
| AI 缓存 | 按 `chart_id + return_year + location_hash` 缓存，保留强制重新生成按钮 |
| RAG + Analytics | 必须，遵守项目 AI 分析设计方针 |

---

## Architecture

```
前端 SolarReturn.jsx
  ├── ① 输入区：下拉选已保存星盘 + Nominatim 地点搜索 + 计算按钮
  ├── ② SVG 双轮盘区：SR 外圈 + 本命内圈 + 行星图例两列
  └── ③ AI 年度报告区：关键词 / 主轴 / 主题分析 / 八领域 / 建议 / SourcesSection

后端
  ├── POST /api/solar-return           ← 已有，计算 SR 星盘数据（return_router.py）
  ├── POST /api/svg_chart              ← 已有，transit 模式传入 natal+sr 生成双轮盘
  └── POST /api/interpret/solar-return ← 新增端点（interpret_router.py）
        ├── _compute_sr_theme_scores()   ← 新规则引擎函数（rag.py）
        ├── rag_generate(k=5) + _log_analytics()
        └── solar_return_cache 表（新增，db.py）
```

---

## Backend: Rule Engine

### 函数签名

```python
def _compute_sr_theme_scores(
    sr_planets: dict,       # SR 星盘行星数据（含宫位）
    sr_houses: dict,        # SR 宫位数据
    natal_planets: dict,    # 本命行星数据（供相位对比）
    natal_houses: dict,     # 本命宫位数据（供 SR ASC 落本命宫计算）
    sr_asc_degree: float,   # SR 上升黄道度数（0-360）
) -> dict

# 调用方从 natal_chart_data 中提取：
#   natal_planets = natal_chart_data.get("planets", {})
#   natal_houses  = natal_chart_data.get("houses", {})
```

### 输出结构

```python
{
    "core_facts": [
        "SR上升落本命第4宫",
        "SR太阳落第4宫",
        "SR月亮落第9宫",
        "上升守护星土星落SR第2宫",
        "木星落SR第7宫",
        "太阳合天王星（orb 2.3°）"
    ],
    "theme_scores": {
        "self_identity": 24,
        "relationships": 61,
        "career_public": 36,
        "home_family": 79,
        "money_resources": 48,
        "health_routine": 31,
        "learning_expansion": 44,
        "inner_healing": 53
    },
    "top_themes": [
        {"theme": "home_family", "score": 79},
        {"theme": "relationships", "score": 61},
        {"theme": "inner_healing", "score": 53}
    ],
    "modifiers": ["change", "restructuring"],
    "confidence": 0.71
}
```

### 打分规则（6 层，从高到低）

**Layer 1 — SR 上升落本命宫（Volguine 第一要素，权重 6）**

计算方法：用 `sr_asc_degree` 与 `natal_houses` 中每个宫位的起始/结束黄道度数比较，确定 SR ASC 落入本命哪个宫，然后查表打分。

```python
SR_ASC_NATAL_HOUSE_WEIGHTS = {
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
```

**Layer 2 — SR 太阳落宫（年度核心主轴，权重 5）**
```python
SUN_HOUSE_WEIGHTS = {
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
```

**Layer 3 — SR 月亮落宫（情绪体验，权重 3-4）**
```python
MOON_HOUSE_WEIGHTS = {
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
```

**Layer 4 — SR 上升守护星落 SR 宫（传统守护，权重 2）**

传统守护星查表（MVP 不用现代守护）：
```python
_TRADITIONAL_RULER = {
    "Aries": "mars",    "Taurus": "venus",   "Gemini": "mercury",
    "Cancer": "moon",   "Leo": "sun",         "Virgo": "mercury",
    "Libra": "venus",   "Scorpio": "mars",    "Sagittarius": "jupiter",
    "Capricorn": "saturn", "Aquarius": "saturn", "Pisces": "jupiter",
}
```

计算步骤：
1. 从 `sr_houses["1"]["sign_original"]` 取 SR 上升星座
2. 用 `_TRADITIONAL_RULER` 查到守护星 key
3. 从 `sr_planets[ruler_key]["house"]` 取守护星落 SR 宫号（str）
4. 用 **`SUN_HOUSE_WEIGHTS`** 查该宫位对应主题，各 +2
5. 若该宫号在 `{1, 4, 7, 10}`，额外 +1 给同一主题

**Layer 5 — 角宫行星强调（各角宫独立计算）**

对四个角宫分别统计行星数，**每个角宫独立**打分：
- 该角宫有 2 颗行星 → 对应主题 +2
- 该角宫有 3 颗及以上行星 → 对应主题 +3

```python
ANGULAR_HOUSE_THEMES = {
    "1": "self_identity",
    "4": "home_family",
    "7": "relationships",
    "10": "career_public",
}
```

例：1 宫 2 颗行星 → `self_identity +2`；10 宫 3 颗行星 → `career_public +3`，互不干扰。

**Layer 6 — 功能性行星落 SR 宫（木土金火，权重 1-3）**
```python
PLANET_HOUSE_WEIGHTS = {
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
```

**Modifier 相位（orb ≤ 3°，仅加标签不加分）**

| 相位 | modifier 标签 |
|---|---|
| 太阳合/刑/冲 土星 | `"restructuring"` |
| 太阳合/刑/冲 木星 | `"expansion"` |
| 太阳合 天王星 | `"change"` |
| 太阳合 海王星 | `"dissolution"` |
| 太阳合 冥王星 | `"transformation"` |
| 月亮合 土星 | `"emotional_weight"` |

---

## Backend: New Endpoint

```
POST /api/interpret/solar-return
```

**注意：仅接受已保存星盘（`chart_id > 0`）。访客模式（`chart_id = 0`）不支持本功能。**

**Request:**
```json
{
    "chart_id": 42,
    "natal_chart_data": { "planets": {...}, "houses": {...}, "aspects": [...], ... },
    "sr_planets": { ... },
    "sr_houses": { ... },
    "sr_asc_degree": 134.5,
    "return_year": 2026,
    "location_lat": 31.2304,
    "location_lon": 121.4737,
    "language": "zh",
    "force_refresh": false
}
```

**注：`location_hash` 由后端计算，不由前端传入：**
```python
location_hash = hashlib.md5(f"{location_lat:.4f},{location_lon:.4f}".encode()).hexdigest()[:12]
```

**Response:**
```json
{
    "keywords": ["家庭重构", "关系深化", "内在转化"],
    "summary": "...",
    "themes": [
        {"theme": "home_family", "score": 79, "analysis": "...", "evidence": ["SR太阳落第4宫"]}
    ],
    "domains": {
        "career_public": "...",
        "relationships": "...",
        "money_resources": "...",
        "home_family": "...",
        "health_routine": "...",
        "learning_expansion": "...",
        "inner_healing": "...",
        "self_identity": "..."
    },
    "suggestions": ["...", "...", "..."],
    "sources": [...],
    "model_used": "gemini-3.1-flash-lite-preview",
    "theme_scores": { ... }
}
```

**注：`domains` 使用与 `theme_scores` 相同的 8 个 key，保持一致。缓存命中时 `model_used` 返回 `"cached"`。**

**执行流程：**
1. `chart_id == 0` → 直接返回 `403 / 400`（访客不支持）
2. 计算 `location_hash = md5(f"{lat:.4f},{lon:.4f}")[:12]`
3. 调用 `db_get_sr_cache(chart_id, return_year, location_hash)`
4. 命中且非 `force_refresh` → 返回缓存，`model_used = "cached"`
5. 未命中 → `_compute_sr_theme_scores(sr_planets, sr_houses, natal_planets, natal_houses, sr_asc_degree)` → `analysis_json`
6. `rag_generate(query=f"solar return {return_year} annual themes {top3_themes}", prompt=..., k=5)` → `(answer, sources)`
7. 组装 response dict
8. `db_save_sr_cache(chart_id, return_year, location_hash, json.dumps(response))` （INSERT OR REPLACE）
9. `asyncio.create_task(_log_analytics(query, response))`
10. 返回 response

---

## Database: New Cache Table

在 `db.py` 中新增常量 `_CREATE_SR_CACHE`，并追加到 `create_tables()` 的 DDL 循环中：

```python
_CREATE_SR_CACHE = """
CREATE TABLE IF NOT EXISTS solar_return_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id      INTEGER NOT NULL,
    return_year   INTEGER NOT NULL,
    location_hash TEXT    NOT NULL,
    result_json   TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sr_cache
    ON solar_return_cache(chart_id, return_year, location_hash);
"""
```

`create_tables()` 中追加：
```python
for ddl in [..., _CREATE_SR_CACHE]:
    ...
```

新增 DB 辅助函数（`db.py`）：
```python
def db_get_sr_cache(chart_id: int, return_year: int, location_hash: str) -> dict | None:
    """返回缓存的 result_json（已 json.loads），未命中返回 None。"""

def db_save_sr_cache(chart_id: int, return_year: int, location_hash: str, result_json: str) -> None:
    """INSERT OR REPLACE 写入缓存。"""
```

---

## SVG Bi-Wheel API Call

现有 `POST /api/svg_chart` 支持双轮盘，需以 **transit 模式**传入：

```json
{
    "natal_chart": { <本命盘出生数据> },
    "chart_type": "transit",
    "transit_chart": { <SR盘出生时刻数据，结构同 NatalChartRequest> },
    "language": "zh"
}
```

后端 `generators.py` 中 `generate_chart_svg()` 会将 `transit_subject`（即 SR subject）作为 `second_obj` 传给 `KerykeionChartSVG`，生成 SR 外圈 + 本命内圈的双轮盘。

---

## Frontend: SolarReturn.jsx

### 区域 ① 输入区
- 下拉选已保存星盘（调用 `GET /api/charts`，仅显示已保存星盘，访客提示"请先登录并保存星盘"）
- Nominatim 地点搜索组件（复用本命盘页的 `LocationSearch` 逻辑，取回 `lat/lon`）
- `计算` 按钮（disabled 直到星盘和地点均已选）

### 区域 ② SVG 双轮盘
- 调用 `POST /api/svg_chart`（transit 模式），本命盘数据 + SR出生时刻数据
- 图例两列：左列本命行星位置，右列 SR 行星位置

### 区域 ③ AI 年度报告
- Loading skeleton 在 AI 生成期间显示
- 年度关键词 Tags 行
- 核心主轴段落
- Top 3 主题卡片（主题名 + 分数条 + 分析文字 + 依据标注）
- 八个生活领域简述（可折叠）
- 三条实际建议列表
- `[强制重新生成]` 按钮（触发 `force_refresh=true`）
- `<SourcesSection sources={...} />` RAG 来源展示

---

## AI Checklist（项目强制要求）

**后端**
- [ ] `rag_generate(query, prompt, k=5)` 调用存在，query 包含 SR 年份 + top3 主题关键词
- [ ] RAG 片段通过 `rag_generate()` 注入 prompt
- [ ] 返回值包含 `sources` 字段
- [ ] router 中有 `asyncio.create_task(_log_analytics(query, result))` 调用

**前端**
- [ ] 报告区域已渲染 `<SourcesSection sources={...} />`
- [ ] `sources` 数据从 API 响应正确传递到组件 props

---

## Out of Scope (MVP)

- SR 年份可选（固定当年）
- SR Midheaven 落本命宫打分（Volguine 第二要素，留 v2）
- SR → 本命宫位全量叠加打分（留 v2）
- 月回归（lunar return）
- 报告多语言（MVP 仅中文）
- 访客模式 SR 分析
