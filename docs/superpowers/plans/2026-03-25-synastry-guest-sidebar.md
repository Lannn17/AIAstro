# 合盘功能 + 访客侧边栏重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整合盘功能（双轮SVG + 跨盘相位表 + RAG AI解读），同时重构访客侧边栏以支持会话内多盘管理。

**Architecture:** ChartSessionContext 从单条升级为列表，访客侧边栏显示会话盘列表；后端扩展 synastry 相位计算（ASC/MC接触+方向性+double whammy）并新增 RAG 合盘解读端点；前端 Synastry.jsx 完全重写，支持从已保存/会话盘选择或手动输入。

**Tech Stack:** FastAPI, Kerykeion, Qdrant RAG, Gemini, React/Vite, pytest+TestClient

---

## 文件变更总览

| 文件 | 操作 | 说明 |
|---|---|---|
| `astrology_api/app/core/calculations.py` | 修改 | `get_synastry_aspects_data` 加 ASC/MC 接触、方向性、double whammy |
| `astrology_api/app/schemas/models.py` | 修改 | `AspectData` 加 `direction`、`double_whammy` 字段 |
| `astrology_api/app/rag.py` | 修改 | 新增 `analyze_synastry` 函数 |
| `astrology_api/app/api/interpret_router.py` | 修改 | 新增 `POST /api/interpret/synastry` 端点 |
| `astrology_api/tests/test_api.py` | 修改 | 新增合盘相关测试 |
| `frontend/src/contexts/ChartSessionContext.jsx` | 修改 | 单条 → 列表，新增方法 |
| `frontend/src/App.jsx` | 修改 | AppInner 中监听 sessionKey，登出/切换时清空会话盘 |
| `frontend/src/pages/NatalChart.jsx` | 修改 | 适配新 context；侧边栏条件渲染；计算后 addSessionChart |
| `frontend/src/pages/Transits.jsx` | 修改 | 下拉框和 handleSelectChart 全部改为 sessionCharts[] |
| `frontend/src/components/GuestSessionList.jsx` | 新增 | 访客侧边栏子组件 |
| `frontend/src/pages/Synastry.jsx` | 重写 | 完整合盘 UI |

---

## Task 1: 扩展合盘相位计算（后端）

**Files:**
- Modify: `astrology_api/app/core/calculations.py` (函数 `get_synastry_aspects_data`, 约 421 行起)
- Modify: `astrology_api/app/schemas/models.py` (class `AspectData`, 约 160 行)

- [ ] **Step 1: 在 `AspectData` schema 中添加新字段**

在 `astrology_api/app/schemas/models.py` 的 `AspectData` 类中加入：
```python
direction: Optional[str] = Field(None, description="p1_to_p2 or p2_to_p1")
double_whammy: bool = Field(False, description="True if reciprocal aspect exists")
```

- [ ] **Step 2: 重写 `get_synastry_aspects_data`**

替换 `astrology_api/app/core/calculations.py` 中的 `get_synastry_aspects_data` 函数：

