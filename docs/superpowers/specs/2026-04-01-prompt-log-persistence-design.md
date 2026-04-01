# Prompt Log 持久化与版本管理设计

**日期**：2026-04-01
**状态**：已审核，待实现

---

## 背景与目标

当前 `prompt_log.py` 使用内存环形缓冲（`deque`，最多 200 条），后端重启后全部丢失。

目标：将每次 AI 调用记录持久化到 Turso，支持按 prompt 版本积累数据，供管理员对比不同 prompt 版本的输出质量，决定是否部署新版本。

---

## 数据模型

### `prompt_versions`

每个 caller 的 prompt 全文只存一次，以版本号索引。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | uuid hex |
| caller | TEXT | 业务功能内部标识，如 `interpret_planets`、`transits_full` |
| version_tag | TEXT | 如 `v1`、`v1.1`、`v2`（同一 caller 内，UNIQUE(caller, version_tag)）|
| prompt_text | TEXT | 完整 prompt 模板 |
| system_instruction | TEXT | system prompt（可空）|
| status | TEXT | `draft` / `deployed` / `superseded` / `retired` |
| created_at | TEXT | UTC ISO |
| deployed_at | TEXT | 部署时间（null = 未部署）|

**版本号规则**：
- 当前线上版本为 `v1`
- 第一版草稿为 `v1.1`，继续修改推进为 `v1.2`、`v1.3`...
- 管理员确认部署时，当前草稿（如 `v1.2`）的 version_tag 改写为 `v2`，status 改为 `deployed`
- 旧 deployed 版本改为 `retired`，被取代的草稿改为 `superseded`

**状态机**：
```
draft ──[run-test, 可多次]──→ draft
draft ──[revise]────────────→ superseded  （同时创建新 draft）
draft ──[deploy]────────────→ deployed    （version_tag 改为 v{n+1}）
deployed ──[新版本部署]──────→ retired
```

**初始 seed**：系统上线后，管理员需通过 admin 界面为每个 caller 手动创建 `version_tag=v1, status=deployed` 的初始版本，写入当前实际使用的 prompt 内容。未 seed 前，production logs 的 version_id 允许为 null。

### `prompt_logs`

每次实际 AI 调用记录一条，替代现有内存存储。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | |
| version_id | TEXT | → prompt_versions.id（可空，seed 完成前的早期记录）|
| source | TEXT | `test`（管理员测试）/ `production`（真实用户）|
| input_data | TEXT | JSON，完整输入（星盘数据等）|
| rag_query | TEXT | |
| rag_chunks | TEXT | JSON |
| response_text | TEXT | 完整 AI 输出 |
| latency_ms | INTEGER | |
| model_used | TEXT | |
| temperature | REAL | |
| finish_reason | TEXT | |
| prompt_tokens_est | INTEGER | |
| response_tokens_est | INTEGER | |
| user_id | TEXT | production 调用时填入（可空）|
| created_at | TEXT | UTC ISO |

**version_id 解析**：`prompt_store.append()` 写入 DB 时，后端维护一个内存字典 `_deployed_version_cache: {caller: version_id}`，在 `create_tables()` 启动时从 DB 预热。每次 deploy 操作后同步更新此缓存。写入 DB 为异步 best-effort（`asyncio.create_task`），失败只记录 log，不影响主流程。

### `prompt_evaluations`

每条 log 可关联多条评价记录，evaluator_type 区分来源。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | |
| log_id | TEXT | → prompt_logs.id |
| version_id | TEXT | 冗余字段，方便按版本聚合（与 log 的 version_id 一致）|
| compared_to_log_id | TEXT | AI 对比评价时填入另一条 log id（可空）|
| evaluator_type | TEXT | `ai_absolute` / `ai_comparative` / `admin` / `user` |
| score_overall | REAL | 1-5（可空）|
| dimensions | TEXT | JSON，如 `{"accuracy":4,"readability":5,"astro_quality":3}` |
| notes | TEXT | AI 或管理员的文字说明 |
| suggestions | TEXT | JSON 数组，AI 输出的改进建议（ai_* 类型专用）|
| created_at | TEXT | UTC ISO |

**用户评价维度**：文案"你认为该分析在多大程度上展示了差异化？"，低/中/高三档（映射 1/3/5），可附文字反馈写入 notes。

### `user_feedback`

全局反馈入口收集的非结构化反馈，不关联具体 log。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | |
| caller | TEXT | 内部功能标识（可空，用户选"其他"时为 null）|
| content | TEXT | 文字反馈内容 |
| user_id | TEXT | 可空 |
| created_at | TEXT | UTC ISO |

前端选项使用中文显示标签，提交时映射为内部 caller key（如"行运分析" → `transits_full`）。

---

## DDL

