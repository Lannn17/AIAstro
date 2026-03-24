"""
出生时间校对：两阶段自适应扫描

Phase1: 全天/大范围 → 每20分钟取一个候选（≤72个）→ 行运打分 → 取Top 25%
Phase2: 对Top候选 ±20分钟细扫，每4分钟一个 → 行运+推运联合打分
最终返回 Top3（去重：相差<30分钟视为同一候选）
"""
from datetime import date, timedelta
from kerykeion import AstrologicalSubject, TransitsTimeRangeFactory

ACTIVE_POINTS = [
    'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
    'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
    'Ascendant', 'Medium_Coeli',
]

# 事件类型权重倍率
EVENT_TYPE_WEIGHT = {
    'marriage':    1.5,
    'divorce':     1.2,
    'career_up':   1.3,
    'career_down': 1.2,
    'bereavement': 1.0,
    'illness':     1.0,
    'relocation':  0.8,
    'accident':    1.1,
    'other':       1.0,
}


def _score_transits(natal: AstrologicalSubject,
                    event_subj: AstrologicalSubject,
                    event_weight: float) -> float:
    """行运打分：事件当天行运命中本命 ASC/MC 的相位得分"""
    factory = TransitsTimeRangeFactory(natal, [event_subj], active_points=ACTIVE_POINTS)
    moments = factory.get_transit_moments()
    score = 0.0
    for t in moments.transits:
        for a in t.aspects:
            if a.p2_name in ('Ascendant', 'Medium_Coeli') and a.orbit < 5:
                score += (5 - a.orbit) * event_weight
    return score