```python
def get_synastry_aspects_data(subject1: AstrologicalSubject, subject2: AstrologicalSubject, language: str = "zh") -> List[AspectData]:
    """
    计算两张本命盘之间的跨盘相位。
    包含：行星×行星、行星×对方ASC/MC。
    每条相位带方向性（p1_to_p2 / p2_to_p1）和 double whammy 标记。
    """
    planet_attrs = [
        'sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn',
        'uranus', 'neptune', 'pluto', 'mean_node', 'chiron'
    ]
    # ASC/MC 作为接受点（不作为主动点）
    sensitive_points = {
        'first_house': 'Ascendant',
        'tenth_house': 'Midheaven',
    }
    aspect_configs = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}
    orbs = {"Conjunction": 8, "Opposition": 8, "Trine": 6, "Square": 6, "Sextile": 4}

    def _calc_aspects(attribs_a, subject_a, name_a,
                      attribs_b, subject_b, name_b,
                      direction: str) -> list:
        """计算 A 中各点对 B 中各点的单向相位列表"""
        results = []
        for p1_attr in attribs_a:
            p1 = getattr(subject_a, p1_attr, None)
            if p1 is None:
                continue
            for p2_attr in attribs_b:
                p2 = getattr(subject_b, p2_attr, None)
                if p2 is None:
                    continue
                diff = abs(p1.abs_pos - p2.abs_pos)
                if diff > 180:
                    diff = 360 - diff
                for asp_name, asp_angle in aspect_configs.items():
                    orb = abs(diff - asp_angle)
                    if orb <= orbs[asp_name]:
                        results.append({
                            "p1_attr": p1_attr, "p1_name": p1_attr,
                            "p1_pos": p1.abs_pos,
                            "p2_attr": p2_attr, "p2_name": p2_attr,
                            "p2_pos": p2.abs_pos,
                            "aspect": asp_name, "orbit": round(orb, 4),
                            "direction": direction,
                        })
                        break
        return results

    # 行星 × 行星（双向）
    raw_p1p2 = _calc_aspects(planet_attrs, subject1, "chart1",
                              planet_attrs, subject2, "chart2", "p1_to_p2")
    raw_p2p1 = _calc_aspects(planet_attrs, subject2, "chart2",
                              planet_attrs, subject1, "chart1", "p2_to_p1")

    # 行星 × 对方 ASC/MC（甲行星 → 乙ASC/MC；乙行星 → 甲ASC/MC）
    sp_attrs = list(sensitive_points.keys())
    raw_p1sp2 = _calc_aspects(planet_attrs, subject1, "chart1",
                               sp_attrs, subject2, "chart2", "p1_to_p2")
    raw_p2sp1 = _calc_aspects(planet_attrs, subject2, "chart2",
                               sp_attrs, subject1, "chart1", "p2_to_p1")

    all_raw = raw_p1p2 + raw_p2p1 + raw_p1sp2 + raw_p2sp1

    # Double whammy 检测：同一对行星在双向均有同类相位
    seen_pairs: dict[tuple, str] = {}
    for r in all_raw:
        key = (frozenset([r["p1_attr"], r["p2_attr"]]), r["aspect"])
        seen_pairs[key] = seen_pairs.get(key, "") + r["direction"] + ","
    dw_keys = {k for k, v in seen_pairs.items() if "p1_to_p2" in v and "p2_to_p1" in v}

    aspects = []
    for r in all_raw:
        key = (frozenset([r["p1_attr"], r["p2_attr"]]), r["aspect"])
        p1_display = sensitive_points.get(r["p1_attr"], r["p1_attr"].replace("_", " ").title())
        p2_display = sensitive_points.get(r["p2_attr"], r["p2_attr"].replace("_", " ").title())
        # p1_owner / p2_owner 表示哪张盘拥有该行星（"chart1" 或 "chart2"）
        p1_owner = "chart1" if r["direction"] == "p1_to_p2" else "chart2"
        p2_owner = "chart2" if r["direction"] == "p1_to_p2" else "chart1"
        asp_angle = aspect_configs[r["aspect"]]
        aspects.append(AspectData(
            p1_name=p1_display,
            p2_name=p2_display,
            p1_owner=p1_owner,
            p2_owner=p2_owner,
            aspect=r["aspect"],
            aspect_degrees=float(asp_angle),
            orbit=r["orbit"],
            diff=round(abs(r["p1_pos"] - r["p2_pos"]), 4),
            applying=False,  # 两张本命盘均固定，无入/出相之分
            direction=r["direction"],
            double_whammy=(key in dw_keys),
        ))

    # 按容许度排序
    aspects.sort(key=lambda a: a.orbit)
    return aspects
```

- [ ] **Step 3: 写测试**

在 `astrology_api/tests/test_api.py` 末尾添加：

```python
MARIE_CURIE_DATA = {
    "name": "Marie Curie",
    "year": 1867, "month": 11, "day": 7,
    "hour": 12, "minute": 0,
    "longitude": 21.01, "latitude": 52.23,
    "tz_str": "Europe/Warsaw",
    "house_system": "Placidus",
    "language": "zh",
}

def test_synastry_returns_aspects():
    payload = {
        "chart1": EINSTEIN_DATA,
        "chart2": MARIE_CURIE_DATA,
        "language": "zh",
        "include_interpretations": False,
    }
    res = client.post("/api/synastry", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "aspects" in data
    assert len(data["aspects"]) > 0

def test_synastry_aspects_have_direction():
    payload = {
        "chart1": EINSTEIN_DATA,
        "chart2": MARIE_CURIE_DATA,
        "language": "zh",
        "include_interpretations": False,
    }
    res = client.post("/api/synastry", json=payload)
    data = res.json()
    directions = {a["direction"] for a in data["aspects"] if a.get("direction")}
    assert directions  # 至少有一个方向标注

def test_synastry_aspects_sorted_by_orbit():
    payload = {
        "chart1": EINSTEIN_DATA,
        "chart2": MARIE_CURIE_DATA,
        "language": "zh",
        "include_interpretations": False,
    }
    res = client.post("/api/synastry", json=payload)
    orbits = [a["orbit"] for a in res.json()["aspects"]]
    assert orbits == sorted(orbits)
```

- [ ] **Step 4: 运行测试**

```bash
cd astrology_api
pytest tests/test_api.py::test_synastry_returns_aspects tests/test_api.py::test_synastry_aspects_have_direction tests/test_api.py::test_synastry_aspects_sorted_by_orbit -v
```