```sql
CREATE TABLE IF NOT EXISTS prompt_versions (
    id TEXT PRIMARY KEY,
    caller TEXT NOT NULL,
    version_tag TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    system_instruction TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    deployed_at TEXT,
    UNIQUE(caller, version_tag)
);

CREATE TABLE IF NOT EXISTS prompt_logs (
    id TEXT PRIMARY KEY,
    version_id TEXT,
    source TEXT NOT NULL,
    input_data TEXT,
    rag_query TEXT,
    rag_chunks TEXT,
    response_text TEXT,
    latency_ms INTEGER,
    model_used TEXT,
    temperature REAL,
    finish_reason TEXT,
    prompt_tokens_est INTEGER,
    response_tokens_est INTEGER,
    user_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_evaluations (
    id TEXT PRIMARY KEY,
    log_id TEXT NOT NULL,
    version_id TEXT,
    compared_to_log_id TEXT,
    evaluator_type TEXT NOT NULL,
    score_overall REAL,
    dimensions TEXT,
    notes TEXT,
    suggestions TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id TEXT PRIMARY KEY,
    caller TEXT,
    content TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL
);
```

---

## 工作流程

### Phase 1：管理员小范围测试

```
1. 创建草稿
   POST /api/admin/prompt-versions
   → 基于当前 deployed 版本内容预填，创建 status=draft，version_tag=v{n}.1

2. 编辑草稿（可选）
   PATCH /api/admin/prompt-versions/{id}
   → 直接修改 prompt_text / system_instruction（draft 状态才允许）

3. 运行测试
   POST /api/admin/prompt-versions/{id}/run-test
   body: { "chart_id": "<管理员已保存的星盘 id>" }
   → 用指定星盘数据调用 AI，写入 prompt_logs（source=test）
   → 同步触发 AI 绝对评分（ai_absolute）→ 写入 prompt_evaluations
   → 同步触发 AI 对比评分（ai_comparative）
     · 对比目标：当前 deployed 版本的最近 test log；如无 test log，则取最近 production log
     · 均无时跳过对比评分，仅输出绝对评分
   → AI 评分低或对比劣于上版时，suggestions 字段必填
   → 返回：test log + 两种评分 + 改进建议

4. 管理员填写评价
   POST /api/admin/prompt-evaluations
   → evaluator_type=admin，填写评分 + 文字判断

5a. 决策：部署
    POST /api/admin/prompt-versions/{id}/deploy
    → 草稿 version_tag 改写为 v{n+1}，status=deployed，填入 deployed_at
    → 原 deployed 版本改为 retired
    → 更新内存 _deployed_version_cache

5b. 决策：继续修改
    POST /api/admin/prompt-versions/{id}/revise
    → 当前草稿改为 status=superseded
    → 创建新草稿，version_tag 递增（v1.1 → v1.2）
    → 回到步骤 2
```

### Phase 2：生产环境数据收集

```
- 所有 production AI 调用自动写入 prompt_logs（version_id = 缓存中当前 deployed 版本）
- 用户切换 tab 时触发评分弹窗（拦截 tab 切换，完成/关闭后再切换）
  → 用户评分写入 prompt_evaluations（evaluator_type=user）
  → 用户关闭弹窗时显示提示："你的反馈帮助我们持续优化"
  → 连续关闭 3 次后显示一次加强提示，之后重置计数
- 管理员可在 admin 页面对某版本触发批量 AI 评分
```

---

