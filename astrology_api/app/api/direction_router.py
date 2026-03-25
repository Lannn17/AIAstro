"""
Router for astrological direction endpoints.

This module contains endpoints for calculating solar arc and primary directions.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from ..schemas.models import DirectionRequest, DirectionResponse, HouseSystemType, LanguageType, AspectData
from ..core.calculations import (
    create_astrological_subject,
    get_planet_data,
    get_houses_data,
    calculate_solar_arc_directions,
    get_aspects_data
)
from ..core.utils import validate_date, validate_timezone, validate_time
from ..interpretations.text_search import get_planet_interpretation
from ..interpretations.translations import translate_sign, translate_aspect, translate_planet
router = APIRouter(
    prefix="/api",
    tags=["Directions"],
)

# Zodiac signs in order
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def get_sign_name(sign_num: int) -> str:
    """Returns the sign name based on its number (1-12)."""
    if 1 <= sign_num <= 12:
        return ZODIAC_SIGNS[sign_num - 1]
    return "Unknown"

def calculate_house_position(longitude: float, house_cusps: List[float]) -> int:
    """
    Calculates the astrological house for a given longitude.

    Args:
        longitude (float): Ecliptic longitude
        house_cusps (List[float]): List of house cusps

    Returns:
        int: House number (1-12)
    """
    # Normalize longitude to 0-360
    while longitude < 0:
        longitude += 360
    while longitude >= 360:
        longitude -= 360

    # Check each house
    for i in range(1, 13):
        cusp_start = house_cusps[i-1]
        cusp_end = house_cusps[i % 12]

        # Handle houses that cross 0°
        if cusp_end < cusp_start:
            if longitude >= cusp_start or longitude < cusp_end:
                return i
        else:
            if cusp_start <= longitude < cusp_end:
                return i

    return 1  # Default to first house if something goes wrong

@router.post("/solar-arc", response_model=DirectionResponse)
async def calculate_solar_arc(request: DirectionRequest):
    """
    Calculates solar arc directions for a natal chart.

    Args:
        request (DirectionRequest): Data for the direction calculation.

    Returns:
        DirectionResponse: Calculated direction data.

    Raises:
        HTTPException: If an error occurs during calculation.
    """
    try:
        # Validate natal chart input data
        natal = request.natal_chart
        if not validate_date(natal.year, natal.month, natal.day):
            raise HTTPException(status_code=400, detail="Invalid natal date")

        if not validate_time(natal.hour, natal.minute):
            raise HTTPException(status_code=400, detail="Invalid natal time")

        if not validate_timezone(natal.tz_str):
            raise HTTPException(status_code=400, detail="Invalid natal timezone")

        # Validate direction date
        direction_date = request.direction_date
        if not validate_date(direction_date.year, direction_date.month, direction_date.day):
            raise HTTPException(status_code=400, detail="Invalid direction date")

        # Use defaults for house_system and language if not provided
        house_system: HouseSystemType = natal.house_system or "Placidus"
        language: LanguageType = request.language or "pt"

        # Create AstrologicalSubject for the natal chart
        natal_subject = create_astrological_subject(
            name=natal.name if natal.name else "NatalChart",
            year=natal.year,
            month=natal.month,
            day=natal.day,
            hour=natal.hour,
            minute=natal.minute,
            longitude=natal.longitude,
            latitude=natal.latitude,
            tz_str=natal.tz_str,
            house_system=house_system
        )

        # Calculate solar arc directions
        direction_date_obj = datetime(
            direction_date.year,
            direction_date.month,
            direction_date.day
        )

        solar_arc, directed_positions = calculate_solar_arc_directions(natal_subject, direction_date_obj)

        # Get natal house data
        houses = get_houses_data(natal_subject, language)

        # Build directed planet positions
        directed_planets = {}

        for planet_name, planet_data in get_planet_data(natal_subject, language).items():
            # Copy natal planet data
            directed_planet = planet_data.model_copy()

            # Update longitude with directed position
            if planet_name in directed_positions:
                longitude = directed_positions[planet_name]
                directed_planet.longitude = longitude

                # Calculate new sign
                sign_num = int(longitude / 30) + 1
                sign = get_sign_name(sign_num)
                directed_planet.sign = translate_sign(sign, language)
                directed_planet.sign_original = sign
                directed_planet.sign_num = sign_num

                # Update house
                house_cusps = [float(h.longitude) for h in houses.values()]
                directed_planet.house = calculate_house_position(longitude, house_cusps)

            directed_planets[planet_name] = directed_planet

        # Calculate aspects between directed and natal planets
        natal_planets = get_planet_data(natal_subject, language)
        all_aspects = []

        for d_planet, d_data in directed_planets.items():
            for n_planet, n_data in natal_planets.items():
                # Calculate aspect
                diff = abs(d_data.longitude - n_data.longitude) % 360
                for aspect_angle, aspect_name in [(0, "Conjunction"), (60, "Sextile"),
                                              (90, "Square"), (120, "Trine"), (180, "Opposition")]:
                    orbit = abs(diff - aspect_angle)
                    if orbit <= 8:  # 8-degree orb
                        all_aspects.append(AspectData(
                            p1_name=translate_planet(d_planet, language),
                            p1_name_original=d_planet,
                            p1_owner="directed",
                            p2_name=translate_planet(n_planet, language),
                            p2_name_original=n_planet,
                            p2_owner="natal",
                            aspect=translate_aspect(aspect_name, language),
                            aspect_original=aspect_name,
                            orbit=round(orbit, 4),
                            aspect_degrees=float(aspect_angle),
                            diff=round(diff, 4),
                            applying=False
                        ))

        # Generate interpretations if requested
        interpretations = None
        if request.include_interpretations:
            interpretations = {
                "planets": {},
                "aspects": []
            }

            # Planet interpretations
            for planet_name, planet_data in directed_planets.items():
                interp = get_planet_interpretation(planet_name, planet_data.sign, planet_data.house, language)
                if interp:
                    interpretations["planets"][planet_name] = interp

            # Aspect interpretations
            for aspect in all_aspects:
                p1_name = aspect["p1_name_original"]
                p2_name = aspect["p2_name_original"]
                aspect_name = aspect["aspect_original"]
                interp = get_planet_interpretation(f"{p1_name} {aspect_name} {p2_name}", "", 0, language)
                if interp:
                    interpretations["aspects"].append({
                        "p1": p1_name,
                        "p2": p2_name,
                        "aspect": aspect_name,
                        "text": interp
                    })

        # Build response
        return DirectionResponse(
            input_data=request,
            directed_planets=directed_planets,
            natal_houses=houses,
            direction_value=solar_arc,
            aspects=all_aspects,
            house_system=house_system,
            interpretations=interpretations
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
