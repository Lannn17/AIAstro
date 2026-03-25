"""
Pydantic models for the AstroAPI application.

This file contains the Pydantic models that define the structure
of API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Literal

# Literal types for house systems
HouseSystemType = Literal[
    "Placidus", "Koch", "Porphyrius", "Regiomontanus", "Campanus",
    "Equal", "Whole Sign", "Alcabitus", "Morinus", "Horizontal",
    "Topocentric", "Vehlow"
]

# Literal types for supported languages
LanguageType = Literal["pt", "en", "es", "zh", "ja"]

# Friendly name to Kerykeion code mapping
HOUSE_SYSTEM_MAP = {
    "Placidus": "P",
    "Koch": "K",
    "Porphyrius": "O",
    "Regiomontanus": "R",
    "Campanus": "C",
    "Equal": "A",  # or "E"
    "Whole Sign": "W",
    "Alcabitus": "B",
    "Morinus": "M",
    "Horizontal": "H",
    "Topocentric": "T",
    "Vehlow": "V"
}

# Request models

class NatalChartRequest(BaseModel):
    """
    Request model for natal chart calculation.
    """
    name: Optional[str] = Field(None, description="Name of the person or event")
    year: int = Field(..., description="Birth year")
    month: int = Field(..., ge=1, le=12, description="Birth month (1-12)")
    day: int = Field(..., ge=1, le=31, description="Birth day (1-31)")
    hour: int = Field(..., ge=0, le=23, description="Birth hour (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Birth minute (0-59)")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude of birth location")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of birth location")
    tz_str: str = Field(..., description="Timezone string (e.g. 'America/Sao_Paulo')")
    house_system: Optional[HouseSystemType] = Field("Placidus", description="House system to use")
    language: Optional[LanguageType] = Field("pt", description="Language for text in the response")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class TransitRequest(BaseModel):
    """
    Request model for transit calculation.
    """
    year: int = Field(..., description="Transit year")
    month: int = Field(..., ge=1, le=12, description="Transit month (1-12)")
    day: int = Field(..., ge=1, le=31, description="Transit day (1-31)")
    hour: int = Field(..., ge=0, le=23, description="Transit hour (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Transit minute (0-59)")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude of transit location")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of transit location")
    tz_str: str = Field(..., description="Timezone string (e.g. 'America/Sao_Paulo')")
    house_system: Optional[HouseSystemType] = Field("Placidus", description="House system to use")
    language: Optional[LanguageType] = Field("pt", description="Language for text in the response")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class TransitsToNatalRequest(BaseModel):
    """
    Request model for transits to natal chart.
    """
    natal: NatalChartRequest = Field(..., description="Natal chart data")
    transit: TransitRequest = Field(..., description="Transit data")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class SVGChartRequest(BaseModel):
    """
    Request model for SVG chart generation.
    """
    natal_chart: NatalChartRequest = Field(..., description="Natal chart data")
    transit_chart: Optional[TransitRequest] = Field(None, description="Transit data (optional)")
    chart_type: Literal["natal", "transit", "combined"] = Field(
        "natal",
        description="Chart type: 'natal' for natal only, 'transit' for transit only, 'combined' for natal with transits"
    )
    show_aspects: bool = Field(
        True,
        description="Whether to show aspect lines on the chart"
    )
    language: LanguageType = Field(
        "pt",
        description="Language for text on the chart"
    )
    theme: Literal["light", "dark"] = Field(
        "light",
        description="Color theme for the chart"
    )

# Response component models

class PlanetData(BaseModel):
    """
    Model for planet data.
    """
    name: str = Field(..., description="Planet name")
    name_original: Optional[str] = Field(None, description="Original planet name in English")
    longitude: float = Field(..., description="Ecliptic longitude of the planet")
    latitude: Optional[float] = Field(0.0, description="Ecliptic latitude of the planet")
    sign: str = Field(..., description="Zodiac sign of the planet")
    sign_original: Optional[str] = Field(None, description="Original sign name in English")
    sign_num: int = Field(..., description="Sign number (1-12)")
    house: int = Field(..., description="Astrological house of the planet (1-12)")
    retrograde: bool = Field(..., description="Whether the planet is retrograde")
    speed: Optional[float] = Field(0.0, description="Planet speed")

class HouseCuspData(BaseModel):
    """
    Model for house cusp data.
    """
    number: int = Field(..., description="House number (1-12)")
    sign: str = Field(..., description="Zodiac sign of the cusp")
    sign_original: Optional[str] = Field(None, description="Original sign name in English")
    sign_num: int = Field(..., description="Sign number (1-12)")
    longitude: float = Field(..., description="Ecliptic longitude of the cusp")

class AspectData(BaseModel):
    """
    Model for aspect data.
    """
    p1_name: str = Field(..., description="Name of the first planet/point")
    p1_name_original: Optional[str] = Field(None, description="Original name of the first planet/point in English")
    p1_owner: str = Field(..., description="Owner of the first planet/point (natal/transit)")
    p2_name: str = Field(..., description="Name of the second planet/point")
    p2_name_original: Optional[str] = Field(None, description="Original name of the second planet/point in English")
    p2_owner: str = Field(..., description="Owner of the second planet/point (natal/transit)")
    aspect: str = Field(..., description="Aspect name")
    aspect_original: Optional[str] = Field(None, description="Original aspect name in English")
    orbit: float = Field(..., description="Aspect orb")
    aspect_degrees: float = Field(..., description="Aspect degrees")
    diff: float = Field(..., description="Degree difference")
    applying: bool = Field(..., description="Whether the aspect is applying (true) or separating (false)")
    direction: Optional[str] = Field(None, description="p1_to_p2 or p2_to_p1")
    double_whammy: bool = Field(False, description="True if reciprocal aspect exists")

# Response models

class NatalChartResponse(BaseModel):
    """
    Response model for natal chart.
    """
    input_data: NatalChartRequest = Field(..., description="Request input data")
    planets: Dict[str, PlanetData] = Field(..., description="Planet data")
    houses: Dict[str, HouseCuspData] = Field(..., description="House data")
    ascendant: HouseCuspData = Field(..., description="Ascendant data")
    midheaven: HouseCuspData = Field(..., description="Midheaven data")
    aspects: List[AspectData] = Field(default_factory=list, description="Aspects between planets")
    house_system: HouseSystemType = Field(..., description="House system used")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")

class TransitResponse(BaseModel):
    """
    Response model for transits.
    """
    input_data: TransitRequest = Field(..., description="Request input data")
    planets: Dict[str, PlanetData] = Field(..., description="Transit planet data")
    house_system: HouseSystemType = Field(..., description="House system used")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")

class TransitsToNatalResponse(BaseModel):
    """
    Response model for transits to natal chart.
    """
    input_data: TransitsToNatalRequest = Field(..., description="Request input data")
    natal_planets: Dict[str, PlanetData] = Field(..., description="Natal planet data")
    transit_planets: Dict[str, PlanetData] = Field(..., description="Transit planet data")
    aspects: List[AspectData] = Field(default_factory=list, description="Aspects between transit and natal planets")
    natal_house_system: HouseSystemType = Field(..., description="House system used for the natal chart")
    transit_house_system: HouseSystemType = Field(..., description="House system used for transits")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")

class SVGChartResponse(BaseModel):
    """
    Response model for SVG chart.
    """
    svg_image: str = Field(..., description="SVG content of the chart")

class SVGChartBase64Response(BaseModel):
    """
    Response model for Base64-encoded SVG chart.
    """
    svg_base64: str = Field(..., description="Base64-encoded SVG content")
    data_uri: str = Field(..., description="Base64 SVG data URI")

class InterpretationResponse(BaseModel):
    """
    Response model for interpretations.
    """
    interpretations: Dict[str, Any] = Field(..., description="Textual interpretations")

class SynastryRequest(BaseModel):
    """
    Request model for synastry (natal chart comparison).
    """
    chart1: NatalChartRequest = Field(..., description="First natal chart data")
    chart2: NatalChartRequest = Field(..., description="Second natal chart data")
    language: Optional[LanguageType] = Field("pt", description="Language for text in the response")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class SynastryResponse(BaseModel):
    """
    Response model for synastry.
    """
    input_data: SynastryRequest = Field(..., description="Request input data")
    chart1_planets: Dict[str, PlanetData] = Field(..., description="Planet data from the first chart")
    chart2_planets: Dict[str, PlanetData] = Field(..., description="Planet data from the second chart")
    aspects: List[AspectData] = Field(default_factory=list, description="Aspects between planets of both charts")
    chart1_house_system: HouseSystemType = Field(..., description="House system used for the first chart")
    chart2_house_system: HouseSystemType = Field(..., description="House system used for the second chart")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")

class ProgressionDateRequest(BaseModel):
    """
    Model for progression date data.
    """
    year: int = Field(..., description="Progression year")
    month: int = Field(..., ge=1, le=12, description="Progression month (1-12)")
    day: int = Field(..., ge=1, le=31, description="Progression day (1-31)")

class ProgressionRequest(BaseModel):
    """
    Request model for secondary progressions.
    """
    natal_chart: NatalChartRequest = Field(..., description="Natal chart data")
    progression_date: ProgressionDateRequest = Field(..., description="Date for the progression")
    include_natal_comparison: bool = Field(True, description="Whether to include comparison with natal chart")
    language: Optional[LanguageType] = Field("pt", description="Language for text in the response")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class ProgressionResponse(BaseModel):
    """
    Response model for secondary progressions.
    """
    input_data: ProgressionRequest = Field(..., description="Request input data")
    progressed_planets: Dict[str, PlanetData] = Field(..., description="Progressed planet data")
    natal_houses: Dict[str, HouseCuspData] = Field(..., description="Natal house data")
    aspects: List[AspectData] = Field(default_factory=list, description="Aspects between progressed and natal planets")
    house_system: HouseSystemType = Field(..., description="House system used")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")

class ReturnRequest(BaseModel):
    """
    Request model for solar or lunar returns.
    """
    natal_chart: NatalChartRequest = Field(..., description="Natal chart data")
    return_year: int = Field(..., description="Year for the return")
    return_month: Optional[int] = Field(None, ge=1, le=12, description="Month for the return (used only for lunar return)")
    location_longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude of return location (if different from birth location)")
    location_latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude of return location (if different from birth location)")
    location_tz_str: Optional[str] = Field(None, description="Timezone string for the return location (if different from birth location)")
    include_natal_comparison: bool = Field(True, description="Whether to include comparison with natal chart")
    language: Optional[LanguageType] = Field("pt", description="Language for text in the response")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class ReturnResponse(BaseModel):
    """
    Response model for solar or lunar returns.
    """
    input_data: ReturnRequest = Field(..., description="Request input data")
    return_planets: Dict[str, PlanetData] = Field(..., description="Return chart planet data")
    return_houses: Dict[str, HouseCuspData] = Field(..., description="Return chart house data")
    return_date: str = Field(..., description="Exact date and time of the return")
    aspects: List[AspectData] = Field(default_factory=list, description="Aspects between return and natal planets")
    house_system: HouseSystemType = Field(..., description="House system used")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")

class DirectionRequest(BaseModel):
    """
    Request model for solar arc directions.
    """
    natal_chart: NatalChartRequest = Field(..., description="Natal chart data")
    direction_date: ProgressionDateRequest = Field(..., description="Date for the direction")
    direction_type: Literal["solar_arc", "primary"] = Field("solar_arc", description="Direction type")
    include_natal_comparison: bool = Field(True, description="Whether to include comparison with natal chart")
    language: Optional[LanguageType] = Field("pt", description="Language for text in the response")
    include_interpretations: bool = Field(False, description="Whether to include textual interpretations in the response")

class DirectionResponse(BaseModel):
    """
    Response model for solar arc directions.
    """
    input_data: DirectionRequest = Field(..., description="Request input data")
    directed_planets: Dict[str, PlanetData] = Field(..., description="Directed planet data")
    natal_houses: Dict[str, HouseCuspData] = Field(..., description="Natal house data")
    direction_value: float = Field(..., description="Direction value in degrees")
    aspects: List[AspectData] = Field(default_factory=list, description="Aspects between directed and natal planets")
    house_system: HouseSystemType = Field(..., description="House system used")
    interpretations: Optional[Dict[str, Any]] = Field(None, description="Textual interpretations (optional)")
