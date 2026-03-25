"""
出生时间校对：两阶段自适应扫描

Phase1: 全天/大范围 → 每20分钟取一个候选（≤72个）→ 快速评分（行运 + 太阳弧）
Phase2: 对Top候选 ±20分钟细扫，每4分钟一个 → 全量评分（加入慢速方法）
最终返回 Top3（去重：相差<30分钟视为同一候选）

版本策略：
  v1.0 — 基础版：行运 + 太阳弧 + 二次推运
  v1.1 — 加入初级推运（Primary Directions，pyswisseph 精确实现）
"""
from datetime import date, datetime, timedelta
import pytz
from kerykeion import AstrologicalSubject, TransitsTimeRangeFactory


# ── 版本策略字典 ──────────────────────────────────────────────────
# 每个版本声明启用哪些评分维度。
# 快速维度（transits / solar_arc）在 Phase1+2 均运行。
# 慢速维度（progressions / primary_directions）仅在 Phase2 运行。

SCORING_STRATEGIES: dict[str, dict] = {
    "v1.0": {
        "transits":           True,
        "solar_arc":          True,
        "progressions":       True,
        "primary_directions": False,
    },
    "v1.1": {
        "transits":           True,
        "solar_arc":          True,
        "progressions":       True,
        "primary_directions": True,
    },
}

STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "v1.0": "行运相位 + 太阳弧方向 + 二次推运",
    "v1.1": "v1.0 基础上加入初级推运（Primary Directions，Naibod 率，pyswisseph 精确计算）",
}

DEFAULT_VERSION = "v1.0"


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


# ── 评分函数 ──────────────────────────────────────────────────────

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
    """太阳弧方向打分：SA-ASC 命中本命行星（容许度 1.5°）"""
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


