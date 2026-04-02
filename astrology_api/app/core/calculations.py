"""
Astrological calculation module for the AstroAPI application.
"""
from kerykeion import AstrologicalSubject
from typing import Any, Dict, List, Optional, Tuple, Union, Literal, cast
from datetime import datetime, timedelta
import logging
import math

from ..schemas.models import (
    PlanetData, HouseCuspData, AspectData, 
    HouseSystemType, HOUSE_SYSTEM_MAP,
    LanguageType
)
from ..interpretations.translations import (
    translate_planet, translate_sign, translate_aspect, translate_house
)
from ..core.cache import get_cache_key, get_from_cache, save_to_cache

logger = logging.getLogger(__name__)

# Kerykeion 4.x returns 3-letter sign abbreviations; map to full names for translations
SIGN_ABBR_TO_FULL = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces"
}

# Kerykeion 4.x returns house names like "Tenth_House"; map to int
HOUSE_NAME_TO_NUM = {
    "First_House": 1, "Second_House": 2, "Third_House": 3, "Fourth_House": 4,
    "Fifth_House": 5, "Sixth_House": 6, "Seventh_House": 7, "Eighth_House": 8,
    "Ninth_House": 9, "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12
}

def get_kerykeion_house_system_code(house_system: HouseSystemType) -> str:
    """Converts the house system name to the code used by Kerykeion."""
    return HOUSE_SYSTEM_MAP.get(house_system, "P")

def create_astrological_subject(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    longitude: float,
    latitude: float,
    tz_str: str,
    house_system: HouseSystemType = "Placidus"
) -> AstrologicalSubject:
    """Creates a Kerykeion AstrologicalSubject object."""
    try:
        # Ensure house_system is not None
        house_system_code = HOUSE_SYSTEM_MAP.get(house_system or "Placidus", "P")
        
        subject = AstrologicalSubject(
            name=str(name),
            year=int(year),
            month=int(month),
            day=int(day),
            hour=int(hour),
            minute=int(minute),
            city="CustomLocation",
            nation="",
            lng=float(longitude),
            lat=float(latitude),
            tz_str=str(tz_str),
            houses_system_identifier=house_system_code
        )
        
        return subject
        
    except Exception as e:
        logger.error(f"Error creating AstrologicalSubject: {str(e)}")
        raise ValueError(f"Error creating AstrologicalSubject: {str(e)}")

def get_planet_data(subject: AstrologicalSubject, language: LanguageType = "pt") -> Dict[str, PlanetData]:
    """
    Gets planet data from an AstrologicalSubject.

    Args:
        subject (AstrologicalSubject): Astrological subject
        language (LanguageType): Language for translated names. Defaults to "pt".

    Returns:
        Dict[str, PlanetData]: Dictionary with planet data
    """
    planets_data = {}

    # Ensure language is not None
    language = language or "pt"
    
    # 只保留平均节点/黑月，过滤掉真实（振荡）版本
    _SKIP_ATTRS = {'true_node', 'true_lilith'}

    for planet_name in subject.planets_names_list:
        attr = planet_name.lower()
        if attr in _SKIP_ATTRS:
            continue
        if not hasattr(subject, attr):
            continue
        planet = getattr(subject, attr)
        if planet is None:
            continue
        name = planet.name
        sign_full = SIGN_ABBR_TO_FULL.get(planet.sign, planet.sign)
        house_num = HOUSE_NAME_TO_NUM.get(str(planet.house), 0)
        if house_num == 0:
            try:
                h = int(planet.house)
                if 1 <= h <= 12:
                    house_num = h
            except (ValueError, TypeError):
                pass

        planets_data[name.lower()] = PlanetData(
            name=name,
            name_original=name,
            longitude=planet.abs_pos,
            latitude=0.0,
            sign=sign_full,
            sign_original=sign_full,
            sign_num=planet.sign_num,
            house=house_num,
            retrograde=planet.retrograde,
            speed=0.0
        )

    return planets_data

