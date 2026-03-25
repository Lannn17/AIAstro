# Admin Analytics Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/admin` 隐藏路由，已登录用户可查看 RAG 质量统计数据并一键生成 AI 分析报告。

**Architecture:** 后端新增 `admin_router.py`，提供两个鉴权接口（聚合数据 + AI报告生成）；前端新增 `Analytics.jsx` 页面，通过 `/admin` 路由访问，不出现在导航栏。

**Tech Stack:** FastAPI / SQLite+Turso / google-genai（已有）/ React + Vite（已有）

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `astrology_api/app/db.py` | Modify | 新增 `db_get_analytics_summary()` + `db_get_analytics_records()` |
| `astrology_api/app/api/admin_router.py` | Create | GET `/api/admin/analytics` + POST `/api/admin/analytics/report` |
| `astrology_api/main.py` | Modify | 注册 admin_router |
| `frontend/src/pages/Analytics.jsx` | Create | Admin 页面：报告 + 数据表格 |
| `frontend/src/App.jsx` | Modify | 新增 `/admin` 隐藏路由（不加入导航栏） |

---

## Task 1: DB — 新增两个读取函数

**Files:**
- Modify: `astrology_api/app/db.py`

- [ ] **Step 1: 在 db.py 末尾添加聚合查询函数**

```python
def db_get_analytics_summary() -> list[dict]:
    """按 label 聚合：count、avg_score、cite_rate。"""
    sql = """
        SELECT
            label,
            COUNT(*)              AS count,
            ROUND(AVG(max_rag_score), 3) AS avg_score,
            ROUND(AVG(any_cited), 3)     AS cite_rate
        FROM query_analytics
        GROUP BY label
        ORDER BY count DESC
    """
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql))
    return _sqlite_fetchall(sql)


def db_get_analytics_records(limit: int = 200) -> list[dict]:
    """最近 N 条原始记录（不含原始 query 文本）。"""
    sql = """
        SELECT id, label, max_rag_score, any_cited, created_at
        FROM query_analytics
        ORDER BY created_at DESC
        LIMIT ?
    """
    if USE_TURSO:
        return _to_dicts(_turso_exec(sql, [limit]))
    return _sqlite_fetchall(sql, [limit])
```

- [ ] **Step 2: 验证函数可调用（本地，无数据时返回空列表不报错）**

```bash
cd astrology_api
python -c "from app.db import db_get_analytics_summary, db_get_analytics_records; print(db_get_analytics_summary()); print(db_get_analytics_records())"
# 期望: [] []  （或实际数据行）
```

- [ ] **Step 3: Commit**

```bash
git add astrology_api/app/db.py
git commit -m "feat(admin): add db_get_analytics_summary and db_get_analytics_records"
```

---

## Task 2: 后端 — admin_router.py

**Files:**
- Create: `astrology_api/app/api/admin_router.py`

- [ ] **Step 1: 创建文件**

```python
from fastapi import APIRouter, HTTPException, Depends
from ..security import require_auth
from ..db import db_get_analytics_summary, db_get_analytics_records

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/analytics")
def get_analytics(_user: str = Depends(require_auth)):
    """返回 query_analytics 的聚合摘要 + 最近200条记录。"""
    return {
        "summary": db_get_analytics_summary(),
        "records": db_get_analytics_records(limit=200),
    }


@router.post("/analytics/report")
def generate_analytics_report(_user: str = Depends(require_auth)):
    """用 Gemini 生成 RAG 质量分析报告。"""
    summary = db_get_analytics_summary()
    if not summary:
        return {"report": "暂无数据，请在占星对话模块积累一些对话后再生成报告。"}
    try:
        from ..rag import client, GENERATE_MODEL
        from google.genai import types

        summary_text = "\n".join(
            f"- {r['label']}: {r['count']}条, 平均RAG分={r['avg_score']}, 引用率={r['cite_rate']}"
            for r in summary
        )
        total = sum(r["count"] for r in summary)
        low_score = [r for r in summary if r["avg_score"] < 0.6]

        prompt = f"""以下是占星对话系统的 RAG 检索质量统计数据（共 {total} 条对话）：

{summary_text}

说明：
- avg_score：向量检索相似度均值（0~1，越高说明书籍库与该类问题的匹配越好）
- cite_rate：AI 在回答中引用书籍的比例（越高说明检索结果对 AI 有帮助）

请生成一份简洁的中文分析报告，包含：
1. 整体 RAG 覆盖情况评估
2. 哪类问题检索效果最好 / 最差（重点分析 avg_score < 0.6 的类别）
3. 具体建议（应补充哪类占星书籍内容来改善弱项）
4. 一句话总结"""

        resp = client.models.generate_content(
            model=GENERATE_MODEL,
            contents=prompt,
        )
        return {"report": resp.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
```

- [ ] **Step 2: 在 main.py 注册路由**

找到现有路由注册区域，添加：

```python
from app.api.admin_router import router as admin_router
app.include_router(admin_router)
```

- [ ] **Step 3: 验证接口可访问**

