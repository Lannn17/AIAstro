# 合盘功能 + 访客侧边栏重构 — 设计文档

**日期：** 2026-03-25
**状态：** 已批准，待实现

---

## 目标

1. 实现合盘（Synastry）功能：双盘 SVG + 跨盘相位表（含 ASC/MC 接触、方向性、double whammy）+ RAG + Gemini AI 解读
2. 重构访客侧边栏：访客可在当次会话中管理多张已计算的星盘，用于合盘选择

---

## 一、ChartSessionContext 升级

### 现状
```js
sessionChart: { chartData, formData, svgData, locationName }  // 单条
```

### 升级后
```js
sessionCharts: [
  { id, name, chartData, formData, svgData, locationName }
]
currentSessionId: string | null
```

### 新增方法
| 方法 | 说明 |
|---|---|
| `addSessionChart(chart)` | 计算完成后自动加入列表，name 取自 `formData.name` |
| `setCurrentSessionId(id)` | 切换当前激活盘 |
| `clearSessionCharts()` | 登出或重置时清空 |

### 兼容性（需修改的现有读取点）
- `NatalChart.jsx`：恢复逻辑改为读取 `sessionCharts.find(c => c.id === currentSessionId)` 或列表第一条
- `Transits.jsx`：下拉框改为遍历 `sessionCharts[]`
- 已登录用户：session 列表继续存在于内存，但不显示在侧边栏（DB 列表优先）

---

## 二、访客侧边栏

### 逻辑变更
移除 `display: isAuthenticated ? undefined : 'none'`，侧边栏对所有用户可见。
根据 `isAuthenticated` 渲染不同子组件：
- 已登录 → `<SavedChartsList />`（现有逻辑不变）
- 访客 → `<GuestSessionList />`（新组件）

### GuestSessionList 规格
| 元素 | 说明 |
|---|---|
| 标题 | "本次会话" |
| 星盘卡片 | 显示人名（来自表单 name 字段），点击切换当前盘 |
| 操作 | 仅"加载"，无删除（刷新自然清空） |
| 保存区 | 灰色提示"登录后可永久保存" |
| 底部小字 | "刷新页面后数据将清除" |

### 数据隔离保证
- 访客 session 列表：纯 React 内存状态，不写 DB，不经过鉴权 API
- 已登录 DB 列表：`GET /api/charts`（Bearer token），不经过 ChartSessionContext
- 两者无交叉

---

## 三、合盘输入 UI（Synastry.jsx）

### 布局
两列并排（移动端竖向堆叠），每列代表一人。

### 每列输入方式（Tab 切换）
```
[ 从已有选择 ▼ ]  |  [ 手动填写 ]
```

| 用户类型 | "从已有选择" 数据源 |
|---|---|
| 已登录 | `GET /api/charts` 返回的 DB 星盘 |
| 访客 | `sessionCharts[]` 会话列表 |

- 选择后只读展示出生信息
- 手动填写：与本命盘表单字段相同（姓名/日期/时间/经纬度/时区/宫位系统）
- "计算合盘"按钮：两列均有有效数据后才可点击

---

## 四、合盘结果展示

### 4.1 双轮 SVG 图
- **新端点：** `POST /api/synastry_svg`
- 接受两组出生数据，返回双圈星盘 SVG（内圈=甲，外圈=乙）
- 使用 Kerykeion `KerykeionChartSVG` synastry 模式生成

### 4.2 跨盘相位表

**容许度标准（合盘专用）：**
| 相位 | 容许度 |
|---|---|
| 合相 / 对分 | 8° |
| 三分 / 刑 | 6° |
| 六分 | 4° |

**合盘专有逻辑：**
1. **ASC/MC 接触** — 一方行星与另一方 ASC/MC 的相位一并计算（不只看行星）
2. **方向性标注** — 每条相位标注"甲→乙"或"乙→甲"，因为同相位方向不同意义不同
3. **Double whammy 高亮** — 若同一组行星对在双向均有同类相位，标记显示

**表格列：** 方向 / 甲行星 / 相位符号 / 乙行星 / 容许度 / double whammy 标记

**排序：** 容许度从小到大（最紧密优先）

### 4.3 AI 综合解读（RAG + Gemini）

**端点：** `POST /api/interpret/synastry`

**流程（与现有行运/星盘解读一致）：**
1. 从跨盘相位中提取最紧密的 Top N 相位，构建检索 query（如 `"synastry Venus conjunct Mars, Sun opposition Moon"`）
2. Qdrant 检索相关书籍段落（k=5）
3. 检索结果 + 相位数据 + 两张盘信息送 Gemini 生成解读
4. 写入 `query_analytics` 做质量追踪

**输出结构：**
- 情感连结（最强正面相位解读）
- 沟通方式（水星/第三宫相关相位）
- 摩擦点（刑/对分 + Saturn/Mars 接触）
- 整体兼容度概述

**前端：** 默认折叠，"生成解读"按钮触发，带加载状态

---

## 五、后端变更汇总

| 端点 | 状态 | 说明 |
|---|---|---|
| `POST /api/synastry` | 已存在，需扩展 | 加入 ASC/MC 接触、方向性标注、double whammy 标记 |
| `POST /api/synastry_svg` | 新增 | 双轮 SVG 生成 |
| `POST /api/interpret/synastry` | 新增 | RAG + Gemini 合盘 AI 解读 |

---

## 六、前端文件变更汇总

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `contexts/ChartSessionContext.jsx` | 修改 | 单条 → 列表，新增方法 |
| `pages/NatalChart.jsx` | 修改 | 读取方式适配新 context；侧边栏渲染调整；计算后 addSessionChart |
| `pages/Transits.jsx` | 修改 | 下拉框改为遍历 sessionCharts[] |
| `pages/Synastry.jsx` | 重写 | 完整合盘 UI 实现 |
| `components/GuestSessionList.jsx` | 新增 | 访客侧边栏子组件 |

---

## 七、TODO（后续迭代）

- **House Overlays（行星落入对方宫位）** — 甲太阳落乙第七宫等，是传统合盘重要分析维度，留待 Phase 2
- **合盘评分** — 基于相位强度和性质的量化兼容度得分
