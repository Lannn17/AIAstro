# CLAUDE.md

本文件为 Claude Code 在此仓库中工作时提供指导。

---

## Hard rules / 硬性规则

- **绝对不能自行修改 `GENERATE_MODEL`**（当前值：`gemini-3.1-flash-lite-preview`）。用户已明确指定此模型，任何情况下不得擅自更改。
- **每次代码改动后立即 `git commit`，但不自动 push。** 只有当用户明确说"push"/"部署"/"推一下"时，才同时执行 `git push origin main`（GitHub）和 `git push hf main`（HuggingFace）。

---

## Current version / 当前版本

**v0.7.0** — JWT 登录 + 访客模式 + 行运分析 + 占星对话（RAG）+ 校正系统 + RAG 质量分析后台。
See `CHANGELOG.md` for full history.

---

## Commands / 命令

```bash
# ── Backend ──────────────────────────────────────────────────
cd astrology_api
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
# API docs: http://127.0.0.1:8001/docs

# ── Frontend ─────────────────────────────────────────────────
cd frontend
npm install
npm run dev     # http://localhost:5173  (proxies /api → 127.0.0.1:8001)
npm run lint
npm run build
```

**Required env vars** — copy `astrology_api/.env.example` to `astrology_api/.env`:

| Variable | Purpose | Required |
|---|---|---|
| `TURSO_DATABASE_URL` | Turso libSQL URL (`libsql://xxx.turso.io`) | Production only |
| `TURSO_AUTH_TOKEN` | Turso auth token | Production only |
| `GOOGLE_API_KEY` | Gemini API key (RAG + chat) | Always |
| `QDRANT_URL` | Qdrant vector DB URL | Always |
| `QDRANT_API_KEY` | Qdrant API key | Always |
| `SECRET_KEY` | JWT signing key | Always |

Local dev uses SQLite (`astrology_api/charts.db`) automatically when Turso vars are absent.

---

## Feature overview / 功能概览

| Feature | Status | Location |
|---|---|---|
| 本命盘计算 + SVG 星盘图 | ✅ | `星盘` tab |
| 行星表 + 宫位系统说明 | ✅ | `星盘` tab |
| 地点搜索（Nominatim） | ✅ | `星盘` tab → form |
| 星盘保存 / 加载 / 删除 | ✅ | `星盘` tab → sidebar |
| 多语言 UI (zh/ja/en/pt/es/fr/de) | ✅ | Form language selector |
| JWT 登录 + 访客模式 | ✅ | Login modal |
| 待审核队列（访客星盘） | ✅ | Admin sidebar |
| 行运分析 + AI 解读 | ✅ | `行运` tab |
| 占星对话（RAG + Gemini） | ✅ | `星盘` tab → 占星对话 |
| 行星解读缓存 | ✅ | `星盘` tab → 行星解读 |
| 出生时间校正 | ✅ | `星盘` tab → 校正 |
| RAG 质量分析后台 | ✅ | `/admin` 隐藏路由 |
| 合盘 Synastry | 🚧 Stub | `合盘` tab |
| 推运 Progressions | 🚧 Stub | `推运` tab |
| 太阳回归 Solar return | 🚧 Stub | `太阳回归` tab |
| 方向法 Directions | 🚧 Stub | `方向法` tab |
| HuggingFace Spaces 云部署 | ✅ | `lannn17-astro.hf.space` |

---

## Architecture / 架构

**前后端分离**：Python FastAPI 后端 + React/Vite 前端，开发时通过 Vite proxy 连接，生产环境由 HF Spaces 统一托管（前端静态文件由 FastAPI serve）。

```
frontend/
  src/
    pages/         NatalChart, Transits, Synastry, Progressions,
                   SolarReturn, Directions, Analytics
    components/    ChartForm, ChartWheel, PlanetTable, LoginModal,
                   GuestSaveConfirmModal
    contexts/      AuthContext (JWT + guest), ChartSessionContext (跨tab共享当前星盘)
    App.jsx        Router + sticky nav + AuthProvider + ChartSessionProvider

astrology_api/
  main.py          App entry, router registration, create_tables(), serve frontend static
  app/
    api/           natal_chart, transit, synastry, progression, return, direction,
                   interpret_router, rectification, charts_router, auth_router, admin_router
    core/          calculations.py (Kerykeion wrapper), utils.py
    db.py          自定义双模式 DB 层（SQLite 本地 / Turso HTTP 生产），无 ORM
    rag.py         RAG 核心：Qdrant 检索 + Gemini 生成，classify_query，chat_with_chart
    schemas/       Pydantic models (models.py)
    security.py    JWT auth (require_auth, get_optional_user)
    svg/           SVG chart generators
```

