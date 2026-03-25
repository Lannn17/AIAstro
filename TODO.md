# AIAstro — 开发进度跟踪

> 每次对话结束后同步更新。格式：✅ 已完成 / 🚧 开发中 / 📋 待规划 / ❌ 已取消

---

## 当前版本：v0.7.0

---

## 已完成功能

### 核心功能
- ✅ 本命盘计算 + SVG 星盘图（Kerykeion）
- ✅ 行星表 + 宫位系统说明
- ✅ 地点搜索（Nominatim）
- ✅ 星盘保存 / 加载 / 删除（需登录）
- ✅ 多语言 UI（zh / ja / en / pt / es / fr / de）

### 认证与用户
- ✅ JWT 登录 + 访客模式
- ✅ 切换登录状态后前端界面完整清除（sessionKey remount）
- ✅ 访客星盘待审核队列 + 后台审核通过

### 行运分析
- ✅ 行运盘计算
- ✅ AI 行运解读（Gemini，含缓存）
- ✅ 访客切换到行运 Tab 后可选"当前星盘（未保存）"（ChartSessionContext）

### 占星对话（RAG）
- ✅ RAG 检索（Qdrant + multilingual-e5-small）+ Gemini 生成
- ✅ 已保存星盘加载后对话不再 500
- ✅ 引用检测修复（camelCase 书名正确拆分匹配）
- ✅ 对话来源引用展示（RAG 效果表）

### RAG 质量分析
- ✅ `query_analytics` 表（query_hash、label、max_rag_score、any_cited）
- ✅ 查询自动分类（7 类，Gemini temperature=0）
- ✅ 异步写入（不阻塞对话响应）
- ✅ 后端 `/api/admin/analytics` + `/api/admin/analytics/report`
- ✅ 前端 `/admin` 页面（隐藏路由，书签收藏访问）：数据表 + AI 分析报告

### 出生时间校正
- ✅ 校正系统 v1.0（基础评分）
- ✅ v1.1（主限法 Primary Directions + 版本化策略）
- ✅ v1.2（完整 12 宫事件映射 + 细粒度事件类型）
- ✅ 引导式事件向导（分域步骤 + 转折点选择）

### 部署
- ✅ HuggingFace Spaces 云部署（`lannn17-astro.hf.space`）
- ✅ 每次代码改动立即 commit + 推两端（origin + hf）
- ✅ SPA 直接 URL 访问修复（catch-all 路由，支持 /admin 等路径直接打开）

### Bug 修复（本次 debug 轮）
- ✅ 访客切换 Tab 后返回星盘页结果保留（sessionChart 恢复）
- ✅ 访客转登录后界面正确清空（isGuest 守卫）
- ✅ 行运下拉框早期记录显示 undefined 日期（label fallback）

---

## Stub 页面（已建路由，尚未实现）

- 🚧 合盘 Synastry（`/synastry`）
- 🚧 推运 Progressions（`/progressions`）
- 🚧 太阳回归 Solar Return（`/solar-return`）
- 🚧 方向法 Directions（`/directions`）

---

## 待规划 / 候选功能

_以下为潜在方向，尚未确认优先级：_

- 📋 合盘实现（双盘叠加 SVG + 相位解读）
- 📋 二次推运实现
- 📋 太阳回归实现
- 📋 校正系统 v1.3+（更多技法、评分权重调优）
- 📋 RAG 质量持续优化（基于 analytics 数据反馈）
- 📋 行星解读缓存策略优化

---

## 已知问题 / 待优化

- 🔧 修改综合星盘分析的标签生成逻辑

---

## 维护规则

- 每次对话确认新任务后，将其加入"待规划"或直接标记为"开发中"
- 功能完成并 push 后立即改为 ✅
- Stub 页面开始实现时从 🚧 移到对应分类