预期：3 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add astrology_api/app/core/calculations.py astrology_api/app/schemas/models.py astrology_api/tests/test_api.py
git commit -m "feat(synastry): add ASC/MC contacts, direction, double whammy to aspect calculation"
```

---

## Task 2: 合盘 RAG AI 解读端点（后端）

**Files:**
- Modify: `astrology_api/app/rag.py` (在文件末尾新增函数)
- Modify: `astrology_api/app/api/interpret_router.py` (新增端点)

- [ ] **Step 1: 在 `rag.py` 末尾新增 `analyze_synastry`**

```python
# ── 合盘解读 ───────────────────────────────────────────────────────

def analyze_synastry(
    chart1_summary: dict,
    chart2_summary: dict,
    aspects: list[dict],
) -> dict:
    """
    合盘 RAG 解读：检索占星书籍相关段落 + Gemini 生成关系分析。
    返回 {answer, sources, index_used}
    """
    _load()

    # 取最紧密的 Top5 相位构造检索 query
    tight = sorted(aspects, key=lambda a: a.get("orbit", 99))[:5]
    desc_parts = []
    for a in tight:
        desc_parts.append(f"synastry {a.get('p1_name','')} {a.get('aspect','')} {a.get('p2_name','')}")
    query = ", ".join(desc_parts) if desc_parts else "synastry compatibility aspects"

    chunks = retrieve(query, k=5)

    name1 = chart1_summary.get("name", "甲")
    name2 = chart2_summary.get("name", "乙")

    # 相位列表文字
    aspect_lines = []
    for a in aspects[:20]:  # 最多展示20条避免 prompt 过长
        dw = " ★" if a.get("double_whammy") else ""
        direction = "→" if a.get("direction") == "p1_to_p2" else "←"
        aspect_lines.append(
            f"  {name1} {direction} {name2}  {a.get('p1_name','')} "
            f"{a.get('aspect','')} {a.get('p2_name','')}  容许度{a.get('orbit',0):.1f}°{dw}"
        )

    rag_section = ""
    if chunks:
        parts = [
            f"[参考{i} · {_clean_source_name(c['source'])}]\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        rag_section = (
            "\n\n---\n以下是检索到的占星书籍参考片段，若与合盘主题相关可引用（注明书名），不相关可忽略：\n\n"
            + "\n\n".join(parts)
        )

    prompt = f"""合盘分析：{name1} × {name2}

【跨盘相位】（按容许度排序，★ 表示双向命中 double whammy）
{chr(10).join(aspect_lines) or '（无相位数据）'}

---
请根据以上合盘相位，从以下四个维度给出综合分析：
1. 情感连结（最强的正面相位体现了怎样的情感共鸣？）
2. 沟通方式（双方沟通和理解的特点，水星/第三宫相关相位）
3. 摩擦点（刑/对分 + 土星/火星接触带来的挑战）
4. 整体兼容度（综合评估这段关系的基调与潜力）{rag_section}"""

    response = client.models.generate_content(
        model=GENERATE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT_UNIFIED,
            temperature=0.5,
        ),
    )

    finish = response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN"
    if finish != "STOP":
        print(f"[RAG] analyze_synastry finish_reason={finish}")

    sources = _detect_citations(response.text, chunks) if chunks else []
    return {
        "answer": response.text,
        "sources": sources,
        "index_used": _index_source,
    }
```

- [ ] **Step 2: 在 `interpret_router.py` 末尾新增端点**

注意：`hashlib`、`asyncio`、`List`、`Dict` 在该文件顶部已存在，**不要重复导入**。直接追加以下内容：

```python
class SynastryInterpretRequest(BaseModel):
    chart1_summary: Dict[str, Any]   # {name, ...} 用于 prompt 中称呼
    chart2_summary: Dict[str, Any]
    aspects: List[Dict[str, Any]]    # 来自 /api/synastry 返回的 aspects 列表


@router.post("/interpret/synastry")
async def interpret_synastry(body: SynastryInterpretRequest):
    """合盘 RAG 解读：Qdrant 检索 + Gemini 生成关系分析，写入 query_analytics。"""
    try:
        from ..rag import analyze_synastry
        result = analyze_synastry(
            chart1_summary=body.chart1_summary,
            chart2_summary=body.chart2_summary,
            aspects=body.aspects,
        )
        # 异步写入 analytics（不阻塞响应），复用已有的 _log_chat_analytics
        query = " ".join(
            f"{a.get('p1_name','')} {a.get('aspect','')} {a.get('p2_name','')}"
            for a in body.aspects[:5]
        )
        asyncio.create_task(_log_chat_analytics(query, result))
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synastry interpretation error: {e}")
```

- [ ] **Step 3: 用 curl 手动验证端点可访问**

```bash
cd astrology_api
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
# 新终端：
curl -s -X POST http://127.0.0.1:8001/api/interpret/synastry \
  -H "Content-Type: application/json" \
  -d '{"chart1_summary":{"name":"甲"},"chart2_summary":{"name":"乙"},"aspects":[{"p1_name":"Sun","aspect":"Conjunction","p2_name":"Moon","orbit":1.2,"double_whammy":false,"direction":"p1_to_p2"}]}' | python -m json.tool