### Key architectural notes

- **DB 层**：`app/db.py` 是自定义的 SQLite/Turso HTTP 双模式层，不使用 SQLAlchemy。`USE_TURSO` 标志按环境变量自动切换。
- **RAG**：使用 Qdrant 向量库 + `intfloat/multilingual-e5-small` embedding + Gemini 生成。书籍文件名为 camelCase，`_clean_source_name` 做 camelCase 拆分后匹配引用。
- **Auth**：JWT Bearer token，`require_auth` 依赖强制鉴权，`get_optional_user` 允许匿名（访客星盘自动标记 `is_guest=1`）。
- **跨 tab 星盘共享**：`ChartSessionContext` 在内存中保存当前计算结果，访客切换到行运 tab 时可选"当前星盘（未保存）"。
- **Frontend port**：后端必须跑在 **8001**，`vite.config.js` proxy target 对应此端口。
- **生产构建**：`npm run build` 输出到 `frontend/dist/`，FastAPI 的 `StaticFiles` 从此目录 serve。

---

## Data model / 数据模型

### Tables

**`saved_charts`** — 主表

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `label` | TEXT | 显示名（`name · YYYY/M/D`）|
| `name` | TEXT | 出生姓名 |
| `birth_year/month/day/hour/minute` | INTEGER | |
| `location_name` | TEXT | Nominatim 地名 |
| `latitude` / `longitude` | REAL | |
| `tz_str` | TEXT | IANA timezone |
| `house_system` | TEXT | e.g. `"Placidus"` |
| `language` | TEXT | e.g. `"zh"` |
| `chart_data` | TEXT | JSON-serialised `NatalChartResponse` |
| `svg_data` | TEXT | Raw SVG |
| `is_guest` | INTEGER | 0 = 已审核，1 = 待审核访客 |
| `created_at` | TEXT | UTC ISO |

**其他缓存表**：`transit_analysis_cache`、`transit_overall_cache`、`planet_analysis_cache`、`query_analytics`

Schema 通过 `create_tables()` 启动时自动创建。无迁移工具——schema 不兼容变更时删除 `charts.db` 重启。

---

## API endpoints / API 端点

### 星盘计算

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/natal_chart` | 计算本命盘 |
| `POST` | `/api/svg_chart` | 生成 SVG 星盘图 |
| `POST` | `/api/transit_chart` | 计算行运盘 |
| `POST` | `/api/interpret/transits_full` | 行运完整 AI 分析（含缓存）|
| `POST` | `/api/synastry` | 合盘 |
| `POST` | `/api/progressions` | 推运 |
| `POST` | `/api/solar-return` | 太阳回归 |
| `POST` | `/api/interpret_planets` | 行星解读（Gemini，含缓存）|
| `POST` | `/api/interpret/chat` | 占星对话（RAG + Gemini）|
| `POST` | `/api/rectify` | 出生时间校正 |

### 星盘存储（需 JWT）

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/charts` | 列出已保存星盘 |
| `POST` | `/api/charts` | 保存星盘（访客自动标 is_guest）|
| `GET` | `/api/charts/{id}` | 读取单张星盘 |
| `DELETE` | `/api/charts/{id}` | 删除星盘 |
| `GET` | `/api/charts/pending` | 列出待审核（访客）星盘 |
| `POST` | `/api/charts/pending/{id}/approve` | 审核通过 |

### Auth

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/login` | 登录，返回 JWT |

### Admin（需 JWT）

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/admin/analytics` | RAG 统计数据（聚合 + 明细）|
| `POST` | `/api/admin/analytics/report` | Gemini 生成 RAG 质量分析报告 |

---

## Workflow / 工作流程

### Commit
每次代码改动后立即 commit，使用 Conventional Commits 格式，英文，72 字符以内：
```
feat(natal): add saved charts sidebar
fix(rag): split camelCase filenames in citation detection
chore(db): add query_analytics table
```

### Push
用户说"push"/"部署"/"推一下"时，同时推两端：
```bash
git push origin main   # GitHub
git push hf main       # HuggingFace（触发重新部署）
```

### 版本发布（仅当用户明确要求时）
1. Bump version in `frontend/package.json`
2. Update "Current version" line in this file
3. Add `CHANGELOG.md` entry
4. `git add -A && git commit -m "chore(release): vX.Y.Z"`
5. `git tag vX.Y.Z`
6. Push 两端（同上）

### /clear guard
`/clear` 前检查 `git status`，有未提交改动则询问是否先 commit。

### Do not commit
- `astrology_api/charts.db`
- `astrology_api/.env`
- `frontend/dist/`
- `**/__pycache__/`
