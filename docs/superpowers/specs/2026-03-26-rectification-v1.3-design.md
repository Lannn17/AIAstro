# 校正算法 v1.3 设计文档

**日期：** 2026-03-26
**版本：** v1.3
**文件：** `astrology_api/app/core/rectification.py`

---

## 背景

v1.2 算法在真实案例验证中出现两个问题：
1. 标记转折点后误差反而从 9 分钟扩大至 5 小时，转折点乘数过激且无上限
2. 事件类型权重为固定值，未利用本命盘数据动态调整

v1.3 同时解决这两个问题，并新增分数展示的分辨力 / 证据强度指标。

---

## Part 1：转折点权重修复

### 1.1 乘数归一化

| 情况 | v1.2 | v1.3 |
|---|---|---|
| 单个转折点 | ×2.0 | ×1.5 |
| N 个转折点（每个）| ×2.0（无上限）| `× max(1.1, 1.5 / √N)` |

归一化公式确保多个转折点不会集体炸裂评分，同时保留单个高权重事件的影响力。

### 1.2 慢星相位检测（新增函数）

新增 `_score_slow_planet_transits(natal, event_subj, event_weight)`：

- **参数**：`natal` = 候选出生时间的 `AstrologicalSubject`；`event_subj` = 事件日期构建的 `AstrologicalSubject`（与 `_score_transits` 一致，由调用方传入）
- **触发条件**：仅在 `ev.get('is_turning_point')` 为 True 时调用，且仅在 Phase 2 精扫阶段运行
- **检测范围**：`event_subj` 中土星 / 天王星 / 冥王星 / 木星 / 海王星 的位置，与 `natal` 中**所有行星**（日月水金火木土天海冥）形成相位
- **容许度**：2°（严于普通行运的 5°）
- **相位**：合相(0°) / 对分(180°) / 四分(90°) / 三分(120°)
- **评分系数**：

| 慢星（行运方） | 系数 | 理由 |
|---|---|---|
| 冥王星 | 3.5 | 深层转化 |
| 土星 | 3.0 | 人生结构重塑 |
| 天王星 | 2.5 | 突变 / 颠覆 |
| 海王星 | 1.5 | 解构 / 迷失 |
| 木星 | 1.5 | 扩张 / 机遇 |

评分公式：`score += (2.0 - orbit) × planet_coef × event_weight`

---

## Part 2：动态星盘赋权

### 2.1 预计算 chart_affinity

在 `_score_candidate` 的事件循环开始前，调用一次 `_compute_chart_affinity(natal)` 返回：

```python
chart_affinity: dict[str, float]  # event_type → multiplier, range [0.6, 2.0]
```

**参数**：`natal` 为已构建的 `AstrologicalSubject`（候选出生时间），与其他评分函数一致。不使用 JSON dict，因为三层计算需要直接访问行星位置属性（`natal.sun.house`、`natal.first_house.sign` 等）。`chart_affinity` 随候选时间变化（不同出生时间→不同宫位→不同动态权重），在每个候选的 Phase 2 评分中各计算一次。

### 2.2 宫主星映射（_SIGN_RULER）

使用传统 + 现代混合守护星：

```python
_SIGN_RULER = {
    "Aries": "Mars",    "Taurus": "Venus",   "Gemini": "Mercury",
    "Cancer": "Moon",   "Leo": "Sun",         "Virgo": "Mercury",
    "Libra": "Venus",   "Scorpio": "Pluto",   "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}
```

### 2.3 三层激活计算

对每个事件类型，遍历其 `EVENT_HOUSE_MAP` 的前两个关联宫位：

**层 1 — 关键行星落入关联宫位（+0.25 / 命中）**
- 每个事件类型定义关键行星表（`EVENT_KEY_PLANETS`）
- 若关键行星实际落在关联宫位 → +0.25
- 若非关键但重要行星（日 / 月 / 木 / 土）落在关联宫位 → +0.15

**层 2 — 宫主星落入角宫（+0.15）**
- 关联宫位的宫主星（基于宫头星座 → `_SIGN_RULER`）
- 若宫主星落在角宫（1 / 4 / 7 / 10）→ +0.15