def _score_primary_directions(natal: AstrologicalSubject,
                               birth_year: int, birth_month: int, birth_day: int,
                               h: int, m: int,
                               lat: float, lng: float, tz_str: str,
                               event_date: date,
                               event_weight: float,
                               orb: float = 1.5) -> float:
    """
    初级推运（Primary Directions）打分 — v1.1 新增。
    使用 Naibod 率（0.9856°/年）在赤经上推进 ASC，
    通过 pyswisseph 精确换算回黄道经度后检查与本命行星的相位。
    对出生时间极敏感：差 10 分钟出生时间 ≈ Primary Arc 差约 2.5°。
    """
    try:
        import swisseph as swe

        # 1. 本命时刻 → UTC → 儒略日
        tz = pytz.timezone(tz_str)
        local_dt = datetime(birth_year, birth_month, birth_day, h, m)
        utc_dt = tz.localize(local_dt).astimezone(pytz.utc)
        natal_jd = swe.julday(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour + utc_dt.minute / 60.0,
        )

        # 2. Naibod 弧：0.9856°/年
        years = (event_date - date(birth_year, birth_month, birth_day)).days / 365.25
        arc = years * 0.9856

        # 3. 本命 RAMC（赤经中天）+ 推运弧 → 推运后 RAMC
        _, ascmc = swe.houses(natal_jd, lat, lng, b'P')
        directed_ramc = (ascmc[2] + arc) % 360   # ascmc[2] = ARMC

        # 4. 黄赤交角（真倾角）
        nut, _ = swe.calc_ut(natal_jd, swe.ECL_NUT, 0)
        obliquity = nut[0]

        # 5. 从推运 RAMC 精确求推运 ASC 的黄道经度
        _, dir_ascmc = swe.houses_armc(directed_ramc, lat, obliquity, b'P')
        directed_asc = dir_ascmc[0]

        # 6. 推运 ASC 与本命行星的相位得分
        planet_attrs = ['sun', 'moon', 'mercury', 'venus', 'mars',
                        'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
        aspects = {0: 5.0, 180: 3.5, 120: 2.5, 90: 2.0, 60: 1.5}
        score = 0.0
        for attr in planet_attrs:
            p = getattr(natal, attr, None)
            if p is None:
                continue
            diff = abs(directed_asc - p.abs_pos)
            if diff > 180:
                diff = 360 - diff
            for asp_angle, asp_weight in aspects.items():
                orbit = abs(diff - asp_angle)
                if orbit <= orb:
                    score += (orb - orbit) * asp_weight * event_weight
                    break   # 只取最近相位，避免重复计分
        return score
    except Exception:
        return 0.0


# ── 综合打分 ──────────────────────────────────────────────────────

def _score_candidate(h: int, m: int,
                     birth_year: int, birth_month: int, birth_day: int,
                     lat: float, lng: float, tz_str: str,
                     events: list[dict],
                     strategy: dict,
                     include_slow: bool = False) -> float:
    """
    对一个候选出生时间打综合分。
    strategy  — 来自 SCORING_STRATEGIES[version]，控制启用哪些维度。
    include_slow — Phase2 才为 True，启用慢速维度（progressions / primary_directions）。
    """
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

        # 快速维度（Phase1 + Phase2）
        if strategy.get('transits'):
            try:
                ev_subj = AstrologicalSubject(
                    'ev', ev_date.year, ev_date.month, ev_date.day,
                    12, 0, lng=lng, lat=lat, tz_str=tz_str,
                )
                total += _score_transits(natal, ev_subj, ew)
            except Exception:
                pass

        if strategy.get('solar_arc'):
            total += _score_solar_arc(natal, birth_date, ev_date, ew)

        # 慢速维度（Phase2 only）
        if include_slow:
            if strategy.get('progressions'):
                total += _score_progressions(natal, birth_date, ev_date, h, m, lat, lng, tz_str, ew)
            if strategy.get('primary_directions'):
                total += _score_primary_directions(
                    natal, birth_year, birth_month, birth_day,
                    h, m, lat, lng, tz_str, ev_date, ew,
                )

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


# ── 主入口 ────────────────────────────────────────────────────────

def rectify_birth_time(
    birth_year: int, birth_month: int, birth_day: int,
    lat: float, lng: float, tz_str: str,
    events: list[dict],
    approx_hour: int | None = None,
    approx_minute: int | None = None,
    time_range_hours: float | None = None,
    version: str = DEFAULT_VERSION,
) -> list[dict]:
    """
    两阶段自适应扫描，返回 Top3 候选。
    返回格式: [{hour, minute, score, asc_sign, version}, ...]
    version 参数控制使用哪套评分策略（默认 v1.0）。
    """
    strategy = SCORING_STRATEGIES.get(version, SCORING_STRATEGIES[DEFAULT_VERSION])

    # ── 确定扫描范围 ──
    if approx_hour is not None and time_range_hours is not None:
        center = approx_hour * 60 + (approx_minute or 0)
        half = int(time_range_hours * 60)
        start_min = max(0, center - half)
        end_min = min(1439, center + half)
    else:
        start_min, end_min = 0, 1439

    span = end_min - start_min
    if span <= 240:
        phase1_step = 4
        do_phase2 = False
    else:
        phase1_step = 20
        do_phase2 = True

    # ── Phase 1：快速维度扫描 ──
    phase1_mins = list(range(start_min, end_min + 1, phase1_step))
    scores: dict[int, float] = {}
    for total_min in phase1_mins:
        h, m = total_min // 60, total_min % 60
        scores[total_min] = _score_candidate(
            h, m, birth_year, birth_month, birth_day,
            lat, lng, tz_str, events,
            strategy=strategy,
            include_slow=not do_phase2,   # 小范围单阶段时直接用全量
        )

    # ── Phase 2：Top25% 精细扫描（全量评分）──
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
                        strategy=strategy,
                        include_slow=True,
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
        top3.append({
            'hour': h,
            'minute': m,
            'score': round(score, 2),
            'asc_sign': asc,
            'version': version,       # 验证集用：记录是哪个算法版本产生的结果
        })
        selected_mins.append(total_min)
        if len(top3) >= 3:
            break

    return top3
