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

- 推盘逻辑优化: 增加星盘计算层,差异化确定事件权重赋值

- 📋 合盘 Phase 2：House Overlays（行星落入对方宫位分析）、合盘量化兼容度评分
- 📋 二次推运实现
- 📋 太阳回归实现
- 📋 校正系统 v1.3+（更多技法、评分权重调优）
- 📋 RAG 质量持续优化（基于 analytics 数据反馈）
- 📋 行星解读缓存策略优化
- 允许用户输入职业身份,使AI输出的分析结果更具体
- 增加验证数据集检验优化当前推盘模型算法
    - Ver1 先导入10条数据

---

## 代码清理（待决策）

> 以下为代码审查中发现的疑似冗余代码，暂未删除，待确认后处理。

- 📋 **遗留构建脚本**：`build_gemini_index.py`、`build_gemini_demo_index.py` — 早期用于构建 FAISS 索引，当前已切换至 Qdrant，可能已无用
- 📋 **stub 功能路由**：`progression_router.py`、`return_router.py`、`direction_router.py` — 对应前端 stub 页面，后端路由已注册但前端未接入，等待功能实现或决定是否保留
- 📋 **text_search.py 中未被导入的函数**：`get_sign_interpretation()`、`get_transit_interpretation()`、`get_natal_chart_interpretations()` — 当前无任何地方导入使用，可考虑删除
- 📋 **磁盘缓存模块** `app/core/cache.py` — 仅被 stub 功能路由间接使用，若 stub 路由移除则整个模块变为死代码
- 📋 **`/api/interpret` GET 端点**（`interpret_router.py`）— 使用旧版 TF-IDF 搜索，非 RAG，前端可能未调用

---

## 已知问题
- 校对分析RAG分析遗留问题(引用未拆分,未出现RAG引用分析模块)
- 不确定分钟(但确定小时)的情况,调盘界面里不好选择