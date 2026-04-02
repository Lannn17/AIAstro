# CLAUDE.md

本文件为 Claude Code 在此仓库中工作时提供指导。

---

## Hard rules / 硬性规则

- **绝对不能自行修改 `GENERATE_MODEL`**（当前值：`gemini-3.1-flash-lite-preview`）。用户已明确指定此模型，任何情况下不得擅自更改。
- **每次代码改动后立即 commit**，不主动 push。Push 两端（`git push origin main && git push hf main`）、版本号更新、CHANGELOG 更新，三者同步，只在用户明确要求时一起完成。
- **每次代码改动后自动检查 `TODO.md`**：对照本次改动判断 TODO 中哪些条目需要新增、修改状态或删除，列出建议变更内容并等待用户确认后再修改 TODO.md。
- **后端需要重启时自动执行**：凡后端代码有改动、或用户提到后端无响应/需要重启，自动运行 kill+restart 命令并通知用户"后端已重启"。Kill 命令：`for /f "tokens=5" %a in ('netstat -ano ^| findstr :8001') do taskkill /F /PID %a`，然后在 `astrology_api/` 目录启动 uvicorn。
- **架构变更时同步更新 `ARCHITECTURE.md`**：新增模块、端点、数据库表、外部服务、缓存策略、模块标准等任何架构层面的改动，必须在同一个 commit 中更新 `ARCHITECTURE.md` 对应章节。
- 不要自行修改代码中的格式问题
- 严格执行进度管理和token控制规则,避免中断再开后重读大段context,避免任务进程中的其他重读.

---

## 进度管理规则
- 每完成一个主要步骤后，立即更新 PROGRESS.md
- 长任务每完成 3-5 步主动写一次 checkpoint
- PROGRESS.md 必须包含：已完成的改动（具体文件+改了什么）、未完成的步骤、当前问题或关键决策、下一步从哪里开始
- 如果我说"写进度"或"存档"，立即将当前完整状态写入 PROGRESS.md
- 新会话开始时，如果存在 PROGRESS.md，先读取它再开始工作

## Token 控制规则
- 不要一次性读取超过 5 个文件
- 优先用 grep 定位再精确读取，不要整个文件全读
- 每完成 3 个 task 写一次 PROGRESS.md
- 自主执行，不需要每步确认
- 每完成一个 task 用中文一句话告诉我改了什么

## 工作流程 / Workflow

### 改动流程
- 收到任务后，先输出改动计划（涉及哪些文件、哪些函数、怎么改）
- 改动计划格式：列出 **[文件名 → 函数名 → 改什么]**，不要在计划阶段写具体代码
- 不要直接写代码，等我明确说"执行"后再动手
- 如果改动很小（< 10 行），可以直接写不用等确认
- 修改代码时不要输出"这段代码的作用是…"之类的解释，直接说改什么

### 代码风格
- 只使用 Turso，不需要 SQLite 兼容分支
- 英文注释+简单中文概括

### 功能测试（每个功能完成后必须执行）
每次完成一个功能或 bug fix 后，**在 commit+push 之前**，向用户列出测试清单并带领其完成：

1. 列出该功能涉及的所有测试路径（登录态 / 访客态 / 边界情况）
2. 逐条引导用户操作，明确告知：路径、预期结果、需要观察的具体现象
3. 等待用户反馈每条测试结果
4. 用户确认全部通过后再 commit + push
5. 若发现问题，先修复再重新测试，不跳过

### test.md 更新规则

每次代码改动后，**在向用户展示测试清单之前**，将本次改动的测试内容追加到 `test.md`：

- **不替换原有内容**——始终在文件末尾追加
- 每批新测试用独立的顶级标题（`# 功能名称（YYYY-MM-DD）`）与前面内容明确区隔，**不继续前面的编号**
- 标题下按功能分组，用二级标题（`## 1. 分组名`）自成体系，编号从 1 重新开始
- checkbox 格式 `- [ ]`，包含路径 + 预期结果
- 写完后随代码一起 commit（或作为紧随的 follow-up commit）

**格式示例（在文件末尾追加）：**
```markdown
---

# 功能名称（YYYY-MM-DD）

> 前置条件说明

## 1. 主要流程

- [ ] 路径描述 → 预期结果

## 2. 边界情况

- [ ] 路径描述 → 预期结果
```

### Commit
每次代码改动后立即 commit，不 push：

bash
git add <files>
git commit -m "type(scope): description"
Conventional Commits 格式，英文，72 字符以内。

Commit 后提示用户重启前端（npm run dev）或后端（uvicorn ...）视改动类型而定，在本地测试。

### Push + 版本发布（仅当用户明确要求时，三步同步完成）
Bump version in frontend/package.json
Update "Current version" line in this file
Add CHANGELOG.md entry
git add -A && git commit -m "chore(release): vX.Y.Z"
git tag vX.Y.Z
git push origin main && git push hf main
/clear guard
/clear 前检查 git status，有未提交改动则询问是否先 commit。

## AI 分析设计方针 / AI Analysis Design Principle
所有涉及 AI 分析的功能，必须同时满足以下三点：