def get_houses_data(subject: AstrologicalSubject, language: LanguageType = "pt") -> Dict[str, HouseCuspData]:
    """
    Gets house data from an AstrologicalSubject.

    Args:
        subject (AstrologicalSubject): Astrological subject
        language (LanguageType): Language for translated names. Defaults to "pt".

    Returns:
        Dict[str, HouseCuspData]: Dictionary with house data
    """
    houses_data = {}

    # Ensure language is not None
    language = language or "pt"
    
    for i, house_name in enumerate(subject.houses_names_list, start=1):
        attr = house_name.lower()
        if not hasattr(subject, attr):
            continue
        house = getattr(subject, attr)
        sign_full = SIGN_ABBR_TO_FULL.get(house.sign, house.sign)

        houses_data[str(i)] = HouseCuspData(
            number=i,
            sign=sign_full,
            sign_original=sign_full,
            sign_num=house.sign_num,
            longitude=house.abs_pos
        )

    return houses_data

def calculate_aspect(point1_long: float, point2_long: float) -> Optional[Dict[str, Union[str, float]]]:
    """Calculates the aspect between two points based on their longitudes."""
    # Difference between longitudes
    diff = abs(point1_long - point2_long)
    if diff > 180:
        diff = 360 - diff
        
    # Aspect definitions and their orbs
    aspects = {
        "Conjunction": {"angle": 0, "orb": 8},
        "Opposition": {"angle": 180, "orb": 8},
        "Trine": {"angle": 120, "orb": 6},
        "Square": {"angle": 90, "orb": 6},
        "Sextile": {"angle": 60, "orb": 4}
    }
    
    # Check each possible aspect
    for aspect_name, aspect_data in aspects.items():
        orbit = abs(diff - aspect_data["angle"])
        if orbit <= aspect_data["orb"]:
            return {
                "aspect": aspect_name,
                "orbit": orbit,
                "angle": aspect_data["angle"],
                "diff": diff
            }
            
    return None

def get_aspects_data(subject: AstrologicalSubject, language: LanguageType = "pt") -> List[AspectData]:
    """Calculates aspects between planets in a chart."""
    result = []
    processed = set()

    try:
        # Main planet list for aspects
        planet_attrs = [
            'sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn',
            'uranus', 'neptune', 'pluto'
        ]
        
        # Calculate aspects between all planet pairs
        for i, p1_attr in enumerate(planet_attrs):
            if not hasattr(subject, p1_attr):
                continue
                
            planet1 = getattr(subject, p1_attr)
            if not planet1 or not hasattr(planet1, 'longitude'):
                continue
                
            for p2_attr in planet_attrs[i+1:]:
                if not hasattr(subject, p2_attr):
                    continue
                    
                planet2 = getattr(subject, p2_attr)
                if not planet2 or not hasattr(planet2, 'longitude'):
                    continue
                    
                # Calculate the aspect
                aspect_info = calculate_aspect(planet1.longitude, planet2.longitude)
                if not aspect_info:
                    continue
                
                # Create unique key for the aspect
                aspect_key = tuple(sorted([p1_attr, p2_attr]))
                if aspect_key in processed:
                    continue
                
                processed.add(aspect_key)
                
                # Determine whether the aspect is applying
                applying = False
                if hasattr(planet1, 'motion') and hasattr(planet2, 'motion'):
                    if hasattr(planet1.motion, 'speed') and hasattr(planet2.motion, 'speed'):
                        applying = planet1.motion.speed > planet2.motion.speed
                
                # Create the AspectData object
                aspect_data = AspectData(
                    p1_name=translate_planet(planet1.name, language),
                    p1_name_original=planet1.name,
                    p1_owner="natal",
                    p2_name=translate_planet(planet2.name, language),
                    p2_name_original=planet2.name,
                    p2_owner="natal",
                    aspect=translate_aspect(aspect_info["aspect"], language),
                    aspect_original=aspect_info["aspect"],
                    orbit=round(float(aspect_info["orbit"]), 4),
                    aspect_degrees=round(float(aspect_info["angle"]), 4),
                    diff=round(float(aspect_info["diff"]), 4),
                    applying=applying
                )
                
                result.append(aspect_data)
                
    except Exception as e:
        logger.error(f"Error calculating aspects: {str(e)}")
        
    return result

