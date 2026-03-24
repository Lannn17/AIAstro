# CLAUDE.md

本文件为 Claude Code 在此仓库中工作时提供指导。
This file provides guidance to Claude Code when working with this repository.

---

## Hard rules / 硬性规则

- **绝对不能自行修改 `GENERATE_MODEL`**（当前值：`gemini-3.1-flash-lite-preview`）。用户已明确指定此模型，任何情况下不得擅自更改。

---

## Current version / 当前版本

**v0.5.0** — 校正 Phase 2/3（ASC 性格问卷 + 生命主题置信度）、太阳弧评分；部署迁移至 HuggingFace Spaces；向量检索迁移至 Qdrant Cloud；移动端全站响应式布局。
See `CHANGELOG.md` for full history and diff from upstream fork.

---

## Commands / 命令

```bash
# ── Backend / 后端 ──────────────────────────────────────────
cd astrology_api

# Install / 安装依赖
pip install -r requirements.txt

# Development (with hot reload) / 开发模式（热重载）
uvicorn main:app --host 127.0.0.1 --port 8001 --reload

# API docs (auto-generated) / 自动文档
# http://127.0.0.1:8001/docs

# ── Frontend / 前端 ─────────────────────────────────────────
cd frontend

# Install / 安装依赖
npm install

# Development / 开发模式
npm run dev          # http://localhost:5173  (proxies /api → 127.0.0.1:8001)

# Lint / 代码检查
npm run lint

# Production build / 生产构建
npm run build
```

**Required env vars / 必需环境变量** — copy `astrology_api/.env.example` to `astrology_api/.env`:

| Variable | Purpose | Required |
|---|---|---|
| `TURSO_DATABASE_URL` | Turso libSQL URL (`libsql://xxx.turso.io`) | Production only |
| `TURSO_AUTH_TOKEN` | Turso auth token | Production only |

Local dev uses a SQLite file (`astrology_api/charts.db`) automatically when Turso vars are absent.

---

## Feature overview / 功能概览

| Feature / 功能 | Status / 状态 | Location / 位置 |
|---|---|---|
| 本命盘计算 Natal chart calculation | ✅ Complete | `星盘` tab |
| SVG 星盘图 SVG chart wheel | ✅ Complete | `星盘` tab → right panel |
| 行星表 Planet table | ✅ Complete | `星盘` tab → right panel |
| 地点搜索（Nominatim）Location search | ✅ Complete | `星盘` tab → form |
| 宫位系统说明弹窗 House system info modal | ✅ Complete | `星盘` tab → form |
| 星盘保存/加载/删除 Chart save/load/delete | ✅ Complete | `星盘` tab → sidebar |
| 多语言 UI Multi-language UI (zh/ja/en/pt/es/fr/de) | ✅ Complete | Form language selector |
| 行运 Transits | 🚧 Stub | `行运` tab |
| 合盘 Synastry | 🚧 Stub | `合盘` tab |
| 推运 Progressions | 🚧 Stub | `推运` tab |
| 太阳回归 Solar return | 🚧 Stub | `太阳回归` tab |
| 方向法 Directions | 🚧 Stub | `方向法` tab |
| 解释 Interpretations | 🚧 Stub | `解释` tab |
| Render + Turso 云部署 Cloud deployment | 🔜 Planned | — |

---

## Architecture / 架构

This is a **decoupled full-stack app** — a Python FastAPI backend and a React/Vite frontend running separately, connected via Vite's dev proxy.

这是一个**前后端分离架构** — Python FastAPI 后端与 React/Vite 前端独立运行，通过 Vite 开发代理连接。

```
frontend/          React + Vite + Tailwind CSS
  src/
    pages/         One component per nav tab (NatalChart, Transits, …)
    components/    ChartForm, ChartWheel, PlanetTable
    App.jsx        Router + sticky nav (7 tabs)
    index.css      Global styles, Chinese font stack (Ma Shan Zheng → fallbacks)

astrology_api/     FastAPI + SQLAlchemy + Kerykeion
  main.py          App entry point, router registration, create_tables() on startup
  app/
    api/           One router per feature (natal_chart, transit, synastry, …)
    core/          calculations.py — wraps Kerykeion; utils.py — validation
    db.py          SQLAlchemy engine (SQLite local / Turso production)
    schemas/       Pydantic request/response models (models.py)
    interpretations/
      translations.py   Planet/sign/aspect/house translations (zh, ja, en, pt, es, fr, de)
      text_search.py    TF-IDF text search (future RAG foundation)
    svg/           SVG chart generators
    security.py    Auth stub (disabled for local dev)
```

### Key architectural notes / 关键架构说明

- **Vite proxy:** `frontend/vite.config.js` proxies `/api` → `http://127.0.0.1:8001`. In production, Nginx or Render's routing will replace this.
- **Database auto-switch:** `app/db.py` reads `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`. If absent → local `charts.db` (SQLite). Changing to PostgreSQL later requires only updating the env var and adding `psycopg2-binary` to requirements.
- **Kerykeion** is the astrological calculation engine. It wraps Swiss Ephemeris and returns planet positions, house cusps, and aspects.
- **Language system:** All astrological term translations live in `translations.py`. Frontend UI labels are hardcoded per-component dicts (see `PlanetTable.jsx → UI_LABELS`, `ChartWheel.jsx → CHART_TITLE`). Both are keyed by the same language codes (`zh`, `ja`, `en`, …).
- **Single-user:** No auth, no user table. All saved charts belong to one implicit user.
- **API auth is disabled** in `app/security.py` (`verify_api_key` returns `None`). Re-enable before any public deployment.
- **Frontend port note:** The backend must run on port **8001** (not 8000) locally — port 8000 may be occupied by another process. If changing, update `vite.config.js` proxy target accordingly.

