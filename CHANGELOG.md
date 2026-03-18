# Changelog

All notable changes to this project are documented here.
本项目所有重要变更均记录于此。

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.1.0] - 2026-03-18

### Forked from / 派生自

This project is forked from **[Bessaq/asoaosq](https://github.com/Bessaq/asoaosq)** — a Python FastAPI astrological calculation API built on [Kerykeion](https://github.com/g-battaglia/kerykeion).

本项目 fork 自 **[Bessaq/asoaosq](https://github.com/Bessaq/asoaosq)**，原项目为基于 [Kerykeion](https://github.com/g-battaglia/kerykeion) 的 Python FastAPI 星盘计算 API。

### What the original project provided / 原始项目提供的功能

- FastAPI backend with full astrological calculation endpoints (natal chart, transits, synastry, progressions, solar/lunar return, solar arc directions)
- SVG chart generation via Kerykeion
- Pydantic request/response models
- TF-IDF text search engine for astrological interpretations (from processed book corpus)
- Multi-language support: `pt`, `en`, `es`, `fr`, `it`, `de`
- Two-level cache system (memory + disk)
- API key authentication scaffold (`security.py`)
- Portuguese (`pt`) as default language throughout

### Added in this version / 本版本新增

**Frontend / 前端**
- React + Vite + Tailwind CSS frontend (entirely new — original had no frontend)
- 7-tab navigation: 星盘 / 行运 / 合盘 / 推运 / 太阳回归 / 方向法 / 解释
- Natal chart page with form, SVG wheel, and planet table
- Location search via OpenStreetMap Nominatim (replaces manual lat/lng input)
- House system info modal explaining all 6 systems with per-audience recommendations
- Saved charts sidebar (load / delete)
- Chinese font stack: Ma Shan Zheng (颜体风格) → STSong → SimSun → Noto Serif CJK SC → serif
- Nav tabs fill header width with even spacing

**Backend / 后端**
- `app/db.py` — SQLAlchemy ORM with dual-mode database: local SQLite (`charts.db`) when Turso env vars absent; Turso (libSQL) in production
- `app/api/charts_router.py` — CRUD endpoints for saved charts (`GET/POST /api/v1/charts`, `GET/DELETE /api/v1/charts/{id}`)
- `main.py` — auto-creates DB tables on startup via `create_tables()`

**Language / 语言**
- Added `zh` (中文) and `ja` (日本語) to `LanguageType` across all Pydantic models and `translations.py`
- Full zh/ja translations for planets, signs, aspects, and houses in `translations.py`
- Fixed Portuguese hardcoded fallback in `translate_house()` → neutral English fallback
- Frontend UI labels (`PlanetTable`, `ChartWheel`) now language-aware via per-component label dicts

**Infrastructure / 基础设施**
- Git repository initialised with `.gitignore`
- `CLAUDE.md` with full architecture docs, API reference, dev workflow, and versioning rules
- Backend port changed from 8000 → 8001 (avoids local port conflicts); Vite proxy updated accordingly

### Changed from original / 相对原始项目的变更

| Item | Original | This fork |
|---|---|---|
| Default language | `pt` (Portuguese) | `zh` (Chinese) |
| Language support | pt, en, es, fr, it, de | + zh, ja |
| Frontend | None | React/Vite SPA |
| Database | None (stateless API) | SQLite / Turso via SQLAlchemy |
| API auth | Enabled (X-API-KEY header) | Disabled for local dev (`security.py` returns None) |
| House system fallback | Portuguese `"Casa X"` | Neutral `"House X"` |
| Backend port (local) | 8000 | 8001 |
| Location input | Manual lat/lng fields | Nominatim autocomplete |

### Removed / 移除

- Manual latitude/longitude input fields in the form (replaced by location search)

---

## [Upstream] — Bessaq/asoaosq baseline

The upstream baseline included all core astrological calculation logic, Kerykeion integration, SVG generation, the TF-IDF interpretation engine, multi-language translation infrastructure, and the Pydantic schema definitions. See [github.com/Bessaq/asoaosq](https://github.com/Bessaq/asoaosq) for the original history.

上游基线包含所有核心星盘计算逻辑、Kerykeion 集成、SVG 生成、TF-IDF 解释引擎、多语言翻译基础设施及 Pydantic schema 定义。原始历史见 [github.com/Bessaq/asoaosq](https://github.com/Bessaq/asoaosq)。