def get_aspects_between_charts(
    subject1: AstrologicalSubject, 
    subject2: AstrologicalSubject,
    language: LanguageType = "pt"
) -> List[AspectData]:
    """Calculates aspects between two astrological charts."""
    result = []

    try:
        # Use chart aspects method if available
        if hasattr(subject1, 'get_aspects_between'):
            aspects = subject1.get_aspects_between(subject2)
        else:
            # Fallback implementation if the method does not exist
            aspects = calculate_aspects_between(subject1, subject2)
            
        for aspect in aspects:
            if not aspect:
                continue
                
            p1_name = aspect.p1.name if hasattr(aspect, 'p1') and hasattr(aspect.p1, 'name') else ''
            p2_name = aspect.p2.name if hasattr(aspect, 'p2') and hasattr(aspect.p2, 'name') else ''
            aspect_name = aspect.aspect if hasattr(aspect, 'aspect') else ''
            
            aspect_data = AspectData(
                p1_name=translate_planet(p1_name, language),
                p1_name_original=p1_name,
                p1_owner="natal",
                p2_name=translate_planet(p2_name, language),
                p2_name_original=p2_name,
                p2_owner="transit",
                aspect=translate_aspect(aspect_name, language),
                aspect_original=aspect_name,
                orbit=float(aspect.orbit) if hasattr(aspect, 'orbit') else 0.0,
                aspect_degrees=float(aspect.aspect_degrees) if hasattr(aspect, 'aspect_degrees') else 0.0,
                diff=float(aspect.diff) if hasattr(aspect, 'diff') else 0.0,
                applying=False  # TODO: implement applying/separating logic
            )
            
            result.append(aspect_data)
            
    except Exception as e:
        logger.error(f"Error calculating aspects between charts: {str(e)}")
        
    return result

def calculate_aspects_between(subject1: AstrologicalSubject, subject2: AstrologicalSubject) -> List[Any]:
    """Fallback implementation for calculating aspects between charts."""
    result = []

    # Define main aspects and their orbs
    aspects = {
        "Conjunction": {"angle": 0, "orb": 8},
        "Opposition": {"angle": 180, "orb": 8},
        "Trine": {"angle": 120, "orb": 6},
        "Square": {"angle": 90, "orb": 6},
        "Sextile": {"angle": 60, "orb": 4}
    }
    
    try:
        planet_attrs = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter',
                        'saturn', 'uranus', 'neptune', 'pluto']
        # Iterate over planets of the first chart
        for p1_attr in planet_attrs:
            p1 = getattr(subject1, p1_attr, None)
            if not p1:
                continue

            # Iterate over planets of the second chart
            for p2_attr in planet_attrs:
                p2 = getattr(subject2, p2_attr, None)
                if not p2:
                    continue
                    
                # Calculate longitude difference
                diff = abs(p1.abs_pos - p2.abs_pos)
                if diff > 180:
                    diff = 360 - diff
                    
                # Check aspects
                for aspect_name, aspect_data in aspects.items():
                    orbit = abs(diff - aspect_data["angle"])

                    if orbit <= aspect_data["orb"]:
                        # Create a simple aspect object
                        aspect = type("Aspect", (), {
                            "p1": p1,
                            "p2": p2,
                            "aspect": aspect_name,
                            "orbit": orbit,
                            "aspect_degrees": aspect_data["angle"],
                            "diff": diff
                        })
                        
                        result.append(aspect)
                        
    except Exception as e:
        logger.error(f"Error calculating aspects manually: {str(e)}")
        
    return result

# Removed duplicate definition of get_aspects_data to avoid confusion and maintenance issues.

