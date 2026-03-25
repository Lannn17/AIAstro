# AIAstro — 待办事项

> 只记录未完成的内容。完成后移入 CHANGELOG.md，从此处删除。

---

## Stub 页面（路由已建，功能未实现）

- 🔨 合盘 Synastry（`/synastry`）— 开发中
- 🚧 推运 Progressions（`/progressions`）
- 🚧 太阳回归 Solar Return（`/solar-return`）
- 🚧 方向法 Directions（`/directions`）

---

## 候选功能（待排期）

- 📋 合盘 Phase 2：House Overlays（行星落入对方宫位分析）、合盘量化兼容度评分
- 📋 二次推运实现
- 📋 太阳回归实现
- 📋 校正系统 v1.3+（更多技法、评分权重调优）
- 📋 RAG 质量持续优化（基于 analytics 数据反馈）
- 📋 行星解读缓存策略优化
- 允许用户输入职业身份,使AI输出的分析结果更具体

---

## 已知问题

- 改综合星盘分析的标签生成逻辑(现在没有生成的具体规则逻辑,全靠AI生成)
- 手机端UI系统显示不美化(跨行显示名词,阅读体验差)
- 调盘功能无法模糊输入重大事件,修改为允许模糊输入(模糊到年份),但根据具体情况设置不同权重
- 已登录星盘数据允许修改(complete, need to be tested)