# CLAUDE.md

本文件为 Claude Code 在此仓库中工作时提供指导。

---

## Hard rules / 硬性规则

- **绝对不能自行修改 `GENERATE_MODEL`**（当前值：`gemini-3.1-flash-lite-preview`）。用户已明确指定此模型，任何情况下不得擅自更改。
- **每次代码改动后立即 commit**，不主动 push。Push 两端（`git push origin main && git push hf main`）、版本号更新、CHANGELOG 更新，三者同步，只在用户明确要求时一起完成。
- **每次代码改动后自动检查 `TODO.md`**：对照本次改动判断 TODO 中哪些条目需要新增、修改状态或删除，列出建议变更内容并等待用户确认后再修改 TODO.md。
- **架构变更时同步更新 `ARCHITECTURE.md`**：新增模块、端点、数据库表、外部服务、缓存策略、模块标准等任何架构层面的改动，必须在同一个 commit 中更新 `ARCHITECTURE.md` 对应章节。

---

## AI 分析设计方针 / AI Analysis Design Principle

**所有涉及 AI 分析的功能，必须同时满足以下三点：**

1. **RAG 知识增强**：调用 Qdrant 检索相关书籍片段，拼入 prompt 作为参考依据，不允许裸调 Gemini。
2. **后端 Analytics 记录**：每次 AI 分析调用后，通过 `_log_analytics` 写入 `query_analytics` 表，记录 query hash、分类标签、最高相似度分、是否被引用，用于持续效果验证。
3. **前端显示引用文献区块**：使用 `<SourcesSection>` 组件展示 RAG 检索到的来源。
   - **当前**：所有用户可见（临时状态）。
   - **目标**：仅管理员可见。此权限控制待注册用户功能开发完成后实现（另一 terminal 正在开发）。

违反以上任意一点的 AI 分析端点均视为未完成实现。

---

## Current version / 当前版本

**v0.7.1** — JWT 登录 + 访客模式 + 行运分析 + 占星对话（RAG）+ 校正系统 + RAG 质量分析后台 + 合盘（Synastry）功能 + Gemini 模型自动 fallback + 模型标签显示。
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

### 功能测试（每个功能完成后必须执行）
每次完成一个功能或 bug fix 后，**在 commit+push 之前**，向用户列出测试清单并带领其完成：

1. 列出该功能涉及的所有测试路径（登录态 / 访客态 / 边界情况）
2. 逐条引导用户操作，明确告知：路径、预期结果、需要观察的具体现象
3. 等待用户反馈每条测试结果
4. 用户确认全部通过后再 commit + push
5. 若发现问题，先修复再重新测试，不跳过

**测试清单格式示例：**
```
请依次测试以下操作：
1. [路径] 登录 → 星盘 Tab → 生成星盘 → 切换行运 Tab
   预期：行运下拉框出现"XXX（未保存）"选项
2. [路径] 未登录 → 访问 /admin
   预期：显示"请先登录"，页面不崩溃
```

### Commit
每次代码改动后立即 commit，不 push：
```bash
git add <files>
git commit -m "type(scope): description"
```
Conventional Commits 格式，英文，72 字符以内。

Commit 后提示用户重启前端（`npm run dev`）或后端（`uvicorn ...`）视改动类型而定，在本地测试。

### Push + 版本发布（仅当用户明确要求时，三步同步完成）
1. Bump version in `frontend/package.json`
2. Update "Current version" line in this file
3. Add `CHANGELOG.md` entry
4. `git add -A && git commit -m "chore(release): vX.Y.Z"`
5. `git tag vX.Y.Z`
6. `git push origin main && git push hf main`

### /clear guard
`/clear` 前检查 `git status`，有未提交改动则询问是否先 commit。

### Do not commit
- `astrology_api/charts.db`
- `astrology_api/.env`
- `frontend/dist/`
- `**/__pycache__/`
