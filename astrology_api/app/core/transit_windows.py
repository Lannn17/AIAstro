"""
transit_windows.py — 行运时间窗口计算器（精选逻辑 v2）

选取逻辑综合四种方法：
  1. 按行星速度分级设置容许度（外行星最宽，内行星最紧）
  2. 只保留 5 个主要相位；六分相用收紧容许度（×0.65）
  3. 优先级打分：外行星过境个人星 > 社会星过境个人星 > …
  4. 只取优先级最高的前 MAX_RESULTS 个行运
  主题聚合（叠加验证）由 AI prompt 处理，此处标注 category 字段辅助。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from .calculations import create_astrological_subject
from ..interpretations.translations import translate_planet

logger = logging.getLogger(__name__)

# ── 行星分类 ─────────────────────────────────────────────────────

_OUTER  = {"uranus", "neptune", "pluto"}
_SOCIAL = {"jupiter", "saturn"}
_INNER  = {"sun", "mercury", "venus", "mars"}

# 本命个人星（被行运激活意义最大）
_PERSONAL_NATAL = {"sun", "moon", "mercury", "venus", "mars"}
_SOCIAL_NATAL   = {"jupiter", "saturn"}
_OUTER_NATAL    = {"uranus", "neptune", "pluto"}

TRANSIT_PLANETS = list(_OUTER) + list(_SOCIAL) + list(_INNER)
NATAL_POINTS    = list(_PERSONAL_NATAL) + list(_SOCIAL_NATAL) + list(_OUTER_NATAL)

# ── 变量容许度（度）——按行星速度分级 ────────────────────────────

_BASE_ORB: dict[str, float] = {
    "sun":     1.5,
    "mercury": 1.5,
    "venus":   1.5,
    "mars":    2.0,
    "jupiter": 2.5,
    "saturn":  2.5,
    "uranus":  4.0,
    "neptune": 4.0,
    "pluto":   4.0,
}

# ── 主要相位 + 容许度系数 ────────────────────────────────────────
# 六分相用 ×0.65 收紧（只在相位极精确时才显示）

_ASPECTS: dict[str, tuple[float, float]] = {
    "Conjunction": (0,   1.00),
    "Opposition":  (180, 1.00),
    "Square":      (90,  1.00),
    "Trine":       (120, 1.00),
    "Sextile":     (60,  0.65),
}

# 最终展示的行运上限（按优先级取前 N 个）
MAX_RESULTS = 8

# 逆行复过检测窗口（天）
_RETRO_LOOKAHEAD = 120

# 扫描步长（天）——越慢的行星步长越大
_PLANET_STEP: dict[str, int] = {
    "sun": 1, "mercury": 1, "venus": 1, "mars": 2,
    "jupiter": 5, "saturn": 7,
    "uranus": 14, "neptune": 14, "pluto": 14,
}


# ── 优先级打分 ────────────────────────────────────────────────────

def _priority(t_attr: str, n_attr: str, aspect: str) -> int:
    """
    打分标准（满分 14）：
      行运行星权重：外行星 6 / 社会星 4 / 内行星 2
      本命行星权重：个人星 4 / 社会星 2 / 外行星 1
      相位权重    ：合/对/刑 2 / 三分 1 / 六分 0
    """
    p = 0
    if t_attr in _OUTER:   p += 6
    elif t_attr in _SOCIAL: p += 4
    else:                   p += 2

    if n_attr in _PERSONAL_NATAL: p += 4
    elif n_attr in _SOCIAL_NATAL:  p += 2
    else:                          p += 1

    if aspect in ("Conjunction", "Opposition", "Square"): p += 2
    elif aspect == "Trine":                                p += 1
    return p


def _category(t_attr: str, n_attr: str) -> str:
    """为 AI prompt 提供人类可读的分类标签。"""
    t_label = "外行星" if t_attr in _OUTER else ("社会星" if t_attr in _SOCIAL else "内行星")
    n_label = "个人星" if n_attr in _PERSONAL_NATAL else ("社会星" if n_attr in _SOCIAL_NATAL else "外行星")
    return f"{t_label}过境{n_label}"


# ── 核心计算工具 ──────────────────────────────────────────────────

def _calc_orb(long1: float, long2: float, aspect_angle: float) -> float:
    diff = abs(long1 - long2) % 360
    if diff > 180:
        diff = 360 - diff
    return abs(diff - aspect_angle)


def _subject_at(d: date, natal_data: dict):
    return create_astrological_subject(
        name="t",
        year=d.year, month=d.month, day=d.day,
        hour=12, minute=0,
        longitude=natal_data["longitude"],
        latitude=natal_data["latitude"],
        tz_str=natal_data["tz_str"],
        house_system=natal_data.get("house_system", "Placidus"),
    )


def _find_exit(natal_long, aspect_angle, planet_attr, natal_data, anchor, orb_threshold):
    """向未来扫描，返回相位最后一天仍在容许度内的日期。"""
    step = _PLANET_STEP.get(planet_attr, 7)
    prev, current = anchor, anchor
    for _ in range(500 // step + 2):
        current = current + timedelta(days=step)
        try:
            p = getattr(_subject_at(current, natal_data), planet_attr, None)
        except Exception:
            break
        if p is None or _calc_orb(p.abs_pos, natal_long, aspect_angle) > orb_threshold:
            break
        prev = current
    lo, hi = prev, current
    for _ in range(10):
        if (hi - lo).days <= 1:
            break
        mid = lo + timedelta(days=(hi - lo).days // 2)
        try:
            p = getattr(_subject_at(mid, natal_data), planet_attr, None)
        except Exception:
            break
        if p and _calc_orb(p.abs_pos, natal_long, aspect_angle) <= orb_threshold:
            lo = mid
        else:
            hi = mid
    return lo


def _find_entry(natal_long, aspect_angle, planet_attr, natal_data, anchor, orb_threshold):
    """向过去扫描，返回相位最早进入容许度的日期。"""
    step = _PLANET_STEP.get(planet_attr, 7)
    prev, current = anchor, anchor
    for _ in range(500 // step + 2):
        current = current - timedelta(days=step)
        try:
            p = getattr(_subject_at(current, natal_data), planet_attr, None)
        except Exception:
            break
        if p is None or _calc_orb(p.abs_pos, natal_long, aspect_angle) > orb_threshold:
            break
        prev = current
    lo, hi = current, prev
    for _ in range(10):
        if (hi - lo).days <= 1:
            break
        mid = lo + timedelta(days=(hi - lo).days // 2)
        try:
            p = getattr(_subject_at(mid, natal_data), planet_attr, None)
        except Exception:
            break
        if p and _calc_orb(p.abs_pos, natal_long, aspect_angle) <= orb_threshold:
            hi = mid
        else:
            lo = mid
    return hi


def _find_exact(natal_long, aspect_angle, planet_attr, natal_data, start, end):
    span = (end - start).days
    step = max(1, span // 60)
    best_date, best_orb = start, float("inf")
    d = start
    while d <= end:
        try:
            p = getattr(_subject_at(d, natal_data), planet_attr, None)
            if p:
                orb = _calc_orb(p.abs_pos, natal_long, aspect_angle)
                if orb < best_orb:
                    best_orb, best_date = orb, d
        except Exception:
            pass
        d += timedelta(days=step)
    return best_date


# ── 主函数 ───────────────────────────────────────────────────────

def get_active_transits(
    natal_data: dict,
    query_date: date,
    language: str = "zh",
) -> list[dict]:
    """
    计算 query_date 当天的活跃行运相位，应用精选逻辑后返回最多 MAX_RESULTS 条。

    natal_data 需包含：
        year, month, day, hour, minute, latitude, longitude, tz_str, house_system
    """
    natal_subj   = create_astrological_subject(
        name="natal",
        year=natal_data["year"], month=natal_data["month"], day=natal_data["day"],
        hour=natal_data["hour"], minute=natal_data["minute"],
        longitude=natal_data["longitude"], latitude=natal_data["latitude"],
        tz_str=natal_data["tz_str"],
        house_system=natal_data.get("house_system", "Placidus"),
    )
    transit_now  = _subject_at(query_date, natal_data)
    transit_next = _subject_at(query_date + timedelta(days=1), natal_data)

    candidates: list[dict] = []

    for t_attr in TRANSIT_PLANETS:
        t_now = getattr(transit_now, t_attr, None)
        if t_now is None:
            continue
        t_nxt  = getattr(transit_next, t_attr, None)
        base_orb = _BASE_ORB.get(t_attr, 2.0)

        for n_attr in NATAL_POINTS:
            n_planet = getattr(natal_subj, n_attr, None)
            if n_planet is None:
                continue
            natal_long = float(n_planet.abs_pos)

            for aspect_name, (aspect_angle, orb_mul) in _ASPECTS.items():
                effective_orb = base_orb * orb_mul
                orb = _calc_orb(float(t_now.abs_pos), natal_long, aspect_angle)
                if orb > effective_orb:
                    continue

                # 入/出相
                applying = False
                if t_nxt:
                    applying = _calc_orb(float(t_nxt.abs_pos), natal_long, aspect_angle) < orb

                # 时间窗口
                entry = _find_entry(natal_long, aspect_angle, t_attr, natal_data, query_date, effective_orb)
                exit_ = _find_exit(natal_long, aspect_angle, t_attr, natal_data, query_date, effective_orb)

                # 逆行复过检测
                pass_count, retrograde_cycle, final_exit = 1, False, exit_
                for off in range(3, _RETRO_LOOKAHEAD + 1, 3):
                    check_d = exit_ + timedelta(days=off)
                    try:
                        p_c = getattr(_subject_at(check_d, natal_data), t_attr, None)
                    except Exception:
                        break
                    if p_c and _calc_orb(float(p_c.abs_pos), natal_long, aspect_angle) <= effective_orb:
                        pass_count += 1
                        retrograde_cycle = True
                        final_exit = _find_exit(natal_long, aspect_angle, t_attr, natal_data, check_d, effective_orb)
                        break

                exact = _find_exact(natal_long, aspect_angle, t_attr, natal_data, entry, final_exit)

                candidates.append({
                    "key":               f"{t_attr}_{aspect_name.lower()}_{n_attr}",
                    "transit_planet":    t_now.name,
                    "transit_planet_zh": translate_planet(t_now.name, language),
                    "natal_planet":      n_planet.name,
                    "natal_planet_zh":   translate_planet(n_planet.name, language),
                    "aspect":            aspect_name,
                    "current_orb":       round(orb, 2),
                    "effective_orb":     round(effective_orb, 2),
                    "applying":          applying,
                    "start_date":        entry.isoformat(),
                    "exact_date":        exact.isoformat(),
                    "end_date":          final_exit.isoformat(),
                    "retrograde_cycle":  retrograde_cycle,
                    "pass_count":        pass_count,
                    "priority":          _priority(t_attr, n_attr, aspect_name),
                    "category":          _category(t_attr, n_attr),
                })

    # 按优先级降序、容许度升序排列，取前 MAX_RESULTS
    candidates.sort(key=lambda x: (-x["priority"], x["current_orb"]))
    results = candidates[:MAX_RESULTS]

    logger.info(
        f"[transit_windows] {query_date}: {len(candidates)} candidates → "
        f"showing top {len(results)}"
    )
    return results
