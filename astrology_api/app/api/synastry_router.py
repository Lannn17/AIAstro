"""
Router for synastry (natal chart comparison) endpoints.

This module contains endpoints for calculating synastry between two natal charts.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional

from ..schemas.models import SynastryRequest, SynastryResponse, HouseSystemType, LanguageType
from ..core.calculations import (
    create_astrological_subject,
    get_planet_data,
    get_synastry_aspects_data
)
from ..core.utils import validate_date, validate_timezone, validate_time
from ..interpretations.text_search import get_aspect_interpretation
router = APIRouter(
    prefix="/api",
    tags=["Synastry"],
)

@router.post("/synastry", response_model=SynastryResponse)
async def calculate_synastry(request: SynastryRequest):
    """
    Calculates synastry (comparison) between two natal charts.

    Args:
        request (SynastryRequest): Data for the synastry calculation.

    Returns:
        SynastryResponse: Calculated synastry data.

    Raises:
        HTTPException: If an error occurs during calculation.
    """
    try:
        # Validate first chart input data
        chart1 = request.chart1
        if not validate_date(chart1.year, chart1.month, chart1.day):
            raise HTTPException(status_code=400, detail="Invalid date for first chart")

        if not validate_time(chart1.hour, chart1.minute):
            raise HTTPException(status_code=400, detail="Invalid time for first chart")

        if not validate_timezone(chart1.tz_str):
            raise HTTPException(status_code=400, detail="Invalid timezone for first chart")

        # Validate second chart input data
        chart2 = request.chart2
        if not validate_date(chart2.year, chart2.month, chart2.day):
            raise HTTPException(status_code=400, detail="Invalid date for second chart")

        if not validate_time(chart2.hour, chart2.minute):
            raise HTTPException(status_code=400, detail="Invalid time for second chart")

        if not validate_timezone(chart2.tz_str):
            raise HTTPException(status_code=400, detail="Invalid timezone for second chart")

        # Use defaults if not provided
        house_system1: HouseSystemType = chart1.house_system or "Placidus"
        house_system2: HouseSystemType = chart2.house_system or "Placidus"
        language: LanguageType = request.language or "pt"

        # Create AstrologicalSubject objects
        subject1 = create_astrological_subject(
            name=chart1.name if chart1.name else "Chart1",
            year=chart1.year,
            month=chart1.month,
            day=chart1.day,
            hour=chart1.hour,
            minute=chart1.minute,
            longitude=chart1.longitude,
            latitude=chart1.latitude,
            tz_str=chart1.tz_str,
            house_system=house_system1
        )

        subject2 = create_astrological_subject(
            name=chart2.name if chart2.name else "Chart2",
            year=chart2.year,
            month=chart2.month,
            day=chart2.day,
            hour=chart2.hour,
            minute=chart2.minute,
            longitude=chart2.longitude,
            latitude=chart2.latitude,
            tz_str=chart2.tz_str,
            house_system=house_system2
        )

        # Get planet data for both charts
        planets1 = get_planet_data(subject1, language)
        planets2 = get_planet_data(subject2, language)

        # Get aspects between the two charts
        aspects = get_synastry_aspects_data(subject1, subject2, language)

        # Get aspect interpretations if requested
        interpretations = None
        if request.include_interpretations:
            interpretations = {
                "aspects": []
            }

            for aspect in aspects:
                p1_name = aspect.p1_name
                p2_name = aspect.p2_name
                aspect_name = aspect.aspect

                interp = get_aspect_interpretation(p1_name, p2_name, aspect_name, request.language)
                if interp:
                    interpretations["aspects"].append({
                        "p1": p1_name,
                        "p2": p2_name,
                        "aspect": aspect_name,
                        "interpretation": interp
                    })

        response = SynastryResponse(
            input_data=request,
            chart1_planets=planets1,
            chart2_planets=planets2,
            aspects=aspects,
            chart1_house_system=chart1.house_system,
            chart2_house_system=chart2.house_system,
            interpretations=interpretations
        )

        return response

    except Exception as e:
        print(f"Error calculating synastry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating synastry: {str(e)}"
        )
