"""
Router for solar and lunar return endpoints.

This module contains endpoints for calculating solar and lunar returns.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional, Any

from ..schemas.models import ReturnRequest, ReturnResponse
from ..core.calculations import (
    create_astrological_subject,
    get_planet_data,
    get_houses_data,
    get_return_chart,
    get_aspects_data,
    get_aspects_between_subjects
)
from ..core.utils import validate_date, validate_timezone, validate_time
from ..interpretations.text_search import get_planet_interpretation
router = APIRouter(
    prefix="/api",
    tags=["Returns"],
)

@router.post("/solar-return", response_model=ReturnResponse)
async def calculate_solar_return(request: ReturnRequest):
    """
    Calculates the solar return for a specific year.

    Args:
        request (ReturnRequest): Data for the solar return calculation.

    Returns:
        ReturnResponse: Calculated solar return data.

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

        # Validate return year
        return_year = request.return_year
        if return_year < 1900 or return_year > 2100:
            raise HTTPException(status_code=400, detail="Return year out of valid range (1900-2100)")

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

        # Calculate solar return
        return_subject = get_return_chart(
            natal_subject,
            return_year,
            return_type="solar",
            location_longitude=request.location_longitude if request.location_longitude is not None else natal.longitude,
            location_latitude=request.location_latitude if request.location_latitude is not None else natal.latitude,
            location_tz_str=request.location_tz_str if request.location_tz_str is not None else natal.tz_str
        )

        # Get return planet data
        return_planets = get_planet_data(return_subject, request.language)

        # Get return house data
        return_houses = get_houses_data(return_subject, request.language)

        # Get aspects between return and natal planets
        aspects = []
        if request.include_natal_comparison:
            aspects = get_aspects_between_subjects(
                return_subject,
                natal_subject,
                subject1_owner="return",
                subject2_owner="natal",
                language=request.language
            )

        # Get interpretations if requested
        interpretations = None
        if request.include_interpretations:
            interpretations = {
                "planets": {},
                "houses": {},
                "aspects": []
            }

            # Return planet interpretations
            for planet_key, planet_data in return_planets.items():
                planet_name = planet_data.name
                sign = planet_data.sign
                house = planet_data.house

                interp = get_planet_interpretation(planet_name, sign, house, request.language)
                if interp:
                    interpretations["planets"][planet_key] = interp

            # House interpretations
            for house_num, house_data in return_houses.items():
                sign = house_data.sign

                interp = get_planet_interpretation(f"House {house_num}", sign, 0, request.language)
                if interp:
                    interpretations["houses"][house_num] = interp

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

        response = ReturnResponse(
            input_data=request,
            return_planets=return_planets,
            return_houses=return_houses,
            return_date=return_subject.iso_formatted_utc_datetime[:19].replace("T", " "),
            aspects=aspects,
            house_system=natal.house_system,
            interpretations=interpretations
        )

        return response

    except Exception as e:
        print(f"Error calculating solar return: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating solar return: {str(e)}"
        )

@router.post("/lunar-return", response_model=ReturnResponse)
async def calculate_lunar_return(request: ReturnRequest):
    """
    Calculates the nearest lunar return to a specific date.

    Args:
        request (ReturnRequest): Data for the lunar return calculation.

    Returns:
        ReturnResponse: Calculated lunar return data.

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

        # Validate return year and month
        return_year = request.return_year
        return_month = request.return_month
        if return_year < 1900 or return_year > 2100:
            raise HTTPException(status_code=400, detail="Return year out of valid range (1900-2100)")

        if return_month is not None and (return_month < 1 or return_month > 12):
            raise HTTPException(status_code=400, detail="Invalid return month (1-12)")

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

        # Calculate lunar return
        return_subject = get_return_chart(
            natal_subject,
            return_year,
            return_month=return_month,
            return_type="lunar",
            location_longitude=request.location_longitude if request.location_longitude is not None else natal.longitude,
            location_latitude=request.location_latitude if request.location_latitude is not None else natal.latitude,
            location_tz_str=request.location_tz_str if request.location_tz_str is not None else natal.tz_str
        )

        # Get return planet data
        return_planets = get_planet_data(return_subject, request.language)

        # Get return house data
        return_houses = get_houses_data(return_subject, request.language)

        # Get aspects between return and natal planets
        aspects = []
        if request.include_natal_comparison:
            aspects = get_aspects_between_subjects(
                return_subject,
                natal_subject,
                subject1_owner="return",
                subject2_owner="natal",
                language=request.language
            )

        # Get interpretations if requested
        interpretations = None
        if request.include_interpretations:
            interpretations = {
                "planets": {},
                "houses": {},
                "aspects": []
            }

            # Return planet interpretations
            for planet_key, planet_data in return_planets.items():
                planet_name = planet_data.name
                sign = planet_data.sign
                house = planet_data.house

                interp = get_planet_interpretation(planet_name, sign, house, request.language)
                if interp:
                    interpretations["planets"][planet_key] = interp

            # House interpretations
            for house_num, house_data in return_houses.items():
                sign = house_data.sign

                interp = get_planet_interpretation(f"House {house_num}", sign, 0, request.language)
                if interp:
                    interpretations["houses"][house_num] = interp

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

        response = ReturnResponse(
            input_data=request,
            return_planets=return_planets,
            return_houses=return_houses,
            return_date=return_subject.iso_formatted_utc_datetime[:19].replace("T", " "),
            aspects=aspects,
            house_system=natal.house_system,
            interpretations=interpretations
        )

        return response

    except Exception as e:
        print(f"Error calculating lunar return: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating lunar return: {str(e)}"
        )