**层 3 — 宫主星与关键行星有紧密相位（+0.10 / 命中）**
- 容许度 < 5° 的主要相位（合 / 对 / 四分 / 三分 / 六分）
- 宫主星与任一关键行星形成此类相位 → +0.10

**范围：** `clamp(0.6, 2.0)`，基础值 1.0

### 2.4 关键行星表（EVENT_KEY_PLANETS）

| 事件类型 | 关键行星 |
|---|---|
| marriage / new_relationship | Venus, Moon, Jupiter |
| divorce / breakup | Saturn, Pluto, Mars |
| career_up / business_start / retirement | Sun, Jupiter, Mars |
| career_down / business_end | Saturn, Pluto |
| career_change | Uranus, Jupiter |
| childbirth | Moon, Jupiter, Sun |
| bereavement_parent / bereavement_spouse / bereavement_child / bereavement_other / bereavement | Saturn, Pluto |
| serious_illness / mental_health_crisis / illness | Mars, Saturn, Pluto |
| accident / surgery | Mars, Uranus |
| relocation_international / study_abroad | Jupiter, Uranus |
| relocation_domestic / relocation | Moon, Saturn |
| financial_gain / inheritance / major_investment | Venus, Jupiter |
| financial_loss / bankruptcy | Saturn, Pluto |
| graduation / major_exam | Jupiter, Mercury |
| legal_win / legal_loss | Jupiter, Saturn |
| family_bond_change | Moon, Saturn |
| spiritual_awakening | Neptune, Pluto, Uranus |
| other（含所有未列出类型）| （空列表，affinity 保持基础值 1.0）|

### 2.5 最终评分公式

```
event_weight = user_weight
             × event_type_weight      # 现有 EVENT_TYPE_WEIGHT 表
             × chart_affinity         # 新增动态系数
             × precision_weight       # 现有模糊日期折扣
             × turning_point_mult     # 修正后转折点系数
```

---

## Part 3：分数展示

### 3.1 分辨力指标

主指标使用 **Top1-Top2 相对差距**，辅以三者变异系数作为二级信号：

```
gap_ratio = (top1_score - top2_score) / top1_score
```

| gap_ratio 范围 | 标签 | 含义 |
|---|---|---|
| ≥ 0.25 | 高 | Top1 明显领先，推荐可信 |
| 0.10 ≤ gap < 0.25 | 中 | 候选间有差距，需结合问卷 |
| < 0.10 | 低 | 三者接近，建议补充事件 |

注：只用 Top3 计算 CV 样本过少（N=3），不具统计代表性，改用 gap_ratio 更直接可靠。

### 3.2 证据强度指标

基于**原始事件列表**（`_expand_events` 展开前的事件，避免 precision_weight 被重复计入）：

```
evidence_score = Σ(raw_event.weight × precision_weight(raw_event)) / N_raw_events
```

其中 `precision_weight` = 1.0（有日期）/ 0.7（有月无日）/ 0.4（仅年份），与 `_PRECISION_WEIGHT` 一致。

| 范围 | 标签 |
|---|---|
| ≥ 1.5 | 强 |
| 0.8 ~ 1.5 | 中 |
| < 0.8 | 弱 |

UI 展示：在 Top3 结果区上方增加两行小字指标：
```
分辨力：高  ·  证据强度：中
```

---

## Part 4：版本注册

```python
"v1.3": {
    "transits":                    True,
    "solar_arc":                   True,
    "progressions":                True,
    "primary_directions":          True,
    "cusp_hits":                   True,
    "dynamic_chart_weights":       True,   # 新增
    "slow_planet_turning_points":  True,   # 新增
}
```

`STRATEGY_DESCRIPTIONS["v1.3"]`：
> "v1.2 基础上加入动态星盘赋权（行星宫位+宫主星+相位）、转折点权重归一化、慢星相位检测，及分辨力/证据强度展示"

**默认版本暂保持 v1.0**，待 v1.3 用真实案例验证后再升级。

---

## 不在本次范围内

- 前端版本选择器 UI 调整
- 历史校对结果对比
- 算法超参数（系数值）自动调优
