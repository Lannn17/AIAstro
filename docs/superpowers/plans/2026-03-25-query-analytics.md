# Query Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收集占星对话的匿名查询统计，用于评估 RAG 检索质量，不存储原始文本，不关联用户身份。

**Architecture:** 每次 `/api/interpret/chat` 成功响应后，异步记录 `(query_hash, label, max_rag_score, any_cited)` 到新表 `query_analytics`。`label` 由 Gemini 自动分类（7类）。日志写入不阻塞主响应。

**Tech Stack:** Python / FastAPI / SQLite + Turso / google-genai (已有)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `astrology_api/app/db.py` | Modify | 新增表 DDL + `db_log_query_analytics()` |
| `astrology_api/app/rag.py` | Modify | 新增 `classify_query()` |
| `astrology_api/app/api/interpret_router.py` | Modify | 成功后异步触发日志写入 |

---

## Task 1: DB — 新增 `query_analytics` 表

**Files:**
- Modify: `astrology_api/app/db.py`

- [ ] **Step 1: 在 db.py 中添加建表 DDL**

在现有 `_CREATE_PLANET_CACHE` 常量之后添加：

```python
_CREATE_QUERY_ANALYTICS = """
CREATE TABLE IF NOT EXISTS query_analytics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash  TEXT    NOT NULL,
    label       TEXT    NOT NULL,
    max_rag_score REAL  NOT NULL,
    any_cited   INTEGER NOT NULL,
    created_at  TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""
```

- [ ] **Step 2: 注册到 `create_tables()`**

```python
def create_tables():
    for ddl in [_CREATE_TABLE, _CREATE_TRANSIT_CACHE, _CREATE_TRANSIT_OVERALL,
                _CREATE_PLANET_CACHE, _CREATE_QUERY_ANALYTICS]:   # ← 加这个
        ...
```

- [ ] **Step 3: 添加写入函数**

在文件末尾追加：

```python
# ── Query analytics ───────────────────────────────────────────────

def db_log_query_analytics(query_hash: str, label: str,
                           max_rag_score: float, any_cited: bool):
    sql = """
        INSERT INTO query_analytics (query_hash, label, max_rag_score, any_cited)
        VALUES (?, ?, ?, ?)
    """
    params = [query_hash, label, round(max_rag_score, 4), 1 if any_cited else 0]
    try:
        if USE_TURSO:
            _turso_exec(sql, params)
        else:
            _sqlite_write(sql, params)
    except Exception as e:
        print(f"[Analytics] log failed (non-fatal): {e}", flush=True)
```

- [ ] **Step 4: 手动验证建表**

启动后端，检查 `charts.db` 中是否出现 `query_analytics` 表：
```bash
sqlite3 astrology_api/charts.db ".tables"
# 期望输出包含: query_analytics
```

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/db.py
git commit -m "feat(analytics): add query_analytics table + db_log_query_analytics"
```

---

## Task 2: RAG — 添加 `classify_query()`

**Files:**
- Modify: `astrology_api/app/rag.py`

- [ ] **Step 1: 在 rag.py 中添加分类标签常量和函数**

在 `_index_source = "qdrant"` 之后添加：

```python
_QUERY_LABELS = (
    "planet_sign",   # 行星在某星座的解读
    "planet_house",  # 行星在某宫位的解读
    "aspect",        # 相位解读
    "life_area",     # 感情/事业/财运/健康等生活领域
    "psychological", # 性格/心理/行为模式
    "prediction",    # 运势预测/时机判断
    "other",         # 兜底
)

def classify_query(query: str) -> str:
    """用 Gemini 将占星问题分类为 7 个预定义标签之一。失败时返回 'other'。"""
    labels_str = " | ".join(_QUERY_LABELS)
    prompt = (
        f"占星问题：{query}\n\n"
        f"从以下标签中选一个最合适的，只输出标签本身，不要其他文字：\n{labels_str}"
    )
    try:
        resp = client.models.generate_content(
            model=GENERATE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )
        label = resp.text.strip().lower()
        return label if label in _QUERY_LABELS else "other"
    except Exception as e:
        print(f"[Analytics] classify_query failed: {e}", flush=True)
        return "other"
