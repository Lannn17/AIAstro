"""
出生时间校对：两阶段自适应扫描

Phase1: 全天/大范围 → 每20分钟取一个候选（≤72个）→ 快速评分（行运 + 太阳弧）
Phase2: 对Top候选 ±20分钟细扫，每4分钟一个 → 全量评分（加入慢速方法）
最终返回 Top3（去重：相差<30分钟视为同一候选）

版本策略：
  v1.0 — 基础版：行运 + 太阳弧 + 二次推运
  v1.1 — 加入初级推运（Primary Directions，pyswisseph 精确实现）
  v1.2 — 用完整12宫事件映射替代旧 ASC/MC 行运评分
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
    "v1.2": {
        "transits":           False,   # 由 cusp_hits 替代（不再只看 ASC/MC）
        "solar_arc":          True,
        "progressions":       True,
        "primary_directions": True,
        "cusp_hits":          True,    # 新增：完整12宫事件映射
    },
    "v1.3": {
        "transits":                    False,
        "solar_arc":                   True,
        "progressions":                True,
        "primary_directions":          True,
        "cusp_hits":                   True,
        "dynamic_chart_weights":       True,   # 新增：动态星盘赋权
        "slow_planet_turning_points":  True,   # 新增：慢星转折点检测
    },
}

STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "v1.0": "行运相位 + 太阳弧方向 + 二次推运",
    "v1.1": "v1.0 基础上加入初级推运（Primary Directions，Naibod 率，pyswisseph 精确计算）",
    "v1.2": "v1.1 基础上用完整12宫事件映射替代旧 ASC/MC 行运评分（婚姻→第7宫，丧亲→第4/8宫等）",
    "v1.3": (
        "v1.2 基础上加入动态星盘赋权（行星宫位+宫主星+相位）、"
        "转折点权重归一化、慢星相位检测，及分辨力/证据强度展示"
    ),
}

DEFAULT_VERSION = "v1.3"


ACTIVE_POINTS = [
    'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
    'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
    'Ascendant', 'Medium_Coeli',
]

# 事件类型权重倍率
EVENT_TYPE_WEIGHT = {
    # 感情
    'marriage':                1.8,
    'divorce':                 1.5,
    'new_relationship':        1.2,
    'breakup':                 1.2,
    # 事业
    'career_up':               1.5,
    'career_down':             1.3,
    'career_change':           1.3,
    'business_start':          1.5,
    'business_end':            1.3,
    'retirement':              1.5,
    # 家庭
    'childbirth':              1.8,
    'bereavement_parent':      1.8,
    'bereavement_spouse':      2.0,
    'bereavement_child':       2.0,
    'bereavement_other':       1.3,
    # 健康
    'serious_illness':         1.5,
    'accident':                1.5,
    'surgery':                 1.3,
    # 居住/迁移
    'relocation_domestic':     0.8,
    'relocation_international': 1.2,
    # 财务
    'financial_gain':          1.3,
    'financial_loss':          1.3,
    'inheritance':             1.5,
    'bankruptcy':              1.5,
    # 教育/法律
    'graduation':              1.0,
    'study_abroad':            1.3,
    'major_exam':              1.0,
    'legal_win':               1.2,
    'legal_loss':              1.2,
    # 健康（补充）
    'mental_health_crisis':    1.5,
    # 财务（补充）
    'major_investment':        1.2,
    # 家庭（补充）
    'family_bond_change':      1.5,
    # 精神
    'spiritual_awakening':     1.2,
    # 其他
    'other':                   1.0,
    # 向后兼容（旧 event_type 名）
    'bereavement':             1.5,
    'illness':                 1.3,
    'relocation':              0.9,
}

# 事件类型 → 相关宫头（Kerykeion 属性名，权重倍率）
# 权重倍率：该宫头对此类事件的占星敏感度
EVENT_HOUSE_MAP: dict[str, list[tuple[str, float]]] = {
    # 感情
    'marriage':                [('seventh_house', 2.5), ('fifth_house', 1.5), ('first_house', 1.0)],
    'divorce':                 [('seventh_house', 2.5), ('eighth_house', 1.8), ('first_house', 1.2)],
    'new_relationship':        [('seventh_house', 2.0), ('fifth_house', 1.8), ('first_house', 1.0)],
    'breakup':                 [('seventh_house', 2.0), ('eighth_house', 1.5), ('twelfth_house', 1.2)],
    # 事业
    'career_up':               [('tenth_house', 2.5), ('first_house', 1.5), ('second_house', 1.2)],
    'career_down':             [('tenth_house', 2.5), ('sixth_house', 1.5), ('twelfth_house', 1.2)],
    'career_change':           [('tenth_house', 2.0), ('first_house', 1.8), ('ninth_house', 1.2)],
    'business_start':          [('tenth_house', 2.0), ('first_house', 1.8), ('second_house', 1.5)],
    'business_end':            [('tenth_house', 2.0), ('eighth_house', 1.5), ('twelfth_house', 1.5)],
    'retirement':              [('tenth_house', 2.5), ('fourth_house', 1.8), ('twelfth_house', 1.2)],
    # 家庭
    'childbirth':              [('fifth_house', 2.5), ('fourth_house', 1.8), ('first_house', 1.2)],
    'bereavement_parent':      [('fourth_house', 2.5), ('tenth_house', 2.0), ('eighth_house', 1.5)],
    'bereavement_spouse':      [('seventh_house', 2.0), ('eighth_house', 2.5), ('fourth_house', 1.2)],
    'bereavement_child':       [('fifth_house', 2.5), ('eighth_house', 2.0), ('fourth_house', 1.2)],
    'bereavement_other':       [('eighth_house', 2.0), ('fourth_house', 1.5), ('twelfth_house', 1.2)],
    # 健康
    'serious_illness':         [('sixth_house', 2.5), ('first_house', 2.0), ('twelfth_house', 1.5)],
    'accident':                [('first_house', 2.5), ('eighth_house', 2.0), ('sixth_house', 1.5)],
    'surgery':                 [('eighth_house', 2.0), ('sixth_house', 2.0), ('first_house', 1.8)],
    # 居住/迁移
    'relocation_domestic':     [('fourth_house', 2.5), ('third_house', 1.8)],
    'relocation_international':[('ninth_house', 2.5), ('fourth_house', 2.0), ('third_house', 1.2)],
    # 财务
    'financial_gain':          [('second_house', 2.5), ('eighth_house', 1.8), ('tenth_house', 1.5)],
    'financial_loss':          [('second_house', 2.5), ('eighth_house', 2.0), ('twelfth_house', 1.5)],
    'inheritance':             [('eighth_house', 2.5), ('second_house', 2.0), ('fourth_house', 1.5)],
    'bankruptcy':              [('second_house', 2.5), ('eighth_house', 2.0), ('twelfth_house', 1.8)],
    # 教育/法律
    'graduation':              [('ninth_house', 2.5), ('third_house', 1.5), ('tenth_house', 1.2)],
    'study_abroad':            [('ninth_house', 2.5), ('third_house', 1.5), ('fourth_house', 1.0)],
    'major_exam':              [('ninth_house', 2.0), ('tenth_house', 1.5), ('third_house', 1.2)],
    'legal_win':               [('ninth_house', 2.0), ('seventh_house', 1.8), ('tenth_house', 1.5)],
    'legal_loss':              [('ninth_house', 1.8), ('seventh_house', 1.8), ('twelfth_house', 2.0)],
    # 健康（补充）
    'mental_health_crisis':    [('twelfth_house', 2.5), ('first_house', 2.0), ('sixth_house', 1.5)],
    # 财务（补充）
    'major_investment':        [('second_house', 2.0), ('fourth_house', 1.8), ('eighth_house', 1.2)],
    # 家庭（补充）
    'family_bond_change':      [('fourth_house', 2.5), ('eighth_house', 1.2), ('first_house', 1.0)],
    # 精神/其他
    'spiritual_awakening':     [('twelfth_house', 2.5), ('ninth_house', 2.0), ('eighth_house', 1.5)],
    'other':                   [('first_house', 1.0), ('tenth_house', 1.0)],
    # 向后兼容
    'bereavement':             [('eighth_house', 2.0), ('fourth_house', 1.8), ('twelfth_house', 1.2)],
    'illness':                 [('sixth_house', 2.5), ('first_house', 2.0), ('twelfth_house', 1.5)],
    'relocation':              [('fourth_house', 2.5), ('third_house', 1.8)],
}


# 宫主星映射（现代守护星）
_SIGN_RULER: dict[str, str] = {
    "Aries": "Mars",    "Taurus": "Venus",   "Gemini": "Mercury",
    "Cancer": "Moon",   "Leo": "Sun",         "Virgo": "Mercury",
    "Libra": "Venus",   "Scorpio": "Pluto",   "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}

# 每种事件类型对应的关键行星（用于动态星盘赋权）
_EVENT_KEY_PLANETS: dict[str, list] = {
    'marriage':                   ['Venus', 'Moon', 'Jupiter'],
    'new_relationship':           ['Venus', 'Moon', 'Jupiter'],
    'divorce':                    ['Saturn', 'Pluto', 'Mars'],
    'breakup':                    ['Saturn', 'Pluto', 'Mars'],
    'career_up':                  ['Sun', 'Jupiter', 'Mars'],
    'business_start':             ['Sun', 'Jupiter', 'Mars'],
    'retirement':                 ['Sun', 'Jupiter', 'Mars'],
    'career_down':                ['Saturn', 'Pluto'],
    'business_end':               ['Saturn', 'Pluto'],
    'career_change':              ['Uranus', 'Jupiter'],
    'childbirth':                 ['Moon', 'Jupiter', 'Sun'],
    'bereavement_parent':         ['Saturn', 'Pluto'],
    'bereavement_spouse':         ['Saturn', 'Pluto'],
    'bereavement_child':          ['Saturn', 'Pluto'],
    'bereavement_other':          ['Saturn', 'Pluto'],
    'bereavement':                ['Saturn', 'Pluto'],
    'serious_illness':            ['Mars', 'Saturn', 'Pluto'],
    'mental_health_crisis':       ['Mars', 'Saturn', 'Pluto'],
    'illness':                    ['Mars', 'Saturn', 'Pluto'],
    'accident':                   ['Mars', 'Uranus'],
    'surgery':                    ['Mars', 'Uranus'],
    'relocation_international':   ['Jupiter', 'Uranus'],
    'study_abroad':               ['Jupiter', 'Uranus'],
    'relocation_domestic':        ['Moon', 'Saturn'],
    'relocation':                 ['Moon', 'Saturn'],
    'financial_gain':             ['Venus', 'Jupiter'],
    'inheritance':                ['Venus', 'Jupiter'],
    'major_investment':           ['Venus', 'Jupiter'],
    'financial_loss':             ['Saturn', 'Pluto'],
    'bankruptcy':                 ['Saturn', 'Pluto'],
    'graduation':                 ['Jupiter', 'Mercury'],
    'major_exam':                 ['Jupiter', 'Mercury'],
    'legal_win':                  ['Jupiter', 'Saturn'],
    'legal_loss':                 ['Jupiter', 'Saturn'],
    'family_bond_change':         ['Moon', 'Saturn'],
    'spiritual_awakening':        ['Neptune', 'Pluto', 'Uranus'],
}
# 未列出的类型 → 空列表 → chart_affinity 保持基础值 1.0


# 精度权重：日期越模糊权重越低
_PRECISION_WEIGHT = {"day": 1.0, "month": 0.7, "year": 0.4}


def _expand_events(events: list[dict]) -> list[dict]:
    """将模糊日期事件展开为具体采样点，同时折算权重。

    - precision="day" (month+day 均有)：保持原权重，直接使用
    - precision="month" (month 有但 day 为 None)：取当月15日，权重×0.7
    - precision="year" (month 为 None)：均匀采样1/4/7/10月15日，权重×0.4/4
    """
    expanded = []
    for ev in events:
        month = ev.get('month')
        day = ev.get('day')
        if month is None:
            precision_mult = _PRECISION_WEIGHT["year"]
            samples = [(ev['year'], m, 15) for m in [1, 4, 7, 10]]
        elif day is None:
            precision_mult = _PRECISION_WEIGHT["month"]
            samples = [(ev['year'], month, 15)]
        else:
            precision_mult = _PRECISION_WEIGHT["day"]
            samples = [(ev['year'], month, day)]

        per_weight = ev.get('weight', 1.0) * precision_mult / len(samples)
        for y, m, d in samples:
            expanded.append({**ev, 'year': y, 'month': m, 'day': d, 'weight': per_weight})
    return expanded


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

def _score_cusp_hits(natal: AstrologicalSubject,
                     event_subj: AstrologicalSubject,
                     event_type: str,
                     event_weight: float,
                     orb: float = 3.0) -> float:
    """
    完整12宫宫头命中打分（v1.2 新增）。
    按事件类型从 EVENT_HOUSE_MAP 取相关宫头，计算行运行星与这些宫头的相位得分。
    替代 v1.0/v1.1 中只检查 ASC/MC 的 _score_transits。
    """
    relevant_cusps = EVENT_HOUSE_MAP.get(event_type, EVENT_HOUSE_MAP['other'])
    planet_attrs = ['sun', 'moon', 'mercury', 'venus', 'mars',
                    'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
    aspects = {0: 3.0, 180: 2.0, 120: 2.0, 90: 1.5, 60: 1.0}

    score = 0.0
    for cusp_attr, cusp_mult in relevant_cusps:
        cusp_obj = getattr(natal, cusp_attr, None)
        if cusp_obj is None:
            continue
        cusp_pos = cusp_obj.abs_pos

        for p_attr in planet_attrs:
            tr_p = getattr(event_subj, p_attr, None)
            if tr_p is None:
                continue
            diff = abs(tr_p.abs_pos - cusp_pos)
            if diff > 180:
                diff = 360 - diff
            for asp_angle, asp_weight in aspects.items():
                orbit = abs(diff - asp_angle)
                if orbit <= orb:
                    score += (orb - orbit) * asp_weight * cusp_mult * event_weight
                    break   # 只取最近相位
    return score


_SLOW_PLANET_COEF: dict = {
    'pluto':   3.5,
    'saturn':  3.0,
    'uranus':  2.5,
    'neptune': 1.5,
    'jupiter': 1.5,
}
_SLOW_ASPECT_TARGETS = (0, 180, 90, 120)   # major aspects, no sextile


def _score_slow_planet_transits(
    natal: AstrologicalSubject,
    event_subj: AstrologicalSubject,
    event_weight: float,
    orb: float = 2.0,
) -> float:
    """
    Slow-planet transit score for turning-point events (Phase 2 only).
    Checks Saturn/Uranus/Pluto/Jupiter/Neptune in event_subj against
    ALL natal planets. Tighter orb (2°) than regular transits (5°).
    """
    score = 0.0
    for slow_attr, coef in _SLOW_PLANET_COEF.items():
        t_obj = getattr(event_subj, slow_attr, None)
        if t_obj is None:
            continue
        t_pos = getattr(t_obj, 'abs_pos', None)
        if t_pos is None:
            continue
        for natal_attr in _PLANET_CAP:
            n_obj = getattr(natal, natal_attr, None)
            if n_obj is None:
                continue
            n_pos = getattr(n_obj, 'abs_pos', None)
            if n_pos is None:
                continue
            diff = abs(t_pos - n_pos) % 360
            if diff > 180:
                diff = 360 - diff
            for target in _SLOW_ASPECT_TARGETS:
                orbit = abs(diff - target)
                if orbit <= orb:
                    score += (orb - orbit) * coef * event_weight
                    break   # count each natal planet once per slow planet
    return score


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

    # v1.3: 转折点乘数归一化
    n_turning_points = sum(1 for e in events if e.get('is_turning_point', False))
    _tp_mult_per = (
        max(1.1, 1.5 / (n_turning_points ** 0.5)) if n_turning_points > 0 else 1.0
    )

    # v1.3: 预计算动态星盘赋权（每候选一次）
    chart_affinity: dict = {}
    if strategy.get('dynamic_chart_weights'):
        try:
            chart_affinity = _compute_chart_affinity(natal)
        except Exception:
            chart_affinity = {}

    for ev in _expand_events(events):
        ev_date = date(ev['year'], ev['month'], ev['day'])
        ev_type = ev.get('event_type', 'other')
        ew = (
            ev.get('weight', 1.0)
            * EVENT_TYPE_WEIGHT.get(ev_type, 1.0)
            * chart_affinity.get(ev_type, 1.0)   # v1.3 动态系数
        )
        if ev.get('is_turning_point', False):
            ew *= _tp_mult_per   # v1.3 归一化转折点乘数

        # 快速维度（Phase1 + Phase2）
        needs_ev_subj = strategy.get('transits') or strategy.get('cusp_hits')
        ev_subj = None
        if needs_ev_subj:
            try:
                ev_subj = AstrologicalSubject(
                    'ev', ev_date.year, ev_date.month, ev_date.day,
                    12, 0, lng=lng, lat=lat, tz_str=tz_str,
                )
                if strategy.get('transits'):
                    total += _score_transits(natal, ev_subj, ew)
                if strategy.get('cusp_hits'):
                    total += _score_cusp_hits(natal, ev_subj, ev_type, ew)
            except Exception:
                ev_subj = None

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
            # v1.3: 慢星转折点检测
            if strategy.get('slow_planet_turning_points') and ev.get('is_turning_point', False):
                try:
                    sp_subj = ev_subj if ev_subj is not None else AstrologicalSubject(
                        'sp', ev_date.year, ev_date.month, ev_date.day,
                        12, 0, lng=lng, lat=lat, tz_str=tz_str,
                    )
                    total += _score_slow_planet_transits(natal, sp_subj, ew)
                except Exception:
                    pass

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


# ── v1.3 辅助函数 ──────────────────────────────────────────────────

_PLANET_CAP: dict[str, str] = {
    'sun': 'Sun', 'moon': 'Moon', 'mercury': 'Mercury',
    'venus': 'Venus', 'mars': 'Mars', 'jupiter': 'Jupiter',
    'saturn': 'Saturn', 'uranus': 'Uranus',
    'neptune': 'Neptune', 'pluto': 'Pluto',
}

_HOUSE_NAME_TO_NUM: dict[str, int] = {
    'First_House': 1, 'Second_House': 2, 'Third_House': 3,
    'Fourth_House': 4, 'Fifth_House': 5, 'Sixth_House': 6,
    'Seventh_House': 7, 'Eighth_House': 8, 'Ninth_House': 9,
    'Tenth_House': 10, 'Eleventh_House': 11, 'Twelfth_House': 12,
}

_HOUSE_ATTR_TO_NUM: dict[str, int] = {
    'first_house': 1,   'second_house': 2,  'third_house': 3,
    'fourth_house': 4,  'fifth_house': 5,   'sixth_house': 6,
    'seventh_house': 7, 'eighth_house': 8,  'ninth_house': 9,
    'tenth_house': 10,  'eleventh_house': 11, 'twelfth_house': 12,
}

_ANGULAR_HOUSES = {1, 4, 7, 10}
_IMPORTANT_PLANETS = {'Sun', 'Moon', 'Jupiter', 'Saturn'}


def _planet_house(natal: AstrologicalSubject, attr: str) -> int:
    """Return the house number (1-12) of a planet, or 0 on failure."""
    try:
        p = getattr(natal, attr.lower(), None)
        if p is None:
            return 0
        h = getattr(p, 'house', 0)
        if isinstance(h, int):
            return h
        return _HOUSE_NAME_TO_NUM.get(str(h), 0)
    except Exception:
        return 0


def _has_tight_aspect(pos1: float, pos2: float, orb: float = 5.0) -> bool:
    """True if two ecliptic positions form a major aspect within orb."""
    diff = abs(pos1 - pos2) % 360
    if diff > 180:
        diff = 360 - diff
    return any(abs(diff - t) <= orb for t in (0, 60, 90, 120, 180))


def _compute_chart_affinity(natal: AstrologicalSubject) -> dict:
    """
    Compute per-event-type affinity multiplier from natal chart.
    Three layers: planet-in-house (+0.25/+0.15), house-ruler angular (+0.15),
    ruler-aspect-key-planet (+0.10).
    Returns dict[event_type -> float] clamped to [0.6, 2.0].
    Called once per candidate in Phase 2 when dynamic_chart_weights is enabled.
    """
    result: dict = {}

    for ev_type, house_pairs in EVENT_HOUSE_MAP.items():
        affinity = 1.0
        key_planets = _EVENT_KEY_PLANETS.get(ev_type, [])

        for house_attr, _ in house_pairs[:2]:   # top 2 relevant houses
            house_num = _HOUSE_ATTR_TO_NUM.get(house_attr, 0)
            if not house_num:
                continue

            # ── Layer 1: planets in this house ──────────────────────
            for planet_attr in _PLANET_CAP:
                ph = _planet_house(natal, planet_attr)
                if ph != house_num:
                    continue
                pname = _PLANET_CAP[planet_attr]
                if pname in key_planets:
                    affinity += 0.25
                elif pname in _IMPORTANT_PLANETS:
                    affinity += 0.15

            # ── Layer 2: house ruler in angular house ────────────────
            try:
                house_obj = getattr(natal, house_attr, None)
                house_sign = getattr(house_obj, 'sign', '') if house_obj else ''
                ruler_name = _SIGN_RULER.get(house_sign, '')
                if ruler_name:
                    ruler_house = _planet_house(natal, ruler_name)
                    if ruler_house in _ANGULAR_HOUSES:
                        affinity += 0.15

                    # ── Layer 3: ruler tight aspect with key planets ──
                    ruler_obj = getattr(natal, ruler_name.lower(), None)
                    ruler_pos = getattr(ruler_obj, 'abs_pos', None) if ruler_obj else None
                    if ruler_pos is not None:
                        for kp in key_planets:
                            kp_obj = getattr(natal, kp.lower(), None)
                            kp_pos = getattr(kp_obj, 'abs_pos', None) if kp_obj else None
                            if kp_pos is not None and _has_tight_aspect(ruler_pos, kp_pos, orb=5.0):
                                affinity += 0.10
            except Exception:
                pass

        result[ev_type] = max(0.6, min(2.0, affinity))

    return result


# ── 主入口 ────────────────────────────────────────────────────────

def _compute_indicators(top3: list, raw_events: list) -> dict:
    """
    Compute gap_ratio (discrimination) and evidence_score (input quality).
    Uses raw (pre-expansion) events to avoid double-counting precision_weight.
    """
    scores = [t['score'] for t in top3]
    top1 = scores[0] if scores else 0.0
    top2 = scores[1] if len(scores) > 1 else 0.0
    gap_ratio = 0.0 if top1 == 0 else (top1 - top2) / top1

    if gap_ratio >= 0.25:
        gap_label = '大'
    elif gap_ratio >= 0.10:
        gap_label = '中'
    else:
        gap_label = '小'

    n = len(raw_events)
    if n == 0:
        ev_score = 0.0
    else:
        total_w = 0.0
        for ev in raw_events:
            mth, d = ev.get('month'), ev.get('day')
            if mth and d:
                pw = 1.0
            elif mth:
                pw = 0.7
            else:
                pw = 0.4
            total_w += ev.get('weight', 1.0) * pw
        ev_score = total_w / n

    if ev_score >= 1.5:
        ev_label = '强'
    elif ev_score >= 0.8:
        ev_label = '中'
    else:
        ev_label = '弱'

    return {
        'gap_ratio': round(gap_ratio, 3),
        'gap_label': gap_label,
        'evidence_score': round(ev_score, 3),
        'evidence_label': ev_label,
    }


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
    两阶段自适应扫描，返回 (top3, indicators)。
    top3: [{hour, minute, score, asc_sign, version}, ...]
    indicators: {gap_ratio, gap_label, evidence_score, evidence_label}
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

    indicators = _compute_indicators(top3, events)
    return top3, indicators
