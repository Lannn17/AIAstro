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

新增 `_score_slow_planet_transits(natal, event_date, event_weight)`：

- **触发条件**：仅在 `ev.get('is_turning_point')` 为 True 时调用，且仅在 Phase 2 精扫阶段运行
- **检测范围**：土星 / 天王星 / 冥王星 / 木星 / 海王星 过本命**所有行星**（而非仅 ASC/MC）
- **容许度**：2°（严于普通行运的 5°）
- **相位**：合相(0°) / 对分(180°) / 四分(90°) / 三分(120°)
- **评分系数**：

| 慢星 | 系数 | 理由 |
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

在 `_score_candidate` 的事件循环开始前，调用一次 `_compute_chart_affinity(natal_chart_dict)` 返回：

```python
chart_affinity: dict[str, float]  # event_type → multiplier, range [0.6, 2.0]
```

### 2.2 三层激活计算

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

### 2.3 关键行星表（EVENT_KEY_PLANETS）

| 事件类型 | 关键行星 |
|---|---|
| marriage / new_relationship | Venus, Moon, Jupiter |
| divorce / breakup | Saturn, Pluto, Mars |
| career_up / business_start | Sun, Jupiter, Mars |
| career_down / business_end | Saturn, Pluto |
| career_change | Uranus, Jupiter |
| childbirth | Moon, Jupiter, Sun |
| bereavement_* | Saturn, Pluto |
| serious_illness / accident | Mars, Saturn, Pluto |
| relocation_international | Jupiter, Uranus |
| financial_gain / inheritance | Venus, Jupiter |
| financial_loss / bankruptcy | Saturn, Pluto |
| spiritual_awakening | Neptune, Pluto, Uranus |
| other | （空，affinity 保持 1.0）|

### 2.4 最终评分公式

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

基于三个候选分数的**变异系数（CV = σ / μ）**：

| CV 范围 | 标签 | 含义 |
|---|---|---|
| CV ≥ 0.3 | 高 | Top1 明显领先，推荐可信 |
| 0.15 ≤ CV < 0.3 | 中 | 候选间有差距，需结合问卷 |
| CV < 0.15 | 低 | 三者接近，建议补充事件 |

### 3.2 证据强度指标

```
evidence_score = Σ(event.weight × event.precision_weight) / N_events
```

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