```

- [ ] **Step 2: 验证函数可调用（本地测试）**

在 Python REPL 中：
```python
import sys; sys.path.insert(0, "astrology_api")
from app.rag import classify_query
print(classify_query("我的上升天蝎说明什么"))   # 期望: planet_sign 或 psychological
print(classify_query("火星在第七宫对感情影响")) # 期望: planet_house 或 life_area
```

- [ ] **Step 3: Commit**

```bash
git add astrology_api/app/rag.py
git commit -m "feat(analytics): add classify_query() with 7-label Gemini classification"
```

---

## Task 3: Router — 成功后异步写入日志

**Files:**
- Modify: `astrology_api/app/api/interpret_router.py`

- [ ] **Step 1: 在成功响应后触发异步日志**

修改 `interpret_chat`，在 `return result` 之前添加异步任务：

```python
import hashlib
import asyncio

@router.post("/interpret/chat")
async def interpret_chat(body: ChatRequest):
    try:
        from ..rag import chat_with_chart, classify_query
        from ..db import db_log_query_analytics

        history = [{"role": m.role, "text": m.text} for m in body.history]
        result = chat_with_chart(body.query, body.chart_data, k=body.k,
                                 history=history, summary=body.summary)

        # 异步写入分析日志，不阻塞响应
        asyncio.create_task(_log_analytics(body.query, result))

        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[CHAT ERROR]\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}: {e}")


async def _log_analytics(query: str, result: dict):
    """非阻塞：分类 query 并写入 query_analytics 表。"""
    try:
        from ..rag import classify_query
        from ..db import db_log_query_analytics

        query_hash = hashlib.sha256(query.encode()).hexdigest()
        label = classify_query(query)
        sources = result.get("sources", [])
        max_score = max((s.get("score", 0.0) for s in sources), default=0.0)
        any_cited = any(s.get("cited", False) for s in sources)

        db_log_query_analytics(query_hash, label, max_score, any_cited)
        print(f"[Analytics] logged: label={label} score={max_score:.3f} cited={any_cited}", flush=True)
    except Exception as e:
        print(f"[Analytics] _log_analytics failed (non-fatal): {e}", flush=True)
```

- [ ] **Step 2: 验证日志写入（本地测试）**

发送一条聊天请求，后端控制台应出现：
```
[Analytics] logged: label=planet_house score=0.742 cited=True
```

查询数据库确认记录：
```bash
sqlite3 astrology_api/charts.db "SELECT * FROM query_analytics LIMIT 5;"
```

- [ ] **Step 3: Commit**

```bash
git add astrology_api/app/api/interpret_router.py
git commit -m "feat(analytics): async log query hash + label + rag scores after chat"
```

---

## 完整逻辑总结

```
用户发送聊天问题
    ↓
interpret_chat() 处理请求
    ↓
chat_with_chart() 执行：RAG检索 → Gemini生成 → 返回 {answer, sources}
    ↓
asyncio.create_task(_log_analytics())   ← 不阻塞响应
    ↓
前端立即收到回答
    ↓ (后台)
classify_query()  →  Gemini 返回标签（planet_house / psychological / ...）
    ↓
db_log_query_analytics(
    query_hash = SHA256(原始问题),   # 不存明文
    label      = "planet_house",
    max_rag_score = 0.742,           # 本次检索最高相似度
    any_cited  = True                # AI是否引用了书名
)
```

**评估用法：**
```sql
-- 哪类问题 RAG 表现最差（score < 0.6）
SELECT label, COUNT(*) as low_score_count
FROM query_analytics
WHERE max_rag_score < 0.6
GROUP BY label
ORDER BY low_score_count DESC;

-- 整体引用率趋势
SELECT label, AVG(max_rag_score) as avg_score, AVG(any_cited) as cite_rate
FROM query_analytics
GROUP BY label;
```
