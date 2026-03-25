"""
Router for astrological progression endpoints.

This module contains endpoints for calculating secondary progressions.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional, Any

from ..schemas.models import ProgressionRequest, ProgressionResponse
from ..core.calculations import (
    create_astrological_subject,
    get_planet_data,
    get_houses_data,
    get_progressed_chart,
    get_aspects_data,
    get_aspects_between_subjects
)
from ..core.utils import validate_date, validate_timezone, validate_time
from ..interpretations.text_search import get_planet_interpretation
router = APIRouter(
    prefix="/api",
    tags=["Progressions"],
)

@router.post("/progressions", response_model=ProgressionResponse)
async def calculate_progressions(request: ProgressionRequest):
    """
    Calculates secondary progressions for a natal chart.

    Args:
        request (ProgressionRequest): Data for the progression calculation.

    Returns:
        ProgressionResponse: Calculated progression data.

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

        # Validate progression date
        prog_date = request.progression_date
        if not validate_date(prog_date.year, prog_date.month, prog_date.day):
            raise HTTPException(status_code=400, detail="Invalid progression date")

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
            house_system=natal.house_system
        )

        # Calculate progressions
        progressed_subject = get_progressed_chart(
            natal_subject,
            prog_date.year,
            prog_date.month,
            prog_date.day
        )

        # Get progressed planet data
        progressed_planets = get_planet_data(progressed_subject, request.language)

        # Get house data (using natal chart as reference)
        houses = get_houses_data(natal_subject, request.language)

        # Get aspects between natal and progressed planets
        aspects = []
        if request.include_natal_comparison:
            natal_planets = get_planet_data(natal_subject, request.language)

            aspects = get_aspects_between_subjects(
                progressed_subject,
                natal_subject,
                subject1_owner="progressed",
                subject2_owner="natal",
                language=request.language
            )

        # Get interpretations if requested
        interpretations = None
        if request.include_interpretations:
            interpretations = {
                "planets": {},
                "aspects": []
            }

            # Progressed planet interpretations
            for planet_key, planet_data in progressed_planets.items():
                planet_name = planet_data.name
                sign = planet_data.sign
                house = planet_data.house

                interp = get_planet_interpretation(planet_name, sign, house, request.language)
                if interp:
                    interpretations["planets"][planet_key] = interp

            # Aspect interpretations
            for aspect in aspects:
                p1_name = aspect.p1_name
                p2_name = aspect.p2_name
                aspect_name = aspect.aspect

                interp = get_planet_interpretation(f"{p1_name} {aspect_name} {p2_name}", "", 0, request.language)
                if interp:
                    interpretations["aspects"].append({
                        "p1": p1_name,
                        "p2": p2_name,
                        "aspect": aspect_name,
                        "interpretation": interp
                    })

        response = ProgressionResponse(
            input_data=request,
            progressed_planets=progressed_planets,
            natal_houses=houses,
            aspects=aspects,
            house_system=natal.house_system,
            interpretations=interpretations
        )

        return response

    except Exception as e:
        print(f"Error calculating progressions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating progressions: {str(e)}"
        )
