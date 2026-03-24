# Changelog

All notable changes to this project are documented here.
本项目所有重要变更均记录于此。

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.5.0] - 2026-03-24

### Added
- **移动端响应式布局**：全站适配手机屏幕（`@media max-width: 768px`）
  - 导航栏在手机端变为全宽横向滚动行，隐藏滚动条
  - 星盘页：侧栏、表单、结果区竖向堆叠；主内容区 padding 从 48px 缩至 16px
  - 行运页：控制面板叠加在结果区上方
  - 宫位说明弹窗 padding 在手机端缩小（28px → 16px）
  - 占星对话面板 min-height 在手机端缩至 400px

---

## [0.4.0] - 2026-03-23

### Added
- **出生时间校正（Rectification）**：新增两阶段扫描算法，结合生命事件权重对候选时间打分，AI 为每个候选时间生成结构化 JSON 原因卡片（`feat(rectify)`）
- **行运 DB 缓存**：每条行运相位结果单独缓存入数据库，避免重复调用 AI；新增 `force_refresh` 参数强制绕过缓存
- **行运 tone/theme 标签**：每条行运解读附带 tone（能量基调）与 theme（主题）字段
- **行星数据修复**：过滤 `true_node`/`true_lilith` 重复条目，新增 Mean Lilith 的七语言翻译
- **调试工具**：`rag.py` 中 `analyze_rectification` 新增调试日志；新增 `test_rectify.py` 手动测试脚本

### Changed
- 行运相位分析改用分级容许度（主要相位优先）与优先度评分
- 行运提示词改为主题聚类式结构，去除 `exact_date` 字段

---

## [0.3.0] - 2026-03-23

### Added
- **行运 AI 解读**：行运页新增「✦ AI 行运解读」区块，点击「生成解读」后调用 RAG + Gemini 对当日行运相位进行四维分析（整体能量、重点相位、机遇与挑战、建议事项），并展示引用书名
- `rag.py` 新增 `analyze_transits()` 函数，专门处理行运场景的摘要格式化与 Gemini 生成
- `interpret_router.py` 新增 `POST /api/interpret/transit` 端点

### Changed
- 导航栏移除「解释」tab（RAG 问答已整合入行运解读）
- `format_chart_summary()` 新增 `max_aspects` 参数，行运场景下截断至 10 条相位以控制 prompt 大小

### Fixed
- **云端部署**：修复 Render 部署时根路由 `/` 返回 JSON 而非前端页面的问题（`dist/` 存在时优先 serve `index.html`）

---

## [0.2.0] - 2026-03-19

### Added

**RAG 解读引擎 / RAG Interpretation Engine**
- `app/rag.py` — 核心 RAG 模块：Gemini 嵌入向量检索（`gemini-embedding-001`）→ FAISS 检索 top-k 书籍片段 → Gemini 生成中文解读（`gemini-3.1-flash-lite-preview`）
- 三种索引构建策略，按优先级自动选择：
  - `build_local_index.py` — 纯本地方案，TF-IDF + SVD (LSA) 生成 384 维密集向量，无需任何 API，依赖 scikit-learn + faiss-cpu
  - `build_demo_index.py` — 3 本精选书籍 demo 索引，使用 Gemini `gemini-embedding-2-preview`，支持断点续跑
  - `build_index.py` — 全语料完整索引，Gemini 嵌入，支持断点续跑（速率限制下自动等待）
- `app/api/interpret_router.py` 新增两个端点：
  - `POST /api/interpret/rag` — 纯 RAG 模式：书籍片段主导解读
  - `POST /api/interpret/chat` — 星盘对话（`mode="interpret"` AI 主导 + RAG 补充；`mode="rag"` 片段主导）
- 星盘摘要格式化 `format_chart_summary()` — 把 `NatalChartResponse` 转为 LLM 可读文本，注入 prompt 上下文
- `data/demo_index/`、`data/faiss_index/`、`data/local_index/` 索引目录（`.gitignore` 中排除）

**部署修复 / Deployment Fix**
- `render.yaml` 改为单服务架构：build 时构建前端，FastAPI 在生产环境 serve `dist/` 静态文件 + SPA catch-all
- `main.py` 新增 `StaticFiles` 挂载（`/assets`）和 SPA 回退路由（`dist/` 存在时自动启用）
- `requirements.txt` 新增 `aiofiles`（FastAPI StaticFiles 必需）

### Changed

- 解读路由支持 `GOOGLE_API_KEY` 环境变量，在 Turso 环境变量之外另需配置

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