```

预期：返回含 `answer`、`sources`、`index_used` 的 JSON

- [ ] **Step 4: Commit**

```bash
git add astrology_api/app/rag.py astrology_api/app/api/interpret_router.py
git commit -m "feat(synastry): add RAG synastry interpretation endpoint with analytics logging"
```

---

## Task 3: 升级 ChartSessionContext（前端）

**Files:**
- Modify: `frontend/src/contexts/ChartSessionContext.jsx`

- [ ] **Step 1: 重写 ChartSessionContext**

```jsx
import { createContext, useContext, useState, useCallback } from 'react'

const ChartSessionContext = createContext(null)

export function ChartSessionProvider({ children }) {
  // 会话星盘列表：[{ id, name, chartData, formData, svgData, locationName }]
  const [sessionCharts, setSessionCharts] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)

  const addSessionChart = useCallback((chart) => {
    const id = chart.id || `session-${Date.now()}`
    const entry = { ...chart, id }
    setSessionCharts(prev => {
      // 如果同名已存在则替换，否则追加
      const exists = prev.findIndex(c => c.name === entry.name)
      if (exists >= 0) {
        const next = [...prev]
        next[exists] = entry
        return next
      }
      return [...prev, entry]
    })
    setCurrentSessionId(id)
    return id
  }, [])

  const clearSessionCharts = useCallback(() => {
    setSessionCharts([])
    setCurrentSessionId(null)
  }, [])

  const currentSessionChart = sessionCharts.find(c => c.id === currentSessionId)
    ?? sessionCharts[0]
    ?? null

  return (
    <ChartSessionContext.Provider value={{
      sessionCharts,
      currentSessionId,
      currentSessionChart,   // 向后兼容：替代原 sessionChart
      addSessionChart,
      setCurrentSessionId,
      clearSessionCharts,
    }}>
      {children}
    </ChartSessionContext.Provider>
  )
}

export function useChartSession() {
  return useContext(ChartSessionContext)
}
```

- [ ] **Step 2: 确认 App.jsx 中的 Provider 包裹位置不需要修改**

检查 `frontend/src/App.jsx` 中 `<ChartSessionProvider>` 的位置，确认它仍然包裹整个应用。无需修改。

- [ ] **Step 3: 在 App.jsx 的 `AppInner` 中监听 sessionKey，登出/切换账号时清空会话盘**

`sessionKey` 在 `AuthContext` 的 `login`、`logout`、`continueAsGuest` 中均会自增，是重置信号。

在 `frontend/src/App.jsx` 的 `AppInner` 函数中添加：
```js
// 已有：const { sessionKey } = useAuth()
// 新增：
const { clearSessionCharts } = useChartSession()
useEffect(() => {
  clearSessionCharts()
}, [sessionKey])  // eslint-disable-line react-hooks/exhaustive-deps
```

同时在文件顶部确认 `useChartSession` 已导入：
```js
import { useChartSession } from './contexts/ChartSessionContext'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/contexts/ChartSessionContext.jsx frontend/src/App.jsx
git commit -m "feat(context): upgrade ChartSessionContext to multi-chart session list"
```

---

## Task 4: 适配 NatalChart.jsx（前端）

**Files:**
- Modify: `frontend/src/pages/NatalChart.jsx`

- [ ] **Step 1: 更新 context 导入和解构**

找到（约第 86 行）：
```js
const { sessionChart, setSessionChart } = useChartSession()
```
替换为：
```js
const { currentSessionChart, addSessionChart } = useChartSession()
```

- [ ] **Step 2: 更新 session 恢复逻辑**

找到（约第 137-144 行）：
```js
if (isGuest && result === null && sessionChart) {
  setResult(sessionChart.chartData)
  setSvgContent(sessionChart.svgData || null)
  setLastFormData(sessionChart.formData)
  setLastLocationName(sessionChart.locationName)
}
```
替换为：
```js
if (isGuest && result === null && currentSessionChart) {
  setResult(currentSessionChart.chartData)
  setSvgContent(currentSessionChart.svgData || null)
  setLastFormData(currentSessionChart.formData)
  setLastLocationName(currentSessionChart.locationName)
}
```

- [ ] **Step 3: 计算完成后调用 addSessionChart**

找到（约第 240 行）：
```js
setSessionChart({ chartData: data, formData, locationName, svgData })
```
替换为：
```js
addSessionChart({ name: formData.name || '未命名', chartData: data, formData, locationName, svgData })
```

同样找到另一处 `setSessionChart`（第 292 行，加载已保存星盘时的逻辑），替换为：
```js
addSessionChart({ name: chart.name || '未命名', chartData, formData, locationName, svgData })
```
其中 `chart.name` 来自已保存星盘对象的 `name` 字段（DB 中即为出生姓名）。共有 **2 处** `setSessionChart` 需要替换，找到并全部改完即可。

- [ ] **Step 4: 更新侧边栏条件渲染**

找到（约第 645 行）：
```jsx
<div className="page-sidebar" style={{ display: isAuthenticated ? undefined : 'none' }}>
```
替换为：
```jsx
<div className="page-sidebar">
```

在侧边栏内部，将现有的已登录内容（待审核队列 + 已保存星盘列表）用条件包裹，并添加访客列表：
```jsx
{isAuthenticated ? (
  <>
    {/* 待审核队列（现有代码不变）*/}
    {/* 已保存星盘列表（现有代码不变）*/}
    {/* 当前盘保存按钮（现有代码不变）*/}
  </>
) : (
  <GuestSessionList />
)}
```

在文件顶部引入：
```js
import GuestSessionList from '../components/GuestSessionList'
```

- [ ] **Step 5: 手动测试**

启动后端和前端，验证：
1. 访客计算一张盘 → 侧边栏出现该星盘卡片
2. 切换到行运 Tab 再切回 → 数据未丢失
3. 已登录用户 → 侧边栏显示原有 DB 星盘列表，行为不变

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/NatalChart.jsx
git commit -m "feat(natal): adapt to new ChartSessionContext; show guest sidebar"
```

