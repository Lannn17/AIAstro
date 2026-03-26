# AIAstro — 完整架构文档 v0.7.0

> 本文档描述当前程序的所有功能、实现逻辑和外部集成，供开发参考。

---

## 目录

1. [功能状态总览](#1-功能状态总览)
2. [前端页面与 Tab](#2-前端页面与-tab)
3. [前端组件](#3-前端组件)
4. [前端 Hooks / Contexts](#4-前端-hooks--contexts)
5. [后端 API 端点](#5-后端-api-端点)
6. [数据库结构](#6-数据库结构)
7. [外部服务与集成](#7-外部服务与集成)
8. [RAG 管道](#8-rag-管道)
9. [认证系统](#9-认证系统)
10. [缓存策略](#10-缓存策略)
11. [模块架构标准（三件套）](#11-模块架构标准三件套)
12. [前后端通信](#12-前后端通信)
13. [部署](#13-部署)

---

## 1. 功能状态总览

| 功能 | 状态 | 后端 | 前端 | 备注 |
|---|---|---|---|---|
| 本命盘计算 | ✅ | `/api/natal_chart` | NatalChart | Kerykeion 计算引擎 |
| SVG 星盘图 | ✅ | `/api/svg_chart` | ChartWheel | KerykeionChartSVG |
| 星盘存取（CRUD） | ✅ | `/api/charts` | NatalChart 侧边栏 | SQLite / Turso 双模式 |
| 行星解读 | ✅ | `/api/interpret_planets` | NatalChart 展开区 | RAG + Gemini，带 DB 缓存 |
| 地点搜索 | ✅ | 前端直连 Nominatim | LocationSearch | 500ms 防抖，自动填经纬度 |
| 多语言 UI | ✅ | — | ChartForm | zh/ja/en/pt/es/fr/de |
| JWT 登录 | ✅ | `/api/auth/login` | LoginModal | Bearer Token，30天有效 |
| 访客模式 | ✅ | is_guest 字段 + 审核流 | GuestSaveConfirmModal | 提交→待审核→管理员批准 |
| 占星对话（RAG） | ✅ | `/api/interpret/chat` | AIPanel（NatalChart） | 多轮 + 历史压缩 |
| 行运分析 | ✅ | `/api/interpret/transits_full` | Transits Tab | 逐相位 + 整体综述，带 DB 缓存 |
| 出生时间校正 | ✅ | `/api/rectify/*` | NatalChart 校正 Tab | 事件评分 + 答题 + 置信度 |
| 合盘（Synastry） | ✅ | `/api/synastry` + `/api/interpret/synastry` | Synastry Tab | 计算 + RAG 解读，带 DB 缓存 |
| RAG 质量后台 | ✅ | `/api/admin/analytics` | `/admin` 隐藏路由 | 分类统计 + 引用率 + 报告 |
| 推运 | 🚧 Stub | `/api/progressions` | Progressions Tab | 仅计算，无 AI 解读 |
| 太阳回归 | 🚧 Stub | `/api/solar-return` | SolarReturn Tab | 仅计算 |
| 方向法 | 🚧 Stub | `/api/solar-arc` | Directions Tab | 仅计算 |

---

## 2. 前端页面与 Tab

| 文件 | 路由 | 主要功能 |
|---|---|---|
| `NatalChart.jsx` | `/` | 本命盘计算、SVG 图、行星表、行星解读、校正、占星对话 |
| `Transits.jsx` | `/transits` | 行运分析（选盘 + 日期）、活跃相位列表、AI 综述 |
| `Synastry.jsx` | `/synastry` | 双盘输入（手填/从已保存加载）、相位表、SVG 双盘图、AI 解读 |
| `Progressions.jsx` | `/progressions` | 推运计算（Stub，无 AI） |
| `SolarReturn.jsx` | `/solar-return` | 太阳回归计算（Stub） |
| `Directions.jsx` | `/directions` | 方向法计算（Stub） |
| `Analytics.jsx` | `/admin` | RAG 质量仪表盘（隐藏路由，需登录） |

---

## 3. 前端组件

| 文件 | 用途 | 关键 Props |
|---|---|---|
| `ChartForm.jsx` | 出生数据输入表单 | `onSubmit`, `initialData`, `loading` |
| `LocationSearch.jsx` | Nominatim 地点搜索 | `initialValue`, `latitude`, `longitude`, `onSelect({lat,lng,locationName})` |
| `ChartWheel.jsx` | SVG 星盘图渲染 | `svgContent` |
| `PlanetTable.jsx` | 行星位置表（星座/宫位/品质） | `planets`, `language`, `analyses` |
| `AIPanel.jsx` | 通用 AI 解读面板 | `onGenerate`, `loading`, `result`, `error`, `label`, `disabled`, `children` |
| `SourcesSection.jsx` (AIPanel 内) | RAG 引用展示区 | `sources[]`（含 cited/score/summary_zh） |
| `LoginModal.jsx` | JWT 登录 / 访客选择 | — |
| `GuestSaveConfirmModal.jsx` | 访客保存确认 | `onConfirm`, `onCancel` |
| `GuestSessionList.jsx` | 访客会话多图列表 | — |

---

## 4. 前端 Hooks / Contexts

| 文件 | 类型 | 提供的状态 / 方法 |
|---|---|---|
| `AuthContext.jsx` | Context | `token`, `isGuest`, `isAuthenticated`, `login()`, `logout()`, `continueAsGuest()`, `authHeaders()`, `sessionKey` |
| `ChartSessionContext.jsx` | Context | `sessionCharts[]`, `currentSessionId`, `addSessionChart()`, `clearSessionCharts()` — 跨 Tab 共享当前星盘 |
| `useInterpret.js` | Hook | `run(body, extraHeaders?)` → `(loading, result, error, reset)` — 所有 AI/RAG 端点的通用异步状态封装 |

---

## 5. 后端 API 端点

### 5a. 星盘计算

| Method | Path | Auth | 功能 |
|---|---|---|---|
| POST | `/api/natal_chart` | 无 | 计算本命盘 |
| POST | `/api/svg_chart` | 无 | 生成 SVG 星盘图 |
| POST | `/api/svg_chart_base64` | 无 | SVG 转 base64 |
| POST | `/api/interpret_planets` | 无 | 行星 AI 解读（RAG + Gemini + DB 缓存） |

### 5b. 行运

| Method | Path | Auth | 缓存 | 功能 |
|---|---|---|---|---|
| POST | `/api/transit_chart` | 无 | 无 | 计算行运盘 |
| POST | `/api/transits_to_natal` | 无 | 无 | 计算行运-本命相位 |
| POST | `/api/interpret/transit` | 无 | DB | 单次行运 AI 解读（RAG） |
| POST | `/api/interpret/transits_full` | 无 | DB | 完整行运报告（逐相位 + 整体，RAG） |

### 5c. 合盘

| Method | Path | Auth | 缓存 | 功能 |
|---|---|---|---|---|
| POST | `/api/synastry` | 无 | 无 | 计算合盘相位 |
| POST | `/api/interpret/synastry` | 无 | DB | 合盘 AI 解读（RAG，按相位 hash 缓存） |

### 5d. AI / RAG 对话

| Method | Path | Auth | 功能 |
|---|---|---|---|
| POST | `/api/interpret/chat` | 无 | 占星对话（RAG + Gemini，多轮历史） |
| POST | `/api/interpret/summarize` | 无 | 压缩多轮历史为摘要 |
| GET  | `/api/interpret` | 无 | 全文检索解读库 |

### 5e. 推运 / 回归 / 方向法

| Method | Path | 功能 |
|---|---|---|
| POST | `/api/progressions` | 二次推运计算 |
| POST | `/api/solar-return` | 太阳回归 |
| POST | `/api/lunar-return` | 月亮回归 |
| POST | `/api/solar-arc` | 太阳弧方向法 |

### 5f. 校正

| Method | Path | 功能 |
|---|---|---|
| POST | `/api/rectify` | 事件评分校正算法 |
| GET  | `/api/rectify/versions` | 列出算法版本 |
| POST | `/api/rectify/asc_quiz` | 上升星座推测 |
| GET  | `/api/rectify/theme_quiz` | 人生主题问卷 |
| POST | `/api/rectify/confidence` | 时间置信度估算 |

### 5g. 星盘存取（需登录）

| Method | Path | Auth | 功能 |
|---|---|---|---|
| GET    | `/api/charts` | **必须** | 列出已保存星盘 |
| POST   | `/api/charts` | 可选 | 保存星盘（访客自动 is_guest=1） |
| GET    | `/api/charts/{id}` | **必须** | 读取完整星盘（含时分） |
| PATCH  | `/api/charts/{id}` | **必须** | 更新星盘 |
| DELETE | `/api/charts/{id}` | **必须** | 删除星盘 |
| GET    | `/api/charts/pending` | **必须** | 列出待审核访客星盘 |
| POST   | `/api/charts/pending/{id}/approve` | **必须** | 批准访客星盘 |
| GET    | `/api/charts/{id}/events` | **必须** | 读取星盘的生活事件列表 |
| PUT    | `/api/charts/{id}/events` | **必须** | 替换星盘的全部生活事件（批量保存） |

### 5h. 认证 & 管理

| Method | Path | Auth | 功能 |
|---|---|---|---|
| POST | `/api/auth/login` | 无 | 登录，返回 JWT |
| GET  | `/api/auth/me` | **必须** | 获取当前用户 |
| GET  | `/api/admin/analytics` | **必须** | RAG 统计数据（聚合 + 最近200条） |
| POST | `/api/admin/analytics/report` | **必须** | Gemini 生成 RAG 质量报告 |

---

## 6. 数据库结构

### `saved_charts` — 主表

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK | 自增 |
| `label` | TEXT | 显示名（"姓名 · YYYY/M/D"） |
| `name` | TEXT | 出生姓名 |
| `birth_year/month/day` | INTEGER | 出生日期 |
| `birth_hour/minute` | INTEGER | 出生时分（24h） |
| `location_name` | TEXT | 地名（来自 Nominatim） |
| `latitude/longitude` | REAL | 坐标 |
| `tz_str` | TEXT | IANA 时区（如 "Asia/Shanghai"） |
| `house_system` | TEXT | 宫位制（Placidus / Whole Sign 等） |
| `language` | TEXT | 语言（zh/en/ja/pt/es/fr/de） |
| `chart_data` | TEXT | 完整 NatalChartResponse（JSON） |
| `svg_data` | TEXT | 原始 SVG 字符串 |
| `is_guest` | INTEGER | 0=已审核，1=待审核 |
| `created_at` | TEXT | UTC ISO 时间戳 |

### `transit_analysis_cache` — 行运逐相位缓存

| 列 | 说明 |
|---|---|
| `chart_id` + `transit_key` | 联合唯一键（UNIQUE） |
| `analysis` | AI 解读文本 |
| `tone` | 顺势 / 挑战 / 转化 |
| `themes` | JSON 数组（事业/感情/健康等） |
| `end_date` | 缓存有效期（行运结束日期） |

### `transit_overall_cache` — 行运整体综述缓存

| 列 | 说明 |
|---|---|
| `chart_id` + `transit_set_hash` | 联合唯一键（按相位集合 MD5 hash） |
| `overall` | 整体综述文本 |

### `planet_analysis_cache` — 行星解读缓存

| 列 | 说明 |
|---|---|
| `chart_id` | PK（每张盘一条记录） |
| `chart_hash` | 输入数据 MD5（hash 不匹配则失效） |
| `analyses` | JSON，各行星解读 + overall 对象 |

### `synastry_cache` — 合盘缓存

| 列 | 说明 |
|---|---|
| `aspects_hash` | PK（相位列表 MD5，确定性 hash） |
| `answer` | AI 解读文本 |
| `sources` | JSON，RAG 来源列表 |

### `query_analytics` — RAG 质量追踪

| 列 | 说明 |
|---|---|
| `query_hash` | 查询 SHA256 |
| `label` | 分类标签（7 类） |
| `max_rag_score` | 最高检索相似度 |
| `any_cited` | AI 是否引用了书籍（0/1） |
| `created_at` | 时间戳 |

### `life_events` — 校正生活事件持久化

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK | 自增 |
| `chart_id` | INTEGER | 关联 saved_charts(id)，级联删除 |
| `year` | INTEGER | 事件年份（必填） |
| `month` | INTEGER | 事件月份（可选） |
| `day` | INTEGER | 事件日（可选，需有月份） |
| `event_type` | TEXT | 事件类型（career_up / marriage 等） |
| `weight` | REAL | 权重（1=一般，2=重要，3=非常重要） |
| `is_turning_point` | INTEGER | 是否为人生转折点（0/1） |
| `domain_id` | TEXT | 所属领域 ID（career/romance/family 等） |
| `created_at` | TEXT | UTC 时间戳 |

---

## 7. 外部服务与集成

| 服务 | 用途 | 认证方式 | 相关环境变量 |
|---|---|---|---|
| **Google Gemini** | 文本生成（解读 + 分类 + 报告） | API Key | `GOOGLE_API_KEY` |
| **Qdrant** | 向量数据库（书籍片段检索） | API Key + URL | `QDRANT_URL`, `QDRANT_API_KEY` |
| **Sentence-Transformers** (intfloat/multilingual-e5-small) | 本地 embedding 模型 | 无（HF 预下载） | — |
| **Turso (libSQL)** | 云端数据库（生产） | Auth Token | `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` |
| **SQLite** | 本地数据库（开发） | 文件路径 | —（无 Turso 变量时自动使用） |
| **Nominatim (OpenStreetMap)** | 地址 → 经纬度（前端直连） | 无 | — |
| **Kerykeion** | 占星计算引擎（行星/宫位/相位） | 无（本地库） | — |
| **PyJWT** | JWT 签发与验证 | 密钥 | `SECRET_KEY` |
| **HuggingFace Spaces** | 云端部署平台 | HF Token（CI） | — |

---

## 8. RAG 管道

### 核心函数（`app/rag.py`）

| 函数 | 功能 |
|---|---|
| `retrieve(query, k=5)` | E5 编码 → Qdrant 向量检索，返回 top-k 书籍片段 |
| `_build_rag_section(chunks)` | 将片段格式化为 prompt 追加块（含引用指令） |
| `rag_generate(query, prompt, k, temperature)` | **统一 RAG 入口**：retrieve → build → Gemini → parse → detect，返回 (answer, sources) |
| `_parse_answer_with_refs(raw, num_chunks)` | 按 `===引用概括===` 分割输出，返回 (主文本, {序号: 中文概括}) |
| `_detect_citations(answer, chunks, summaries)` | 检测 AI 是否引用了各片段，返回含 `cited/score/summary_zh` 的 sources 列表 |
| `classify_query(query)` | Gemini 将问题分类为 7 个标签之一（用于 analytics） |
| `format_chart_summary(chart_data)` | 将本命盘数据格式化为 LLM 可读摘要（含星座/宫位/品质/相位） |
| `chat_with_chart(query, chart_data, history, summary)` | 多轮对话（特殊：自建 contents 注入历史，直接调 retrieve + _build_rag_section） |
| `analyze_transits(...)` | 行运解读，调 `rag_generate` |
| `analyze_active_transits_full(...)` | 完整行运报告，JSON 模式，source_refs 方案注入 RAG |
| `analyze_synastry(...)` | 合盘解读，调 `rag_generate` |
| `analyze_planets(...)` | 行星解读，JSON 模式，source_refs 方案注入 RAG |

### 流程图

```
用户请求（对话 / 解读 / 合盘）
    │
    ▼
[1] retrieve(query, k=5)
    Qdrant "astro_chunks" 集合
    E5 multilingual 向量相似度检索
    │
    ▼
[2] _build_rag_section(chunks)
    格式化为 [参考N · 书名]\n原文
    追加引用指令（===引用概括=== 分隔符）
    │
    ▼
[3] Gemini 生成
    system_instruction = 专业占星师 system prompt
    输入 = 领域 prompt + rag_section
    │
    ▼
[4] _parse_answer_with_refs(response, num_chunks)
    分离主答案 / 引用概括区块
    返回 (answer, {序号: 中文概括})
    │
    ▼
[5] _detect_citations(answer, chunks, summaries)
    匹配书名 / 参考编号 → cited: bool
    附加 summary_zh（中文概括）
    返回 sources[]
    │
    ▼
[6] Router 层 _log_analytics(query, result)
    classify_query → label
    写入 query_analytics 表
    │
    ▼
返回前端 {answer, sources[{source,score,cited,summary_zh}], index_used}
```

### JSON 模式 RAG（行运 Full + 行星解读）

JSON 模式下无法使用 `===引用概括===`，改用 `source_refs` 字段注入 JSON schema：

```json
{
  "aspects": [...],
  "overall": "...",
  "source_refs": {"1": "中文概括", "3": "中文概括"}
}
```

---

## 9. 认证系统

### JWT 流程

```
POST /api/auth/login {username, password}
    ↓ 验证 env 变量 AUTH_USERNAME / AUTH_PASSWORD
    ↓ PyJWT 签发 HS256 token（有效期 30 天）
    ↓ 返回 {access_token, token_type: "bearer"}

前端存入 localStorage["auth_token"]
每次请求加 Authorization: Bearer {token}

后端依赖：
  require_auth       → 未登录返回 401（charts CRUD 使用）
  get_optional_user  → 无 token 返回 None（对话/保存允许访客）
```

### 访客模式

```
用户点击"继续体验（访客）"
    ↓ localStorage["guest_mode"] = "true"
    ↓ 可计算星盘、使用 AI 解读
    ↓ 保存星盘 → is_guest=1，进入待审核队列
    ↓ 管理员 /admin → 审核通过 → is_guest=0，进入正式列表
```

---

## 10. 缓存策略

| 模块 | 缓存表 | 缓存键 | 失效条件 |
|---|---|---|---|
| 行运逐相位 | `transit_analysis_cache` | (chart_id, transit_key) | `end_date < today`（行运结束后自动失效） |
| 行运整体综述 | `transit_overall_cache` | (chart_id, transit_set_hash) | 无失效（相位集合变化则产生新 hash） |
| 行星解读 | `planet_analysis_cache` | (chart_id, chart_hash) | chart_hash 不匹配时重新生成 |
| 合盘解读 | `synastry_cache` | aspects_hash（相位列表 MD5） | 无失效 |
| 访客会话多图 | 内存（ChartSessionContext） | sessionId | 登出 / 刷新页面后清除 |

---

## 11. 模块架构标准（三件套）

**所有业务模块**（含未来开发的推运、太阳回归、方向法）必须同时具备：

| 标准 | 实现方式 | 说明 |
|---|---|---|
| **RAG 知识增强** | 调用 `rag_generate(query, prompt)` | 普通文本模式；JSON 模式用 `source_refs` 方案 |
| **DB 缓存** | 新建对应缓存表 + `db_get_*` / `db_save_*` | 键策略按模块特性设计（hash / id+date 等） |
| **Analytics 记录** | Router 层调 `_log_analytics(query, result)` | 非阻塞后台任务（`asyncio.create_task`） |

---

## 12. 前后端通信

### 开发环境

```javascript
// vite.config.js
proxy: { '/api': 'http://127.0.0.1:8001' }

// 前端使用
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
// 开发时 '' → Vite proxy 转发
```

### 生产环境

FastAPI 直接 serve `frontend/dist/` 静态文件，前后端同源，无需 proxy。

```python
# main.py
app.mount("/", StaticFiles(directory="frontend/dist", html=True))
```

### 请求头

| 情况 | Header |
|---|---|
| 已登录 | `Authorization: Bearer {token}` |
| 访客 / 无需认证 | 无 |
| 所有 POST/PATCH | `Content-Type: application/json` |

---

## 13. 部署

### HuggingFace Spaces（生产）

| 项目 | 值 |
|---|---|
| URL | `lannn17-astro.hf.space` |
| 端口 | 7860 |
| 构建方式 | Dockerfile 多阶段：Node 22 构建前端 → Python 3.11 安装后端 → 下载 E5 模型权重 |
| 静态文件 | `frontend/dist/` 由 FastAPI StaticFiles serve |
| SPA 路由 | FastAPI catch-all → `dist/index.html` |
| 数据库 | Turso（云端 libSQL）|

### 本地开发

```bash
# 后端（8001 端口，必须）
cd astrology_api
uvicorn main:app --host 127.0.0.1 --port 8001 --reload

# 前端（5173 端口）
cd frontend
npm run dev
```

### 环境变量

| 变量 | 必须 | 说明 |
|---|---|---|
| `GOOGLE_API_KEY` | 始终 | Gemini API |
| `QDRANT_URL` | 始终 | Qdrant 实例 URL |
| `QDRANT_API_KEY` | 始终 | Qdrant 认证 |
| `SECRET_KEY` | 始终 | JWT 签名密钥 |
| `TURSO_DATABASE_URL` | 仅生产 | Turso libSQL URL |
| `TURSO_AUTH_TOKEN` | 仅生产 | Turso 认证 |
| `AUTH_USERNAME` | 始终 | 管理员用户名 |
| `AUTH_PASSWORD` | 始终 | 管理员密码 |

---

*最后更新：v0.7.0 — 2026-03-26*