def get_aspects_between_subjects(
    subject1: AstrologicalSubject, 
    subject2: AstrologicalSubject,
    subject1_owner: str = "natal",
    subject2_owner: str = "transit",
    language: str = "pt"
) -> List[AspectData]:
    """
    Extracts aspect data between two AstrologicalSubject objects.

    Args:
        subject1 (AstrologicalSubject): First AstrologicalSubject (usually the natal chart).
        subject2 (AstrologicalSubject): Second AstrologicalSubject (usually the transit chart).
        subject1_owner (str, optional): Owner identifier for the first subject. Defaults to "natal".
        subject2_owner (str, optional): Owner identifier for the second subject. Defaults to "transit".
        language (str, optional): Language for text output. Defaults to "pt".

    Returns:
        List[AspectData]: List of aspect data between the two subjects.
    """
    result = []
    planet_attrs = [
        'sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn',
        'uranus', 'neptune', 'pluto', 'mean_node', 'chiron'
    ]
    aspect_configs = {
        "Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60
    }
    orbs = {"Conjunction": 8, "Opposition": 8, "Trine": 6, "Square": 6, "Sextile": 4}

    for p1_attr in planet_attrs:
        p1 = getattr(subject1, p1_attr, None)
        if not p1:
            continue
        for p2_attr in planet_attrs:
            p2 = getattr(subject2, p2_attr, None)
            if not p2:
                continue
            diff = abs(p1.abs_pos - p2.abs_pos)
            if diff > 180:
                diff = 360 - diff
            for aspect_name, aspect_degree in aspect_configs.items():
                orbit = abs(diff - aspect_degree)
                if orbit <= orbs[aspect_name]:
                    result.append(AspectData(
                        p1_name=translate_planet(p1.name, language),
                        p1_name_original=p1.name,
                        p1_owner=subject1_owner,
                        p2_name=translate_planet(p2.name, language),
                        p2_name_original=p2.name,
                        p2_owner=subject2_owner,
                        aspect=translate_aspect(aspect_name, language),
                        aspect_original=aspect_name,
                        orbit=round(orbit, 4),
                        aspect_degrees=float(aspect_degree),
                        diff=round(diff, 4),
                        applying=False
                    ))

    return result