---

## Task 5: GuestSessionList 组件（前端）

**Files:**
- Create: `frontend/src/components/GuestSessionList.jsx`

- [ ] **Step 1: 创建组件**

```jsx
import { useChartSession } from '../contexts/ChartSessionContext'
import { useAuth } from '../contexts/AuthContext'

export default function GuestSessionList() {
  const { sessionCharts, currentSessionId, setCurrentSessionId } = useChartSession()
  const { setShowLoginModal } = useAuth()

  return (
    <div style={{
      backgroundColor: '#12122a',
      border: '1px solid #2a2a5a',
      borderRadius: '10px',
      overflow: 'hidden',
    }}>
      {/* 标题 */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid #2a2a5a',
        color: '#8888aa',
        fontSize: '0.75rem',
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
      }}>
        本次会话
      </div>

      {/* 星盘列表 */}
      <div style={{ padding: '8px' }}>
        {sessionCharts.length === 0 ? (
          <div style={{ color: '#3a3a6a', fontSize: '0.78rem', padding: '8px 6px' }}>
            暂无星盘，计算后自动显示
          </div>
        ) : (
          sessionCharts.map(c => (
            <div
              key={c.id}
              onClick={() => setCurrentSessionId(c.id)}
              style={{
                padding: '8px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
                backgroundColor: currentSessionId === c.id ? '#1e1e40' : 'transparent',
                color: currentSessionId === c.id ? '#c9a84c' : '#8888aa',
                fontSize: '0.82rem',
                marginBottom: '2px',
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => {
                if (currentSessionId !== c.id)
                  e.currentTarget.style.backgroundColor = '#16163a'
              }}
              onMouseLeave={e => {
                if (currentSessionId !== c.id)
                  e.currentTarget.style.backgroundColor = 'transparent'
              }}
            >
              {c.name || '未命名'}
            </div>
          ))
        )}
      </div>

      {/* 登录提示 */}
      <div style={{
        padding: '10px 14px',
        borderTop: '1px solid #2a2a5a',
        fontSize: '0.72rem',
        color: '#3a3a6a',
      }}>
        <span
          onClick={() => setShowLoginModal(true)}
          style={{ color: '#c9a84c', cursor: 'pointer', textDecoration: 'underline' }}
        >
          登录
        </span>
        {' '}后可永久保存星盘
        <div style={{ marginTop: '4px', color: '#2a2a4a' }}>刷新页面后数据将清除</div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 手动测试**

验证：
1. 访客计算两张不同名字的盘 → 侧边栏显示两张
2. 点击切换 → 当前盘高亮变色
3. 点击"登录" → 弹出登录弹窗

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/GuestSessionList.jsx
git commit -m "feat(guest): add GuestSessionList sidebar component"
```

---

## Task 6: 适配 Transits.jsx（前端）

**Files:**
- Modify: `frontend/src/pages/Transits.jsx`

- [ ] **Step 1: 更新 context 解构**

找到（约第 5 行）：
```js
const { sessionChart } = useChartSession()
```
替换为：
```js
const { sessionCharts } = useChartSession()
```

- [ ] **Step 2: 重写 `handleSelectChart`（第 79-103 行）**

