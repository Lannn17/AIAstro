# Prompt Log Persistence — Progress

Branch: `feature/prompt-log-persistence`
Worktree: `.worktrees/feature-prompt-log-persistence`
Plan: `docs/superpowers/plans/2026-04-01-prompt-log-backend-plan.md`

---

## Status

| Task | Description | Status |
|------|-------------|--------|
| 1 | Create `prompt_registry.py` | ✅ Done |
| 2 | Refactor `planets.py` | ✅ Done |
| 3 | Refactor `transit.py` | ✅ Done |
| 4 | Refactor `chat.py`, `synastry.py`, `solar_return.py`, `rectification.py` | ✅ Done |
| 5 | Add 4 DB tables to `db.py` | 🔄 In Progress |
| 6 | Add DB helpers for prompt_versions (+ `_turso_query` wrapper) | ⬜ Pending |
| 7 | Add DB helpers for prompt_logs, prompt_evaluations, user_feedback | ⬜ Pending |
| 8 | Add `_deployed_version_cache` + startup warm-up | ⬜ Pending |
| 9 | Add `db_seed.py` | ⬜ Pending |
| 10 | Update `PromptLogEntry` + wire sync persistence in `client.py` | ⬜ Pending |
| 11 | Admin router — versions CRUD | ⬜ Pending |
| 12 | Admin router — run-test + AI evaluation | ⬜ Pending |
| 13 | Admin router — deploy, revise, compare | ⬜ Pending |
| 14 | Add `user_router.py`, register in `main.py` | ⬜ Pending |

---

## Checkpoint — 2026-04-01

### 已完成

**Task 1** — `astrology_api/app/rag/prompt_registry.py` 创建完毕
- 12 个 caller key 全部收录（system, interpret_planets, transits_single, transits_full_new, transits_full_summary, generate, chat_with_chart, analyze_synastry, analyze_solar_return, analyze_rectification, generate_asc_quiz, calc_confidence）
- 发现并修复一个 syntax error：`analyze_synastry` prompt 里 `"这段关系的能量自然倾向"` 的内引号是 ASCII `"`，用 `\"` 转义修复

**Task 2** — `astrology_api/app/rag/planets.py` 重构完毕
- 添加 `from .prompt_registry import PROMPTS as _PROMPTS`
- 替换 43 行 f-string prompt 为 `_PROMPTS["interpret_planets"]["prompt_template"].format(...) + json_template + rag_context`

**Task 3** — `astrology_api/app/rag/transit.py` 重构完毕
- 替换 `analyze_transits` 的 f-string（预先计算 `planet_lines_str` / `aspect_lines_str`）
- 替换 `analyze_active_transits_full` 的两个 f-string（new-transits 分支 + summary-only 分支）

**Task 4（进行中）** — `chat.py` + `synastry.py` 已完成：
- `chat.py / generate()`：替换为 `_PROMPTS["generate"].format(context=context, query=query)`
- `chat.py / chat_with_chart()`：预计算 `transit_context_str` 字符串，用模板生成 base_prompt，再 append `query_suffix`（保留 query 嵌入，避免首轮对话丢失问题）
- `synastry.py`：预计算 `context_json = json.dumps(...)`, 替换为 `_PROMPTS["analyze_synastry"].format(...)`

### 待完成（Task 4 剩余）

`solar_return.py` 和 `rectification.py`：
- 实际 prompt 结构与注册表模板差异较大（不同占位符名称、内嵌 JSON schema）
- 计划：只添加 import，暂不替换 prompt（避免行为变化）；后续可单独迁移

**Task 4 完整收尾：**
- `solar_return.py` + `rectification.py`：添加 import（`from .prompt_registry import PROMPTS as _PROMPTS`），prompt 体保留原样（模板结构差异太大，后续单独迁移）

---

## Checkpoint — Task 5 进行中

**Task 5 — `db.py` 添加 4 张新表**

已完成：
- 在 `_CREATE_SR_CACHE` 之后添加 4 个 DDL 常量：`_CREATE_PROMPT_VERSIONS`, `_CREATE_PROMPT_LOGS`, `_CREATE_PROMPT_EVALUATIONS`, `_CREATE_USER_FEEDBACK`
- 将 4 个常量加入 `create_tables()` 的 for 循环列表

待完成：
- 语法验证 + commit

### 下一步

完成 Task 5 commit → Task 6：添加 `_turso_query` wrapper + `db_insert_prompt_version` 等 helper 函数。
