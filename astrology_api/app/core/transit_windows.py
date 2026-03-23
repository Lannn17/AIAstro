"""
transit_windows.py — 行运时间窗口计算器

对每个活跃的行运相位，用二分法找到入相日期和出相日期，
并检测逆行复过（同一次逆行周期内的多次精确相位）。
使用 Kerykeion/Swiss Ephemeris 本地计算，无外部 API 调用。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from .calculations import create_astrological_subject
from ..interpretations.translations import translate_planet

logger = logging.getLogger(__name__)

# 行运行星（排除月亮：相位仅持续数小时，精确到日无意义）
TRANSIT_PLANETS = [
    "sun", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
]

# 本命参考点
NATAL_POINTS = [
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
]

# 相位角度（仅主要相位 + 梅花相）
ASPECT_ANGLES: dict[str, float] = {
    "Conjunction": 0,
    "Opposition":  180,
    "Trine":       120,
    "Square":      90,
    "Sextile":     60,
    "Quincunx":    150,
}

# 扫描步长（天）——越慢的行星步长越大
PLANET_STEP: dict[str, int] = {
    "sun": 1, "mercury": 1, "venus": 1, "mars": 2,
    "jupiter": 5, "saturn": 7,
    "uranus": 14, "neptune": 14, "pluto": 14,
}

# 逆行复过检测窗口（天）：覆盖所有内行星逆行周期
RETRO_LOOKAHEAD = 120


# ── 核心工具函数 ──────────────────────────────────────────────────

def _calc_orb(long1: float, long2: float, aspect_angle: float) -> float:
    diff = abs(long1 - long2) % 360
    if diff > 180:
        diff = 360 - diff
    return abs(diff - aspect_angle)


def _subject_at(d: date, natal_data: dict):
    """为指定日期创建行运 AstrologicalSubject（使用本命盘所在地点）。"""
    return create_astrological_subject(
        name="t",
        year=d.year, month=d.month, day=d.day,
        hour=12, minute=0,
        longitude=natal_data["longitude"],
        latitude=natal_data["latitude"],
        tz_str=natal_data["tz_str"],
        house_system=natal_data.get("house_system", "Placidus"),
    )


def _find_exit(
    natal_long: float, aspect_angle: float, planet_attr: str,
    natal_data: dict, anchor: date, orb_threshold: float,
) -> date:
    """从 anchor 向后（向未来）扫描，返回相位最后一天仍在容许度内的日期。"""
    step = PLANET_STEP.get(planet_attr, 7)
    prev = anchor
    current = anchor

    for _ in range(500 // step + 2):
        current = current + timedelta(days=step)
        try:
            subj = _subject_at(current, natal_data)
            p = getattr(subj, planet_attr, None)
        except Exception:
            break
        if p is None or _calc_orb(p.abs_pos, natal_long, aspect_angle) > orb_threshold:
            break
        prev = current

    # 二分法精确到天
    lo, hi = prev, current
    for _ in range(10):
        if (hi - lo).days <= 1:
            break
        mid = lo + timedelta(days=(hi - lo).days // 2)
        try:
            subj = _subject_at(mid, natal_data)
            p = getattr(subj, planet_attr, None)
        except Exception:
            break
        if p is None:
            break
        if _calc_orb(p.abs_pos, natal_long, aspect_angle) <= orb_threshold:
            lo = mid
        else:
            hi = mid
    return lo


def _find_entry(
    natal_long: float, aspect_angle: float, planet_attr: str,
    natal_data: dict, anchor: date, orb_threshold: float,
) -> date:
    """从 anchor 向前（向过去）扫描，返回相位最早进入容许度的日期。"""
    step = PLANET_STEP.get(planet_attr, 7)
    prev = anchor
    current = anchor

    for _ in range(500 // step + 2):
        current = current - timedelta(days=step)
        try:
            subj = _subject_at(current, natal_data)
            p = getattr(subj, planet_attr, None)
        except Exception:
            break
        if p is None or _calc_orb(p.abs_pos, natal_long, aspect_angle) > orb_threshold:
            break
        prev = current

    # 二分法：lo 在外（更早），hi 在内（更晚）
    lo, hi = current, prev
    for _ in range(10):
        if (hi - lo).days <= 1:
            break
        mid = lo + timedelta(days=(hi - lo).days // 2)
        try:
            subj = _subject_at(mid, natal_data)
            p = getattr(subj, planet_attr, None)
        except Exception:
            break
        if p is None:
            break
        if _calc_orb(p.abs_pos, natal_long, aspect_angle) <= orb_threshold:
            hi = mid   # 入相更早，hi 向左收
        else:
            lo = mid   # 入相更晚，lo 向右收
    return hi


def _find_exact(
    natal_long: float, aspect_angle: float, planet_attr: str,
    natal_data: dict, start: date, end: date,
) -> date:
    """在 [start, end] 内用步进扫描找容许度最小的日期（最精确相位日）。"""
    span = (end - start).days
    step = max(1, span // 60)
    best_date, best_orb = start, float("inf")
    d = start
    while d <= end:
        try:
            subj = _subject_at(d, natal_data)
            p = getattr(subj, planet_attr, None)
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
    orb_threshold: float = 1.0,
    language: str = "zh",
) -> list[dict]:
    """
    计算 query_date 当天所有活跃行运相位，并返回每个相位的时间窗口。

    natal_data 需包含：
        year, month, day, hour, minute, latitude, longitude, tz_str, house_system

    返回列表按当前容许度升序排列（越精确越靠前）。
    """
    # 构建本命盘 subject
    natal_subj = create_astrological_subject(
        name="natal",
        year=natal_data["year"], month=natal_data["month"], day=natal_data["day"],
        hour=natal_data["hour"], minute=natal_data["minute"],
        longitude=natal_data["longitude"], latitude=natal_data["latitude"],
        tz_str=natal_data["tz_str"],
        house_system=natal_data.get("house_system", "Placidus"),
    )

    # 构建当日及明日行运 subject（用于判断入/出相）
    transit_now  = _subject_at(query_date, natal_data)
    transit_next = _subject_at(query_date + timedelta(days=1), natal_data)

    results: list[dict] = []

    for t_attr in TRANSIT_PLANETS:
        t_now = getattr(transit_now, t_attr, None)
        if t_now is None:
            continue
        t_nxt = getattr(transit_next, t_attr, None)

        for n_attr in NATAL_POINTS:
            n_planet = getattr(natal_subj, n_attr, None)
            if n_planet is None:
                continue
            natal_long = float(n_planet.abs_pos)

            for aspect_name, aspect_angle in ASPECT_ANGLES.items():
                orb = _calc_orb(float(t_now.abs_pos), natal_long, aspect_angle)
                if orb > orb_threshold:
                    continue

                # 入/出相判断（容许度明天更小 → 入相）
                applying = False
                if t_nxt is not None:
                    orb_next = _calc_orb(float(t_nxt.abs_pos), natal_long, aspect_angle)
                    applying = orb_next < orb

                # 计算时间窗口
                entry = _find_entry(natal_long, aspect_angle, t_attr, natal_data, query_date, orb_threshold)
                exit_ = _find_exit(natal_long, aspect_angle, t_attr, natal_data, query_date, orb_threshold)

                # 逆行复过检测：在 exit_ 后 RETRO_LOOKAHEAD 天内每隔 3 天检查是否再次进入容许度
                pass_count = 1
                retrograde_cycle = False
                final_exit = exit_

                for off in range(3, RETRO_LOOKAHEAD + 1, 3):
                    check_d = exit_ + timedelta(days=off)
                    try:
                        subj_c = _subject_at(check_d, natal_data)
                        p_c = getattr(subj_c, t_attr, None)
                    except Exception:
                        break
                    if p_c and _calc_orb(float(p_c.abs_pos), natal_long, aspect_angle) <= orb_threshold:
                        pass_count += 1
                        retrograde_cycle = True
                        final_exit = _find_exit(natal_long, aspect_angle, t_attr, natal_data, check_d, orb_threshold)
                        break   # 只合并一次复过（三过点可延伸，暂取最大两窗口）

                # 精确相位日
                exact = _find_exact(natal_long, aspect_angle, t_attr, natal_data, entry, final_exit)

                results.append({
                    "key":               f"{t_attr}_{aspect_name.lower()}_{n_attr}",
                    "transit_planet":    t_now.name,
                    "transit_planet_zh": translate_planet(t_now.name, language),
                    "natal_planet":      n_planet.name,
                    "natal_planet_zh":   translate_planet(n_planet.name, language),
                    "aspect":            aspect_name,
                    "current_orb":       round(orb, 2),
                    "applying":          applying,
                    "start_date":        entry.isoformat(),
                    "exact_date":        exact.isoformat(),
                    "end_date":          final_exit.isoformat(),
                    "retrograde_cycle":  retrograde_cycle,
                    "pass_count":        pass_count,
                })

    results.sort(key=lambda x: x["current_orb"])
    logger.info(f"[transit_windows] {query_date}: found {len(results)} active aspects")
    return results