旧代码用 `'__session__'` 哨兵值并读取单条 `sessionChart`。替换为支持多盘的版本：

```js
async function handleSelectChart(id) {
  setSelectedId(id)
  setResult(null)
  setError(null)
  if (!id) { setSelectedChart(null); return }

  // 会话盘：value 格式为 "session:<id>"
  if (id.startsWith('session:')) {
    const sessionId = id.slice('session:'.length)
    const sc = sessionCharts.find(c => String(c.id) === sessionId)
    if (!sc) { setSelectedChart(null); return }
    const f = sc.formData
    setSelectedChart({
      birth_year: f.year, birth_month: f.month, birth_day: f.day,
      birth_hour: f.hour, birth_minute: f.minute,
      latitude: f.latitude, longitude: f.longitude,
      tz_str: f.tz_str, house_system: f.house_system,
      language: f.language,
      chart_data: sc.chartData,
      location_name: sc.locationName,
    })
    return
  }

  // DB 星盘
  try {
    const headers = authHeaders()
    const r = await fetch(`${API_BASE}/api/charts/${id}`, { headers })
    if (r.ok) setSelectedChart(await r.json())
  } catch { setError('加载星盘失败') }
}
```

- [ ] **Step 3: 更新下拉框选项（约第 173-177 行）**

将旧的单条会话盘 `<option value="__session__">` 替换为遍历 `sessionCharts`：

```jsx
{sessionCharts.map(c => (
  <option key={c.id} value={`session:${c.id}`}>
    {c.name || c.formData?.name || '当前星盘'}（未保存）
  </option>
))}
```

- [ ] **Step 4: 更新空状态提示（第 185 行）**

将：
```jsx
{savedCharts.length === 0 && !sessionChart && (
```
替换为：
```jsx
{savedCharts.length === 0 && sessionCharts.length === 0 && (
```

同样，第 128 行的 `selectedId === '__session__' ? 0 : Number(selectedId)` 改为：
```js
chart_id: selectedId?.startsWith('session:') ? 0 : Number(selectedId),
```

- [ ] **Step 5: 手动测试**

访客计算两张盘后进入行运 Tab，验证下拉框同时显示两个会话盘选项，选择后可正常生成行运分析。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Transits.jsx
git commit -m "feat(transits): update session chart dropdown to support multi-chart session"
```

---

## Task 7: 重写 Synastry.jsx（前端）

**Files:**
- Modify: `frontend/src/pages/Synastry.jsx`

这是最大的单个任务。分步骤实现。

- [ ] **Step 1: 搭建页面骨架（两列输入，无逻辑）**

```jsx
import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useChartSession } from '../contexts/ChartSessionContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

// 空表单初始状态
const EMPTY_FORM = {
  name: '', year: '', month: '', day: '',
  hour: '', minute: '', latitude: '', longitude: '',
  tz_str: 'Asia/Shanghai', house_system: 'Placidus',
  locationName: '',
}