启动后端，用已登录 token 访问：
```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8001/api/admin/analytics
# 期望: {"summary": [...], "records": [...]}
```

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/api/admin_router.py astrology_api/main.py
git commit -m "feat(admin): add /api/admin/analytics + /api/admin/analytics/report endpoints"
```

---

## Task 3: 前端 — Analytics.jsx

**Files:**
- Create: `frontend/src/pages/Analytics.jsx`

- [ ] **Step 1: 创建页面组件**

```jsx
import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export default function Analytics() {
  const { authHeaders, isAuthenticated } = useAuth()
  const [summary, setSummary] = useState([])
  const [records, setRecords] = useState([])
  const [report, setReport] = useState('')
  const [loadingData, setLoadingData] = useState(true)
  const [loadingReport, setLoadingReport] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!isAuthenticated) { setLoadingData(false); return }
    const headers = authHeaders()
    fetch(`${API_BASE}/api/admin/analytics`, { headers })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setSummary(d.summary); setRecords(d.records) })
      .catch(e => setError(`加载失败: ${e}`))
      .finally(() => setLoadingData(false))
  }, [isAuthenticated])

  async function handleGenerateReport() {
    setLoadingReport(true)
    setReport('')
    try {
      const res = await fetch(`${API_BASE}/api/admin/analytics/report`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) throw new Error(res.status)
      const d = await res.json()
      setReport(d.report)
    } catch (e) {
      setReport(`生成失败: ${e.message}`)
    } finally {
      setLoadingReport(false)
    }
  }

  if (!isAuthenticated) {
    return (
      <div style={{ color: '#8888aa', padding: '40px', textAlign: 'center' }}>
        请先登录
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 16px', color: '#c8c8e8' }}>
      <h1 style={{ color: '#c9a84c', fontSize: '1.3rem', marginBottom: '24px' }}>
        ✦ RAG 质量分析
      </h1>

      {/* 生成报告按钮 */}
      <button
        onClick={handleGenerateReport}
        disabled={loadingReport}
        style={{
          padding: '10px 24px', marginBottom: '24px',
          backgroundColor: loadingReport ? '#2a2a4a' : '#c9a84c',
          color: loadingReport ? '#8888aa' : '#0a0a1a',
          border: 'none', borderRadius: '8px',
          fontWeight: 600, fontSize: '0.95rem',
          cursor: loadingReport ? 'not-allowed' : 'pointer',
        }}
      >
        {loadingReport ? '生成中…' : '✦ 生成 AI 分析报告'}
      </button>

      {/* AI 报告 */}
      {report && (
        <div style={{
          backgroundColor: '#0d0d22', border: '1px solid #2a2a5a',
          borderRadius: '10px', padding: '20px', marginBottom: '32px',
          whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: '0.95rem',
        }}>
          {report}
        </div>
      )}

      {/* 聚合摘要表 */}
      {error && <div style={{ color: '#ff6666', marginBottom: '16px' }}>{error}</div>}
      {!loadingData && summary.length > 0 && (
        <>
          <h2 style={{ color: '#8888aa', fontSize: '0.9rem', marginBottom: '12px', letterSpacing: '0.1em' }}>
            各类问题 RAG 统计
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '32px', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2a5a', color: '#8888aa' }}>
                {['类型', '数量', '平均检索分', '书籍引用率'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summary.map(r => (
                <tr key={r.label} style={{ borderBottom: '1px solid #1a1a3a' }}>
                  <td style={{ padding: '8px 12px', color: '#c9a84c' }}>{r.label}</td>
                  <td style={{ padding: '8px 12px' }}>{r.count}</td>
                  <td style={{ padding: '8px 12px', color: r.avg_score < 0.6 ? '#ff8866' : '#88cc88' }}>
                    {r.avg_score.toFixed(3)}
                  </td>
                  <td style={{ padding: '8px 12px' }}>{(r.cite_rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* 原始记录表 */}
      {!loadingData && records.length > 0 && (
        <>
          <h2 style={{ color: '#8888aa', fontSize: '0.9rem', marginBottom: '12px', letterSpacing: '0.1em' }}>
            最近 {records.length} 条记录
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2a5a', color: '#8888aa' }}>
                {['#', '类型', 'RAG分', '引用', '时间'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 10px', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid #12122a' }}>
                  <td style={{ padding: '6px 10px', color: '#4a4a6a' }}>{r.id}</td>
                  <td style={{ padding: '6px 10px', color: '#c9a84c' }}>{r.label}</td>
                  <td style={{ padding: '6px 10px', color: r.max_rag_score < 0.6 ? '#ff8866' : '#88cc88' }}>
                    {r.max_rag_score.toFixed(3)}
                  </td>
                  <td style={{ padding: '6px 10px' }}>{r.any_cited ? '✓' : '—'}</td>
                  <td style={{ padding: '6px 10px', color: '#6666aa' }}>
                    {r.created_at?.slice(0, 16).replace('T', ' ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {!loadingData && summary.length === 0 && (
        <div style={{ color: '#6666aa', textAlign: 'center', padding: '40px' }}>
          暂无数据 — 在占星对话模块积累对话后再来查看
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Analytics.jsx
git commit -m "feat(admin): add Analytics page with summary table + AI report button"
```

---

## Task 4: 前端 — 注册路由

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: 导入并注册 `/admin` 路由**

在 `App.jsx` 顶部导入：
```jsx
import Analytics from './pages/Analytics'
```

在 `<Routes>` 内添加（不加入 `NAV_ITEMS`）：
```jsx
<Route path="/admin" element={<Analytics />} />
```

- [ ] **Step 2: 验证路由可访问**

启动前端，访问 `http://localhost:5173/admin`：
- 未登录 → 显示"请先登录"
- 已登录 → 显示页面（暂无数据时显示提示文字）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(admin): register hidden /admin route for analytics page"
```