def _score_solar_arc(natal: AstrologicalSubject,
                     birth_date: date,
                     event_date: date,
                     event_weight: float) -> float:
    """太阳弧方向打分：SA-ASC 命中本命行星（容许度 1.5°，权重高于行运）"""
    try:
        years = (event_date - birth_date).days / 365.25
        sa_asc = (natal.first_house.abs_pos + years) % 360
        planet_attrs = ['sun', 'moon', 'mercury', 'venus', 'mars',
                        'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
        score = 0.0
        for attr in planet_attrs:
            if not hasattr(natal, attr):
                continue
            p = getattr(natal, attr)
            if p is None:
                continue
            diff = abs(sa_asc - p.abs_pos)
            if diff > 180:
                diff = 360 - diff
            for target in (0, 180, 90, 120, 60):
                orbit = abs(diff - target)
                if orbit <= 1.5:
                    score += (1.5 - orbit) * 4.0 * event_weight
                    break
        return score
    except Exception:
        return 0.0


def _score_progressions(natal: AstrologicalSubject,
                        birth_date: date,
                        event_date: date,
                        h: int, m: int,
                        lat: float, lng: float, tz_str: str,
                        event_weight: float) -> float:
    """二次推运打分：推运盘命中本命 ASC/MC 的相位得分（权重加倍）"""
    delta_days = (event_date - birth_date).days
    prog_date = birth_date + timedelta(days=delta_days / 365.25)
    try:
        prog = AstrologicalSubject(
            'prog',
            prog_date.year, prog_date.month, prog_date.day,
            h, m, lng=lng, lat=lat, tz_str=tz_str,
        )
        factory = TransitsTimeRangeFactory(natal, [prog], active_points=ACTIVE_POINTS)
        moments = factory.get_transit_moments()
        score = 0.0
        for t in moments.transits:
            for a in t.aspects:
                if a.p2_name in ('Ascendant', 'Medium_Coeli') and a.orbit < 3:
                    score += (3 - a.orbit) * 2.0 * event_weight
        return score
    except Exception:
        return 0.0


def _score_candidate(h: int, m: int,
                     birth_year: int, birth_month: int, birth_day: int,
                     lat: float, lng: float, tz_str: str,
                     events: list[dict],
                     include_progressions: bool = False) -> float:
    """对一个候选出生时间打综合分"""
    try:
        natal = AstrologicalSubject(
            'natal', birth_year, birth_month, birth_day,
            h, m, lng=lng, lat=lat, tz_str=tz_str,
        )
    except Exception:
        return 0.0

    birth_date = date(birth_year, birth_month, birth_day)
    total = 0.0
    for ev in events:
        ev_date = date(ev['year'], ev['month'], ev['day'])
        ew = ev.get('weight', 1.0) * EVENT_TYPE_WEIGHT.get(ev.get('event_type', 'other'), 1.0)
        try:
            ev_subj = AstrologicalSubject(
                'ev', ev_date.year, ev_date.month, ev_date.day,
                12, 0, lng=lng, lat=lat, tz_str=tz_str,
            )
            total += _score_transits(natal, ev_subj, ew)
        except Exception:
            pass
        if include_progressions:
            total += _score_progressions(natal, birth_date, ev_date, h, m, lat, lng, tz_str, ew)
        total += _score_solar_arc(natal, birth_date, ev_date, ew)
    return total


def _get_asc_sign(h: int, m: int,
                  birth_year: int, birth_month: int, birth_day: int,
                  lat: float, lng: float, tz_str: str) -> str:
    """返回候选时间的上升星座英文名"""
    try:
        subj = AstrologicalSubject(
            'n', birth_year, birth_month, birth_day,
            h, m, lng=lng, lat=lat, tz_str=tz_str,
        )
        return subj.first_house.sign
    except Exception:
        return ''


def rectify_birth_time(
    birth_year: int, birth_month: int, birth_day: int,
    lat: float, lng: float, tz_str: str,
    events: list[dict],
    approx_hour: int | None = None,
    approx_minute: int | None = None,
    time_range_hours: float | None = None,
) -> list[dict]:
    """
    两阶段自适应扫描，返回 Top3 候选。
    返回格式: [{hour, minute, score, asc_sign}, ...]
    """
    # ── 确定扫描范围 ──
    if approx_hour is not None and time_range_hours is not None:
        center = approx_hour * 60 + (approx_minute or 0)
        half = int(time_range_hours * 60)
        start_min = max(0, center - half)
        end_min = min(1439, center + half)
    else:
        start_min, end_min = 0, 1439

    span = end_min - start_min
    # 小范围直接细扫，大范围两阶段
    if span <= 240:
        phase1_step = 4
        do_phase2 = False
    else:
        phase1_step = 20
        do_phase2 = True

    # ── Phase 1 ──
    phase1_mins = list(range(start_min, end_min + 1, phase1_step))
    scores: dict[int, float] = {}
    for total_min in phase1_mins:
        h, m = total_min // 60, total_min % 60
        scores[total_min] = _score_candidate(
            h, m, birth_year, birth_month, birth_day,
            lat, lng, tz_str, events,
            include_progressions=not do_phase2,
        )

    # ── Phase 2（仅粗扫时进行）──
    if do_phase2:
        sorted_p1 = sorted(scores.items(), key=lambda x: -x[1])
        top_n = max(5, len(sorted_p1) // 4)
        top_centers = [tm for tm, _ in sorted_p1[:top_n]]
        for center in top_centers:
            for offset in range(-20, 21, 4):
                total_min = max(0, min(1439, center + offset))
                if total_min not in scores:
                    h, m = total_min // 60, total_min % 60
                    scores[total_min] = _score_candidate(
                        h, m, birth_year, birth_month, birth_day,
                        lat, lng, tz_str, events,
                        include_progressions=True,
                    )

    # ── 取 Top3（去重：相差 < 30 分钟视为同一候选）──
    sorted_all = sorted(scores.items(), key=lambda x: -x[1])
    top3 = []
    selected_mins: list[int] = []
    for total_min, score in sorted_all:
        if any(abs(total_min - prev) < 30 for prev in selected_mins):
            continue
        h, m = total_min // 60, total_min % 60
        asc = _get_asc_sign(h, m, birth_year, birth_month, birth_day, lat, lng, tz_str)
        top3.append({'hour': h, 'minute': m, 'score': round(score, 2), 'asc_sign': asc})
        selected_mins.append(total_min)
        if len(top3) >= 3:
            break

    return top3