def get_synastry_aspects_data(subject1: AstrologicalSubject, subject2: AstrologicalSubject, language: str = "zh") -> List[AspectData]:
    """
    计算两张本命盘之间的跨盘相位。
    包含：行星×行星、行星×对方ASC/MC。
    每条相位带方向性（p1_to_p2 / p2_to_p1）和 double whammy 标记。
    """
    planet_attrs = [
        'sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn',
        'uranus', 'neptune', 'pluto', 'mean_node', 'chiron'
    ]
    # ASC/MC 作为接受点（不作为主动点）
    sensitive_points = {
        'first_house': 'Ascendant',
        'tenth_house': 'Midheaven',
    }
    aspect_configs = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}
    orbs = {"Conjunction": 8, "Opposition": 8, "Trine": 6, "Square": 6, "Sextile": 4}

    def _calc_aspects(attribs_a, subject_a, attribs_b, subject_b, direction: str) -> list:
        results = []
        for p1_attr in attribs_a:
            p1 = getattr(subject_a, p1_attr, None)
            if p1 is None:
                continue
            for p2_attr in attribs_b:
                p2 = getattr(subject_b, p2_attr, None)
                if p2 is None:
                    continue
                diff = abs(p1.abs_pos - p2.abs_pos)
                if diff > 180:
                    diff = 360 - diff
                for asp_name, asp_angle in aspect_configs.items():
                    orb = abs(diff - asp_angle)
                    if orb <= orbs[asp_name]:
                        results.append({
                            "p1_attr": p1_attr,
                            "p1_pos": p1.abs_pos,
                            "p2_attr": p2_attr,
                            "p2_pos": p2.abs_pos,
                            "norm_diff": diff,
                            "aspect": asp_name,
                            "orbit": round(orb, 4),
                            "direction": direction,
                        })
                        break
        return results

    # 行星 × 行星（双向）
    raw_p1p2 = _calc_aspects(planet_attrs, subject1, planet_attrs, subject2, "p1_to_p2")
    raw_p2p1 = _calc_aspects(planet_attrs, subject2, planet_attrs, subject1, "p2_to_p1")

    # 行星 × 对方 ASC/MC
    sp_attrs = list(sensitive_points.keys())
    raw_p1sp2 = _calc_aspects(planet_attrs, subject1, sp_attrs, subject2, "p1_to_p2")
    raw_p2sp1 = _calc_aspects(planet_attrs, subject2, sp_attrs, subject1, "p2_to_p1")

    all_raw = raw_p1p2 + raw_p2p1 + raw_p1sp2 + raw_p2sp1

    # Double whammy：同一对行星在双向均有同类相位
    seen_pairs: dict = {}
    for r in all_raw:
        key = (frozenset([r["p1_attr"], r["p2_attr"]]), r["aspect"])
        seen_pairs[key] = seen_pairs.get(key, "") + r["direction"] + ","
    dw_keys = {k for k, v in seen_pairs.items() if "p1_to_p2" in v and "p2_to_p1" in v}

    aspects = []
    for r in all_raw:
        key = (frozenset([r["p1_attr"], r["p2_attr"]]), r["aspect"])
        p1_display = sensitive_points.get(r["p1_attr"], r["p1_attr"].replace("_", " ").title())
        p2_display = sensitive_points.get(r["p2_attr"], r["p2_attr"].replace("_", " ").title())
        p1_owner = "chart1" if r["direction"] == "p1_to_p2" else "chart2"
        p2_owner = "chart2" if r["direction"] == "p1_to_p2" else "chart1"
        asp_angle = aspect_configs[r["aspect"]]
        aspects.append(AspectData(
            p1_name=p1_display,
            p2_name=p2_display,
            p1_owner=p1_owner,
            p2_owner=p2_owner,
            aspect=r["aspect"],
            aspect_degrees=float(asp_angle),
            orbit=r["orbit"],
            diff=round(r["norm_diff"], 4),
            applying=False,
            direction=r["direction"],
            double_whammy=(key in dw_keys),
        ))

    aspects.sort(key=lambda a: a.orbit)
    return aspects

def get_progressed_chart(natal_subject: AstrologicalSubject, prog_year: int, prog_month: int, prog_day: int) -> AstrologicalSubject:
    """
    Calculates the secondary progressed chart for a specific date.
    Secondary progression follows the "one day = one year" principle.

    Args:
        natal_subject (AstrologicalSubject): Natal chart AstrologicalSubject.
        prog_year (int): Year for which to calculate the progression.
        prog_month (int): Month for which to calculate the progression.
        prog_day (int): Day for which to calculate the progression.

    Returns:
        AstrologicalSubject: Progressed chart AstrologicalSubject.
    """
    # Calculate the year difference between natal date and progression date
    # Natal date
    natal_date = datetime(
        natal_subject.year, 
        natal_subject.month, 
        natal_subject.day, 
        natal_subject.hour, 
        natal_subject.minute
    )
    
    # Target progression date
    prog_date = datetime(prog_year, prog_month, prog_day)

    # Calculate day difference (1 day = 1 year in secondary progression)
    days_diff = (prog_date.year - natal_date.year) + (prog_date.month - natal_date.month) / 12 + (prog_date.day - natal_date.day) / 365.25

    # Calculate the progressed date
    progressed_date = natal_date + timedelta(days=days_diff)

    # Create a new AstrologicalSubject with the progressed date
    progressed_subject = AstrologicalSubject(
        name=f"{natal_subject.name}_Progressed",
        year=progressed_date.year,
        month=progressed_date.month,
        day=progressed_date.day,
        hour=progressed_date.hour,
        minute=progressed_date.minute,
        city=natal_subject.city,
        lng=natal_subject.lng,
        lat=natal_subject.lat,
        tz_str=natal_subject.tz_str,
        houses_system_identifier=natal_subject.houses_system_identifier
    )
    
    return progressed_subject