RAG 知识增强：调用 Qdrant 检索相关书籍片段，拼入 prompt 作为参考依据，不允许裸调 Gemini。
后端 Analytics 记录：每次 AI 分析调用后，通过 _log_analytics 写入 query_analytics 表，记录 query hash、分类标签、最高相似度分、是否被引用，用于持续效果验证。
前端显示引用文献区块：使用 <SourcesSection> 组件展示 RAG 检索到的来源。
当前：所有用户可见（临时状态）。
目标：仅管理员可见。此权限控制待注册用户功能开发完成后实现（另一 terminal 正在开发）。
违反以上任意一点的 AI 分析端点均视为未完成实现。

新增 AI 功能时的强制 Checklist
每次新增或修改 AI 分析端点，在完成编码前必须逐条确认：

后端

 retrieve(query, k=N) 调用存在，query 语义贴合分析内容
 RAG 片段已注入 prompt（通过 rag_generate() 或手动 _build_rag_section()）
 返回值包含 sources 字段（格式：[{source, score, cited, text}]）
 router 中有 asyncio.create_task(_log_analytics(query, result)) 调用
前端

 AI 分析结果区域（非对话框）已渲染 <SourcesSection sources={...} />
 sources 数据已从 API 响应中正确传递到组件 props

## Current version / 当前版本
v0.8.2 — Tag 标签优化 + admin-prompts 修复 + debug UI 清理。
See CHANGELOG.md for full history.

## Commands / 命令
bash
### ── Backend ──────────────────────────────────────────────────
cd astrology_api
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
### API docs: http://127.0.0.1:8001/docs

### ── Frontend ─────────────────────────────────────────────────
cd frontend
npm install
npm run dev     # http://localhost:5173  (proxies /api → 127.0.0.1:8001)
npm run lint
npm run build

### ── Kill + restart backend (port 8001) ───────────────────────
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8001') do taskkill /F /PID %a
cd astrology_api && uvicorn main:app --host 127.0.0.1 --port 8001 --reload
Required env vars — copy astrology_api/.env.example to astrology_api/.env:

Variable	Purpose	Required
TURSO_DATABASE_URL	Turso libSQL URL (libsql://xxx.turso.io)	Always
TURSO_AUTH_TOKEN	Turso auth token	Always
GOOGLE_API_KEY	Gemini API key (RAG + chat)	Always
QDRANT_URL	Qdrant vector DB URL	Always
QDRANT_API_KEY	Qdrant API key	Always
SECRET_KEY	JWT signing key	Always

## Architecture / 架构
前后端分离：Python FastAPI 后端 + React/Vite 前端，开发时通过 Vite proxy 连接，生产环境由 HF Spaces 统一托管（前端静态文件由 FastAPI serve）。

text
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
    db.py          Turso HTTP 数据层，无 ORM
    rag.py         RAG 核心：Qdrant 检索 + Gemini 生成，classify_query，chat_with_chart
    schemas/       Pydantic models (models.py)
    security.py    JWT auth (require_auth, get_optional_user)
    svg/           SVG chart generators

### Key architectural notes
DB 层：app/db.py 是基于 Turso HTTP 的自定义数据层，不使用 SQLAlchemy。所有环境（开发 + 生产）均连接 Turso。
RAG：使用 Qdrant 向量库 + intfloat/multilingual-e5-small embedding + Gemini 生成。书籍文件名为 camelCase，_clean_source_name 做 camelCase 拆分后匹配引用。
Auth：JWT Bearer token，require_auth 依赖强制鉴权，get_optional_user 允许匿名（访客星盘自动标记 is_guest=1）。
跨 tab 星盘共享：ChartSessionContext 在内存中保存当前计算结果，访客切换到行运 tab 时可选"当前星盘（未保存）"。
Frontend port：后端必须跑在 8001，vite.config.js proxy target 对应此端口。
生产构建：npm run build 输出到 frontend/dist/，FastAPI 的 StaticFiles 从此目录 serve。

### Data model / 数据模型
Tables
saved_charts — 主表

Column	Type	Notes
id	INTEGER PK	
label	TEXT	显示名（name · YYYY/M/D）
name	TEXT	出生姓名
birth_year/month/day/hour/minute	INTEGER	
location_name	TEXT	Nominatim 地名
latitude / longitude	REAL	
tz_str	TEXT	IANA timezone
house_system	TEXT	e.g. "Placidus"
language	TEXT	e.g. "zh"
chart_data	TEXT	JSON-serialised NatalChartResponse
svg_data	TEXT	Raw SVG
is_guest	INTEGER	0 = 已审核，1 = 待审核访客
created_at	TEXT	UTC ISO
其他缓存表：transit_analysis_cache、transit_overall_cache、planet_analysis_cache、solar_return_cache、query_analytics

Schema 通过 create_tables() 启动时自动创建（Turso 端）。无迁移工具——schema 不兼容变更时需在 Turso 控制台手动处理。

### API endpoints / API 端点
星盘计算
Method	Path	Purpose
POST	/api/natal_chart	计算本命盘
POST	/api/svg_chart	生成 SVG 星盘图
POST	/api/transit_chart	计算行运盘
POST	/api/interpret/transits_full	行运完整 AI 分析（含缓存）
POST	/api/synastry	合盘
POST	/api/progressions	推运
POST	/api/solar-return	太阳回归
POST	/api/interpret_planets	行星解读（Gemini，含缓存）
POST	/api/interpret/chat	占星对话（RAG + Gemini）
POST	/api/rectify	出生时间校正

# Do not commit
astrology_api/charts.db （已弃用，仅防御性忽略）
astrology_api/.env
frontend/dist/
**/__pycache__/