---

## Data model / 数据模型

### `saved_charts` table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `label` | TEXT | Display name (auto-generated: `name · YYYY/M/D`) |
| `name` | TEXT | Person's birth name |
| `birth_year/month/day/hour/minute` | INTEGER | Birth datetime components |
| `location_name` | TEXT | Nominatim display name |
| `latitude` / `longitude` | FLOAT | Decimal degrees |
| `tz_str` | TEXT | IANA timezone string |
| `house_system` | TEXT | e.g. `"Placidus"` |
| `language` | TEXT | e.g. `"zh"` |
| `chart_data` | TEXT | JSON-serialised `NatalChartResponse` |
| `svg_data` | TEXT | Raw SVG string |
| `created_at` | DATETIME | UTC |

Schema is created via `Base.metadata.create_all()` on startup. No migration tooling — if the schema changes incompatibly, delete `charts.db` and restart.

---

## API endpoints / API 端点

### Astrological calculations / 星盘计算

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/natal_chart` | Calculate natal chart → `NatalChartResponse` |
| `POST` | `/api/v1/svg_chart` | Generate SVG chart image (returns raw SVG text) |
| `POST` | `/api/v1/svg_chart_base64` | Same, base64-encoded |
| `POST` | `/api/v1/transit_chart` | Calculate transit chart |
| `POST` | `/api/v1/transits_to_natal` | Transit planets overlaid on natal chart |
| `POST` | `/api/v1/synastry` | Synastry (two-chart comparison) |
| `POST` | `/api/v1/progressions` | Secondary progressions |
| `POST` | `/api/v1/solar-return` | Solar return chart |
| `POST` | `/api/v1/lunar-return` | Lunar return chart |
| `POST` | `/api/v1/solar-arc` | Solar arc directions |
| `GET` | `/api/v1/interpret` | Interpretation text search |

### Saved charts / 已保存星盘

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/charts` | List all saved charts (summary only) |
| `POST` | `/api/v1/charts` | Save a new chart (full data + cache) |
| `GET` | `/api/v1/charts/{id}` | Load one chart (full detail) |
| `DELETE` | `/api/v1/charts/{id}` | Delete a chart |

### Request bodies / 请求体

Key request model (`NatalChartRequest`):

```python
name: str | None
year, month, day, hour, minute: int
latitude, longitude: float
tz_str: str               # IANA, e.g. "Asia/Shanghai"
house_system: str         # "Placidus" | "Koch" | "Whole Sign" | "Equal" | "Regiomontanus" | "Campanus"
language: str             # "zh" | "ja" | "en" | "pt" | "es" | "fr" | "de"
include_interpretations: bool = False
```

---

## Development plan / 开发计划

Near-term priorities / 近期重点:

1. **Render + Turso deployment** — configure `render.yaml`, set env vars, deploy both services
2. **行运 Transits page** — transit planets overlaid on natal chart using saved charts as base
3. **合盘 Synastry page** — load two saved charts and compare
4. **Mobile access** — expose dev server with `--host` for LAN testing, or Cloudflare Tunnel
5. **Interpretation engine** — display aspect/planet interpretations from `text_search.py`
6. **RAG for interpretations** — `langchain` + `faiss-cpu` + `sentence-transformers` already in `requirements.txt`

---

## Contributing / 贡献指南

### Branch naming / 分支命名

| Prefix | When to use |
|---|---|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `chore/` | Deps, config, tooling |
| `docs/` | Documentation only |
| `refactor/` | No behaviour change |

### Commit messages / 提交信息

English only. Follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description` under 72 chars, imperative mood.

```
feat(natal): add saved charts sidebar with load/delete
fix(lang): add zh and ja to LanguageType validation
chore(db): switch local SQLite to Turso-compatible dual-mode setup
```

### Do not commit / 不要提交

- `astrology_api/charts.db`
- `astrology_api/.env`
- `frontend/dist/`
- `**/__pycache__/`

Add these to `.gitignore` before the first commit.

---

## Releases & Versioning / 发布与版本管理

Follows [Semantic Versioning](https://semver.org/).

| Bump | When |
|---|---|
| `PATCH` (0.0.x) | Bug fixes, minor tweaks |
| `MINOR` (0.x.0) | New feature (backwards-compatible) |
| `MAJOR` (x.0.0) | Breaking DB schema change, API contract change |

Pre-1.0: breaking changes may appear in `MINOR` bumps.

### Release process / 发布流程

```bash
# 1. Ensure working tree is clean on main
git checkout main && git pull

# 2. Bump version in frontend/package.json (manual or npm version)
npm version minor   # inside frontend/

# 3. Update CLAUDE.md "Current version" line
# 4. Add CHANGELOG.md entry summarising changes since last version
# 5. Commit + tag + push
git add -A && git commit -m "chore(release): v0.x.0"
git tag v0.x.0
git push origin main --follow-tags
```

---

## Workflow / 工作流程

### Auto-commit rule / 自动提交规则

After every code change, **immediately `git commit`** with a Conventional Commits message. Do not batch. Do not bump version per commit.

### Push on demand / 按需推送

When explicitly asked to push:
1. Bump version in `frontend/package.json` following the scheme above.
2. Add a `CHANGELOG.md` entry summarising all commits since the last version.
3. Update the `Current version` line in this file.
4. Commit the version bump + changelog, then `git push`.
5. No confirmation needed — just do it.

### /clear guard / /clear 守卫

Before `/clear`, check `git status`. If uncommitted changes exist, ask whether to commit first. If clean, proceed silently.