def get_return_chart(
    natal_subject: AstrologicalSubject, 
    return_year: int, 
    return_month: Optional[int] = None,
    return_type: Literal["solar", "lunar"] = "solar",
    location_longitude: Optional[float] = None,
    location_latitude: Optional[float] = None,
    location_tz_str: Optional[str] = None
) -> AstrologicalSubject:
    """
    Calculates a solar or lunar return chart.

    Args:
        natal_subject (AstrologicalSubject): Natal chart AstrologicalSubject.
        return_year (int): Year for which to calculate the return.
        return_month (Optional[int]): Month for which to calculate the return (lunar return only).
        return_type (str): Return type, "solar" or "lunar".
        location_longitude (Optional[float]): Longitude of the return location.
        location_latitude (Optional[float]): Latitude of the return location.
        location_tz_str (Optional[str]): Timezone of the return location.

    Returns:
        AstrologicalSubject: Return chart AstrologicalSubject.
    """
    # Set the location for the return
    location_lng = location_longitude if location_longitude is not None else natal_subject.lng
    location_lat = location_latitude if location_latitude is not None else natal_subject.lat
    location_tz = location_tz_str if location_tz_str is not None else natal_subject.tz_str
    
    if return_type == "solar":
        # For solar return, find the exact moment the Sun returns
        # to the same zodiacal position as in the natal chart

        # Get natal Sun position
        natal_sun_position = natal_subject.sun.abs_pos

        # Create an approximate date for the solar return (near birthday)
        natal_month = natal_subject.month
        natal_day = natal_subject.day

        # Start date for the search
        start_date = datetime(return_year, natal_month, natal_day)

        # Adjust to 5 days before birthday
        start_date = start_date - timedelta(days=5)

        # Create a chart for this initial date
        temp_subject = AstrologicalSubject(
            name=f"{natal_subject.name}_SolarReturn",
            year=start_date.year,
            month=start_date.month,
            day=start_date.day,
            hour=12,  # Noon as initial hour
            minute=0,
            city="",
            lng=location_lng,
            lat=location_lat,
            tz_str=location_tz
        )
        
        # Iteratively search for the solar return date
        for i in range(12):  # Check up to 12 days from the initial date
            temp_date = start_date + timedelta(days=i)
            temp_subject = AstrologicalSubject(
                name=f"{natal_subject.name}_SolarReturn",
                year=temp_date.year,
                month=temp_date.month,
                day=temp_date.day,
                hour=12,  # Noon as initial hour
                minute=0,
                city="",
                lng=location_lng,
                lat=location_lat,
                tz_str=location_tz
            )
            
            # Check Sun position
            current_sun_position = temp_subject.sun.abs_pos

            # If current position is past natal, the return occurred between this day and the previous
            if current_sun_position > natal_sun_position and i > 0:
                break

        # Refine to the exact hour of return
        for hour in range(24):
            temp_subject = AstrologicalSubject(
                name=f"{natal_subject.name}_SolarReturn",
                year=temp_date.year,
                month=temp_date.month,
                day=temp_date.day,
                hour=hour,
                minute=0,
                city="",
                lng=location_lng,
                lat=location_lat,
                tz_str=location_tz
            )
            
            current_sun_position = temp_subject.sun.abs_pos
            
            # If close enough to natal position, refine to exact minute
            if abs(current_sun_position - natal_sun_position) < 1.0:
                # Refine to exact minute
                for minute in range(0, 60, 5):
                    temp_subject = AstrologicalSubject(
                        name=f"{natal_subject.name}_SolarReturn",
                        year=temp_date.year,
                        month=temp_date.month,
                        day=temp_date.day,
                        hour=hour,
                        minute=minute,
                        city="",
                        lng=location_lng,
                        lat=location_lat,
                        tz_str=location_tz
                    )
                    
                    current_sun_position = temp_subject.sun.abs_pos
                    
                    # Check if we found the exact position
                    if abs(current_sun_position - natal_sun_position) < 0.1:
                        return temp_subject

                # Return closest match if exact position not found
                return temp_subject

        # Return noon chart if no exact hour found
        return temp_subject

    elif return_type == "lunar":
        # For lunar return, find the exact moment the Moon returns
        # to the same zodiacal position as in the natal chart

        # Get natal Moon position
        natal_moon_position = natal_subject.moon.abs_pos

        # If month not specified, use current month
        if return_month is None:
            return_month = datetime.now().month

        # Start date for search (first day of the month)
        start_date = datetime(return_year, return_month, 1)

        # Check each day of the month for the lunar return
        for day in range(1, 29):  # Moon completes a cycle in approximately 27.3 days
            temp_date = start_date + timedelta(days=day)
            
            temp_subject = AstrologicalSubject(
                name=f"{natal_subject.name}_LunarReturn",
                year=temp_date.year,
                month=temp_date.month,
                day=temp_date.day,
                hour=12,  # Noon as initial hour
                minute=0,
                city="",
                lng=location_lng,
                lat=location_lat,
                tz_str=location_tz
            )
            
            # Check Moon position
            current_moon_position = temp_subject.moon.abs_pos

            # If close to natal position, refine to exact hour
            if abs(current_moon_position - natal_moon_position) < 15:
                # Refine to exact hour
                for hour in range(24):
                    temp_subject = AstrologicalSubject(
                        name=f"{natal_subject.name}_LunarReturn",
                        year=temp_date.year,
                        month=temp_date.month,
                        day=temp_date.day,
                        hour=hour,
                        minute=0,
                        city="",
                        lng=location_lng,
                        lat=location_lat,
                        tz_str=location_tz
                    )
                    
                    current_moon_position = temp_subject.moon.abs_pos
                    
                    # If close enough, refine to exact minute
                    if abs(current_moon_position - natal_moon_position) < 5:
                        # Refine to exact minute
                        for minute in range(0, 60, 5):
                            temp_subject = AstrologicalSubject(
                                name=f"{natal_subject.name}_LunarReturn",
                                year=temp_date.year,
                                month=temp_date.month,
                                day=temp_date.day,
                                hour=hour,
                                minute=minute,
                                city="",
                                lng=location_lng,
                                lat=location_lat,
                                tz_str=location_tz
                            )
                            
                            current_moon_position = temp_subject.moon.abs_pos
                            
                            # Check if we found the exact position
                            if abs(current_moon_position - natal_moon_position) < 0.5:
                                return temp_subject

                        # Return closest match if exact position not found
                        return temp_subject

                # Return noon chart if no exact hour found
                return temp_subject

        # If lunar return not found in specified month, use first day of month
        return AstrologicalSubject(
            name=f"{natal_subject.name}_LunarReturn",
            year=return_year,
            month=return_month,
            day=1,
            hour=12,
            minute=0,
            city="",
            lng=location_lng,
            lat=location_lat,
            tz_str=location_tz
        )
    
    else:
        raise ValueError(f"Unsupported return type: {return_type}")