export default function Synastry() {
  const { isAuthenticated, authHeaders } = useAuth()
  const { sessionCharts } = useChartSession()

  // 每列：{ mode: 'select'|'manual', selectedId: null|string, formData: {...} }
  const [col1, setCol1] = useState({ mode: 'select', selectedId: null, formData: EMPTY_FORM })
  const [col2, setCol2] = useState({ mode: 'select', selectedId: null, formData: EMPTY_FORM })

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)   // { aspects, chart1_planets, chart2_planets }
  const [svgContent, setSvgContent] = useState(null)
  const [interpretation, setInterpretation] = useState(null)
  const [interpLoading, setInterpLoading] = useState(false)

  return (
    <div>
      <div className="mb-6">
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ♀♂ 合盘
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          比较两张星盘的相位关系与缘分分析
        </p>
      </div>

      {/* 两列输入区 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <ChartInputCol
          label="甲方" col={col1} setCol={setCol1}
          isAuthenticated={isAuthenticated}
          authHeaders={authHeaders}
          sessionCharts={sessionCharts}
        />
        <ChartInputCol
          label="乙方" col={col2} setCol={setCol2}
          isAuthenticated={isAuthenticated}
          authHeaders={authHeaders}
          sessionCharts={sessionCharts}
        />
      </div>

      {/* 计算按钮 */}
      {/* 结果区 */}
    </div>
  )
}
```

- [ ] **Step 2: 实现 `ChartInputCol` 子组件（选择/手动切换）**

```jsx
function ChartInputCol({ label, col, setCol, isAuthenticated, authHeaders, sessionCharts }) {
  const [savedCharts, setSavedCharts] = useState([])

  useEffect(() => {
    if (isAuthenticated) {
      fetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
        .then(r => r.ok ? r.json() : [])
        .then(setSavedCharts)
        .catch(() => {})
    }
  }, [isAuthenticated])

  const chartList = isAuthenticated ? savedCharts : sessionCharts

  function handleSelect(id) {
    const chart = chartList.find(c => String(c.id) === String(id))
    if (!chart) return
    const fd = isAuthenticated
      ? {
          name: chart.name || '',
          year: chart.birth_year, month: chart.birth_month, day: chart.birth_day,
          hour: chart.birth_hour, minute: chart.birth_minute,
          latitude: chart.latitude, longitude: chart.longitude,
          tz_str: chart.tz_str, house_system: chart.house_system || 'Placidus',
          locationName: chart.location_name || '',
        }
      : { ...chart.formData }
    setCol(prev => ({ ...prev, selectedId: id, formData: fd }))
  }

  return (
    <div style={{
      backgroundColor: '#12122a', border: '1px solid #2a2a5a',
      borderRadius: '10px', padding: '16px',
    }}>
      <div style={{ color: '#c9a84c', fontWeight: 600, marginBottom: '12px' }}>{label}</div>

      {/* 模式切换 Tab */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        {['select', 'manual'].map(m => (
          <button key={m}
            onClick={() => setCol(prev => ({ ...prev, mode: m }))}
            style={{
              padding: '4px 12px', borderRadius: '6px', fontSize: '0.78rem', cursor: 'pointer',
              backgroundColor: col.mode === m ? '#2a2a5a' : 'transparent',
              border: '1px solid #2a2a5a', color: col.mode === m ? '#c9a84c' : '#8888aa',
            }}
          >
            {m === 'select' ? (isAuthenticated ? '从已保存选择' : '从会话选择') : '手动填写'}
          </button>
        ))}
      </div>

      {col.mode === 'select' ? (
        <select
          value={col.selectedId || ''}
          onChange={e => handleSelect(e.target.value)}
          style={{
            width: '100%', padding: '8px', borderRadius: '6px',
            backgroundColor: '#0d0d22', border: '1px solid #2a2a5a',
            color: '#ccc', fontSize: '0.82rem',
          }}
        >
          <option value="">-- 选择星盘 --</option>
          {chartList.map(c => (
            <option key={c.id} value={c.id}>
              {c.label || c.name || c.formData?.name || '未命名'}
            </option>
          ))}
        </select>
      ) : (
        <SynastryManualForm formData={col.formData}
          onChange={fd => setCol(prev => ({ ...prev, formData: fd }))} />
      )}

      {/* 已选信息预览 */}
      {col.formData.name && (
        <div style={{ marginTop: '10px', color: '#8888aa', fontSize: '0.78rem' }}>
          {col.formData.name} · {col.formData.year}/{col.formData.month}/{col.formData.day}{' '}
          {String(col.formData.hour).padStart(2,'0')}:{String(col.formData.minute).padStart(2,'0')}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 实现 `SynastryManualForm` 子组件**

与本命盘表单字段一致（姓名、年月日、时分、经纬度、时区、宫位系统），复用同样的 input 样式。此处省略完整代码——与 `ChartForm` 组件的字段和样式保持一致即可（参考 `frontend/src/components/ChartForm.jsx` 或 NatalChart.jsx 中的表单实现）。

关键：onChange 回调把整个 formData 对象传给父组件。

- [ ] **Step 4: 实现计算逻辑**

判断两列是否就绪：
```js
function colReady(col) {
  const f = col.formData
  return f.name && f.year && f.month && f.day &&
    f.hour !== '' && f.minute !== '' &&
    f.latitude && f.longitude && f.tz_str
}
const canCalculate = colReady(col1) && colReady(col2)
```

计算按钮 onClick：
```js
async function handleCalculate() {
  setLoading(true)
  setResult(null)
  setSvgContent(null)
  setInterpretation(null)
  try {
    const makeChart = (col) => ({
      name: col.formData.name,
      year: Number(col.formData.year), month: Number(col.formData.month),
      day: Number(col.formData.day), hour: Number(col.formData.hour),
      minute: Number(col.formData.minute),
      latitude: Number(col.formData.latitude), longitude: Number(col.formData.longitude),
      tz_str: col.formData.tz_str, house_system: col.formData.house_system || 'Placidus',
      language: 'zh',
    })

    // 1. 合盘相位
    const syRes = await fetch(`${API_BASE}/api/synastry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chart1: makeChart(col1), chart2: makeChart(col2), language: 'zh' }),
    })
    const syData = await syRes.json()
    setResult(syData)

    // 2. 双轮 SVG（复用 /api/svg_chart，chart_type="transit"）
    const svgRes = await fetch(`${API_BASE}/api/svg_chart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        natal_chart: makeChart(col1),
        transit_chart: makeChart(col2),
        chart_type: 'transit',
        theme: 'dark', language: 'zh',
      }),
    })
    if (svgRes.ok) {
      setSvgContent(await svgRes.text())
    }
  } catch (e) {
    console.error(e)
  } finally {
    setLoading(false)
  }
}
```

- [ ] **Step 5: 实现结果展示**

**SVG 双轮图：**
```jsx
{svgContent && (
  <div style={{ marginTop: '24px' }}
    dangerouslySetInnerHTML={{ __html: svgContent }} />
)}
```

**相位表：**
```jsx
{result?.aspects?.length > 0 && (
  <div style={{ marginTop: '24px' }}>
    <h3 style={{ color: '#c9a84c', marginBottom: '12px' }}>跨盘相位</h3>
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
      <thead>
        <tr style={{ color: '#8888aa', borderBottom: '1px solid #2a2a5a' }}>
          <th style={{ textAlign: 'left', padding: '6px' }}>方向</th>
          <th style={{ textAlign: 'left', padding: '6px' }}>甲行星</th>
          <th style={{ textAlign: 'center', padding: '6px' }}>相位</th>
          <th style={{ textAlign: 'left', padding: '6px' }}>乙行星</th>
          <th style={{ textAlign: 'right', padding: '6px' }}>容许度</th>
        </tr>
      </thead>
      <tbody>
        {result.aspects.map((a, i) => (
          <tr key={i} style={{
            borderBottom: '1px solid #1a1a3a',
            color: a.double_whammy ? '#c9a84c' : '#ccc',
          }}>
            <td style={{ padding: '6px' }}>
              {a.direction === 'p1_to_p2' ? '甲→乙' : '乙→甲'}
            </td>
            <td style={{ padding: '6px' }}>{a.p1_name}</td>
            <td style={{ padding: '6px', textAlign: 'center' }}>{a.aspect}</td>
            <td style={{ padding: '6px' }}>{a.p2_name}</td>
            <td style={{ padding: '6px', textAlign: 'right' }}>
              {a.orbit.toFixed(1)}°{a.double_whammy ? ' ★' : ''}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
```

**AI 解读区：**
```jsx
{result && (
  <div style={{ marginTop: '24px' }}>
    <button
      onClick={handleInterpret}
      disabled={interpLoading}
      style={{
        padding: '8px 20px', borderRadius: '8px', cursor: 'pointer',
        backgroundColor: '#2a2a5a', border: '1px solid #4a4a8a',
        color: '#c9a84c', fontSize: '0.85rem',
      }}
    >
      {interpLoading ? '生成中…' : '生成 AI 解读'}
    </button>
    {interpretation && (
      <div style={{ marginTop: '16px', color: '#ccc', lineHeight: 1.7, fontSize: '0.88rem' }}>
        {/* 使用 ReactMarkdown 或 dangerouslySetInnerHTML 渲染 Markdown */}
        <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
          {interpretation.answer}
        </pre>
      </div>
    )}
  </div>
)}
```

**AI 解读按钮 handler：**
```js
async function handleInterpret() {
  setInterpLoading(true)
  try {
    const res = await fetch(`${API_BASE}/api/interpret/synastry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chart1_summary: { name: col1.formData.name },
        chart2_summary: { name: col2.formData.name },
        aspects: result.aspects,
      }),
    })
    setInterpretation(await res.json())
  } catch (e) {
    console.error(e)
  } finally {
    setInterpLoading(false)
  }
}
```

- [ ] **Step 6: 手动测试清单**

1. 访客：选择"从会话选择" → 下拉框显示已计算的会话盘
2. 已登录：选择"从已保存选择" → 显示 DB 中的星盘
3. 手动填写两张盘 → 点击"计算合盘" → SVG 双轮图出现
4. 相位表按容许度排序，double whammy 相位金色高亮
5. 点击"生成 AI 解读" → 显示四维度分析

- [ ] **Step 7: Commit + Push**

```bash
git add frontend/src/pages/Synastry.jsx
git commit -m "feat(synastry): full synastry page with dual input, aspect table, SVG, and RAG interpretation"
git push origin main && git push hf main
```

---

## 最终验证

完成所有 Task 后，请依次测试：

```
1. [访客] 星盘Tab → 计算"甲"的盘 → 再次填写"乙"的信息计算
   预期：侧边栏出现两个人名卡片

2. [访客] 切换到合盘Tab → 两列"从会话选择"下拉框均显示甲和乙
   预期：分别选择后显示姓名+日期预览

3. [任意用户] 手动填写两列 → 计算合盘
   预期：双轮SVG + 相位表（带方向标注）

4. [任意用户] 相位表中找一条 ★ 相位
   预期：金色显示，表示双向命中

5. [任意用户] 点击"生成 AI 解读"
   预期：情感连结/沟通方式/摩擦点/整体兼容度四段分析

6. [已登录] 侧边栏显示 DB 星盘，行为与之前完全一致
```