## API 端点

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/admin/prompt-versions` | 列出所有 caller 的版本（支持 caller 过滤）|
| POST | `/api/admin/prompt-versions` | 创建草稿 |
| GET | `/api/admin/prompt-versions/{id}` | 获取单个版本完整内容 |
| PATCH | `/api/admin/prompt-versions/{id}` | 编辑草稿内容（仅 draft 状态可操作）|
| POST | `/api/admin/prompt-versions/{id}/run-test` | 触发测试运行（含 AI 评分）|
| POST | `/api/admin/prompt-versions/{id}/revise` | 基于当前草稿创建下一版草稿 |
| POST | `/api/admin/prompt-versions/{id}/deploy` | 部署草稿为正式版本 |
| GET | `/api/admin/prompt-logs` | 查询 logs（按 version_id / caller / source 过滤）|
| GET | `/api/admin/prompt-logs/{log_id}/evaluations` | 获取某条 log 的所有评价 |
| POST | `/api/admin/prompt-evaluations` | 提交管理员评价 |
| GET | `/api/admin/prompt-versions/{id}/compare` | 对比两版本 evaluations 汇总 |
| POST | `/api/user/prompt-evaluations` | 提交用户评分（tab 切换触发）|
| POST | `/api/user/feedback` | 提交全局文字反馈 |

---

## AI 评价输出结构

```json
{
  "evaluator_type": "ai_absolute",
  "score_overall": 3.2,
  "dimensions": {
    "accuracy": 3,
    "readability": 4,
    "astro_quality": 3
  },
  "notes": "输出内容结构清晰，但对逆行行星的解读缺乏专业深度...",
  "suggestions": [
    "建议在 prompt 中明确要求输出具体度数和相位容许度",
    "当前版本对逆行行星的处理缺乏专业性，可补充相关指引"
  ]
}
```

对比评价（ai_comparative）额外填入 `compared_to_log_id`，notes 中包含版本间差异分析。

---

## 前端 UI

### Admin：版本列表页 `/admin/prompts`

- Caller 下拉选择器（内部 key，显示中文标签）
- 版本列表：version_tag、status badge、创建时间
- deployed 版本高亮；superseded/retired 版本默认折叠可展开
- [+ 新建草稿] 按钮，基于当前 deployed 内容预填

### Admin：测试对比详情页（点击草稿版本进入）

- 左侧：草稿 prompt（可编辑，自动保存 PATCH）
- 右侧：当前 deployed prompt（只读对比）
- [运行测试] 按钮（弹出选择管理员已保存星盘的对话框）
- 结果展示：左侧草稿输出 / 右侧 deployed 输出
- AI 绝对评分 + AI 对比评分 + 改进建议（折叠展开）
- 管理员评价输入区（评分 + 文字）
- 底部操作：[保存草稿继续修改（创建新修订版）] / [确认部署为 v{n+1}]

### 用户侧：Tab 切换评分弹窗

- 触发时机：用户切换到任意其他 tab，且当前 tab 有未评分的 AI 结果
- 弹窗内容：
  - 标题："你认为该分析在多大程度上展示了差异化？"
  - 选项：低 / 中 / 高（单选，映射 1/3/5）
  - 可选文字反馈输入框
  - [提交] / [关闭]
- 关闭后显示提示文案："你的反馈帮助我们持续优化"
- 连续关闭 3 次后触发一次加强提示，之后重置计数

### 用户侧：全局反馈入口

- 固定悬浮按钮（右下角）
- 点击弹出功能分类选择（中文标签，提交时映射为内部 caller key）
- 选择后显示文字输入框
- 提交写入 `user_feedback` 表

---

## Prompt Registry（集中式 prompt 管理）

### 目标

将所有业务 prompt 从函数体内联 f-string 抽出，集中到单一文件 `astrology_api/app/rag/prompt_registry.py`，作为：
1. 人类可读的 prompt 参考（直接看文件即可，无需打开数据库）
2. Seed 脚本的数据源（首次部署时自动将 `v1` 写入 `prompt_versions`）
3. 代码运行时的 source of truth（各函数 import 并填入变量）

### 结构

```python
# astrology_api/app/rag/prompt_registry.py

PROMPTS: dict[str, dict] = {
    "interpret_planets": {
        "system_instruction": "你是一位执业25年的西方占星师...",
        "prompt_template": "请分析以下本命盘行星配置：\n{chart_summary}\n...",
        "temperature": 0.3,
        "description": "本命盘逐行星 AI 解读",
    },
    "transits_full": {
        "system_instruction": None,   # 使用 _SYSTEM_PROMPT_UNIFIED 或 None
        "prompt_template": "行运日期：{transit_date}\n{chart_summary}\n...",
        "temperature": 0.5,
        "description": "行运完整分析",
    },
    # ... 其余 caller
}
```

### 覆盖的 caller

| caller | 当前 prompt 位置 |
|---|---|
| `interpret_planets` | `rag/planets.py` |
| `transits_single` | `rag/transit.py` |
| `transits_full` | `rag/transit.py` |
| `chat_with_chart` | `rag/chat.py` |
| `generate` | `rag/chat.py` |
| `analyze_synastry` | `rag/synastry.py` |
| `analyze_solar_return` | `rag/solar_return.py` |
| `analyze_rectification` | `rag/rectification.py` |
| `generate_asc_quiz` | `rag/rectification.py` |
| `calc_confidence` | `rag/rectification.py` |
| `system` | `rag/prompts.py`（`_SYSTEM_PROMPT_UNIFIED`）|

### 函数改造模式

各函数改为从 registry 取模板后填入本地变量：

```python
from ..rag.prompt_registry import PROMPTS

tmpl = PROMPTS["interpret_planets"]["prompt_template"]
prompt = tmpl.format(chart_summary=chart_summary, planet_lines=planet_lines)
```

### Seed 脚本

`astrology_api/app/db_seed.py`（新增，可独立运行也可在 `create_tables()` 中调用）：

```python
# 对每个 caller，若 DB 中不存在 status=deployed 的记录，则插入 v1
for caller, cfg in PROMPTS.items():
    if not _has_deployed_version(caller):
        insert_prompt_version(caller, "v1", cfg["prompt_template"], cfg["system_instruction"])
```

---

## 迁移说明

- `prompt_log.py` 的内存 `prompt_store` 保留，用于实时 debug 查看（现有 debug_router 接口不变）
- 新增持久化写入：每次 `prompt_store.append()` 同时通过 `asyncio.create_task` 异步写入 Turso `prompt_logs`，失败只打印 log，不影响主流程
- `PromptLogEntry` 新增 `version_id: str = ""` 字段，由 `rag/client.py` 调用时从 `_deployed_version_cache` 查询填入
- 四张新表通过 `create_tables()` 启动时自动创建（DDL 见上方）
- 启动时预热 `_deployed_version_cache`：查询所有 `status=deployed` 的版本，建立 `{caller: id}` 字典
- 初始 seed：管理员在 admin 界面为每个 caller 手动创建 `v1` 版本（写入当前实际使用的 prompt）；seed 完成前 production logs 的 version_id 为 null，不影响功能