def get_return_chart_cached(
    natal_subject: AstrologicalSubject, 
    return_year: int, 
    return_month: Optional[int] = None,
    return_type: Literal["solar", "lunar"] = "solar",
    location_longitude: Optional[float] = None,
    location_latitude: Optional[float] = None,
    location_tz_str: Optional[str] = None
) -> AstrologicalSubject:
    """
    Calculates a solar or lunar return chart with caching.

    Args:
        natal_subject (AstrologicalSubject): Natal chart AstrologicalSubject.
        return_year (int): Year for which to calculate the return.
        return_month (Optional[int]): Month for which to calculate the return (lunar return only).
        return_type (str): Return type, "solar" or "lunar".
        location_longitude (Optional[float]): Longitude of the return location.
        location_latitude (Optional[float]): Latitude of the return location.
        location_tz_str (Optional[str]): Timezone of the return location.

    Returns:
        AstrologicalSubject: Return chart AstrologicalSubject.
    """
    # Generate cache key
    cache_key = get_cache_key(
        f"{return_type}_return",
        natal_name=natal_subject.name,
        natal_year=natal_subject.year,
        natal_month=natal_subject.month,
        natal_day=natal_subject.day,
        natal_hour=natal_subject.hour,
        natal_minute=natal_subject.minute,
        return_year=return_year,
        return_month=return_month,
        location_longitude=location_longitude or natal_subject.lng,
        location_latitude=location_latitude or natal_subject.lat,
        location_tz_str=location_tz_str or natal_subject.tz_str
    )
    
    # Check if cached
    cached_subject = get_from_cache(cache_key)
    if cached_subject is not None:
        return cached_subject

    # Not cached — calculate
    subject = get_return_chart(
        natal_subject=natal_subject,
        return_year=return_year,
        return_month=return_month,
        return_type=return_type,
        location_longitude=location_longitude,
        location_latitude=location_latitude,
        location_tz_str=location_tz_str
    )
    
    # Save to cache
    save_to_cache(cache_key, subject)

    return subject

def get_progressed_chart_cached(
    natal_subject: AstrologicalSubject, 
    prog_year: int, 
    prog_month: int, 
    prog_day: int
) -> AstrologicalSubject:
    """
    Calculates the secondary progressed chart with caching.

    Args:
        natal_subject (AstrologicalSubject): Natal chart AstrologicalSubject.
        prog_year (int): Year for which to calculate the progression.
        prog_month (int): Month for which to calculate the progression.
        prog_day (int): Day for which to calculate the progression.

    Returns:
        AstrologicalSubject: Progressed chart AstrologicalSubject.
    """
    # Generate cache key
    cache_key = get_cache_key(
        "progressed_chart",
        natal_name=natal_subject.name,
        natal_year=natal_subject.year,
        natal_month=natal_subject.month,
        natal_day=natal_subject.day,
        natal_hour=natal_subject.hour,
        natal_minute=natal_subject.minute,
        prog_year=prog_year,
        prog_month=prog_month,
        prog_day=prog_day
    )
    
    # Check if cached
    cached_subject = get_from_cache(cache_key)
    if cached_subject is not None:
        return cached_subject

    # Not cached — calculate
    subject = get_progressed_chart(
        natal_subject=natal_subject,
        prog_year=prog_year,
        prog_month=prog_month,
        prog_day=prog_day
    )
    
    # Save to cache
    save_to_cache(cache_key, subject)

    return subject

def calculate_solar_arc_directions(
    natal_subject: AstrologicalSubject, 
    direction_date: datetime
) -> Tuple[float, Dict[str, float]]:
    """
    Calculates solar arc directions.

    Args:
        natal_subject (AstrologicalSubject): Natal chart AstrologicalSubject.
        direction_date (datetime): Date for which to calculate the directions.

    Returns:
        Tuple[float, Dict[str, float]]: Arc value in degrees and directed planet positions.
    """
    # Natal date
    natal_date = datetime(
        natal_subject.year, 
        natal_subject.month, 
        natal_subject.day, 
        natal_subject.hour, 
        natal_subject.minute
    )
    
    # Calculate difference in decimal years
    years_diff = (direction_date.year - natal_date.year) + \
                 (direction_date.month - natal_date.month) / 12 + \
                 (direction_date.day - natal_date.day) / 365.25
    
    # Calculate solar arc (approximately 1 degree per year)
    solar_arc = years_diff

    # Get natal planet positions (lowercase keys)
    natal_positions = {}
    for planet_name in natal_subject.planets_names_list:
        attr = planet_name.lower()
        if hasattr(natal_subject, attr):
            natal_positions[attr] = getattr(natal_subject, attr).abs_pos

    # Calculate directed positions (add solar arc)
    directed_positions = {}
    for planet_key, position in natal_positions.items():
        directed_positions[planet_key] = (position + solar_arc) % 360
    
    return solar_arc, directed_positions
