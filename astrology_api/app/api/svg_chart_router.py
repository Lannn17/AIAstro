"""
Router para os endpoints de geração de gráficos SVG.

Este módulo contém os endpoints relacionados à geração de gráficos astrológicos em formato SVG.
"""
from fastapi import APIRouter, HTTPException, Response
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from typing import Optional
import os
import tempfile

from ..schemas.models import (
    SVGChartRequest, SVGChartResponse, 
    SVGChartBase64Response
)
from ..core.calculations import create_astrological_subject
from ..core.utils import svg_to_base64, validate_date, validate_timezone, validate_time
router = APIRouter(
    prefix="/api",
    tags=["SVG Chart"],
)

@router.post("/svg_chart", response_class=Response)
async def generate_svg_chart(request: SVGChartRequest):
    """
    Gera um gráfico astrológico em formato SVG.
    
    Args:
        request (SVGChartRequest): Dados para a geração do gráfico SVG.
        
    Returns:
        Response: Conteúdo SVG do gráfico gerado.
        
    Raises:
        HTTPException: Se ocorrer um erro durante a geração do gráfico.
    """
    try:
        # Validar os dados de entrada do mapa natal
        natal_req = request.natal_chart
        if not validate_date(natal_req.year, natal_req.month, natal_req.day):
            raise HTTPException(status_code=400, detail="Data natal inválida")
        
        if not validate_time(natal_req.hour, natal_req.minute):
            raise HTTPException(status_code=400, detail="Hora natal inválida")
        
        if not validate_timezone(natal_req.tz_str):
            raise HTTPException(status_code=400, detail="Fuso horário natal inválido")
        
        # Validar os dados de entrada do mapa de trânsito, se fornecido
        transit_subject = None
        if request.transit_chart and request.chart_type in ["transit", "combined"]:
            transit_req = request.transit_chart
            if not validate_date(transit_req.year, transit_req.month, transit_req.day):
                raise HTTPException(status_code=400, detail="Data de trânsito inválida")
            
            if not validate_time(transit_req.hour, transit_req.minute):
                raise HTTPException(status_code=400, detail="Hora de trânsito inválida")
            
            if not validate_timezone(transit_req.tz_str):
                raise HTTPException(status_code=400, detail="Fuso horário de trânsito inválido")
            
            # Criar o objeto AstrologicalSubject para o mapa de trânsito
            transit_subject = create_astrological_subject(
                name="TransitChart",
                year=transit_req.year,
                month=transit_req.month,
                day=transit_req.day,
                hour=transit_req.hour,
                minute=transit_req.minute,
                longitude=transit_req.longitude,
                latitude=transit_req.latitude,
                tz_str=transit_req.tz_str,
                house_system=transit_req.house_system
            )
        
        # Criar o objeto AstrologicalSubject para o mapa natal
        natal_subject = create_astrological_subject(
            name=natal_req.name if natal_req.name else "NatalChart",
            year=natal_req.year,
            month=natal_req.month,
            day=natal_req.day,
            hour=natal_req.hour,
            minute=natal_req.minute,
            longitude=natal_req.longitude,
            latitude=natal_req.latitude,
            tz_str=natal_req.tz_str,
            house_system=natal_req.house_system
        )
        
        # Definir o tipo de gráfico para o Kerykeion
        chart_type = "Natal"
        if request.chart_type == "transit":
            chart_type = "Transit"
        elif request.chart_type == "combined":
            chart_type = "Composite"  # ou "Combined", dependendo da versão do Kerykeion
        
        # Criar um diretório temporário para salvar o SVG
        with tempfile.TemporaryDirectory() as temp_dir:
            kery_theme = "dark" if request.theme == "dark" else "light"
            lang_map = {"pt": "PT", "en": "EN", "es": "ES", "fr": "FR", "it": "IT", "de": "DE"}
            kery_lang = lang_map.get(request.language or "pt", "EN")

            chart_svg_generator = KerykeionChartSVG(
                natal_subject,
                chart_type=chart_type,
                second_obj=transit_subject,
                new_output_directory=temp_dir,
                theme=kery_theme,
                chart_language=kery_lang
            )
            chart_svg_generator.makeSVG()

            svg_files = [f for f in os.listdir(temp_dir) if f.endswith(".svg")]
            if not svg_files:
                raise HTTPException(status_code=500, detail="Arquivo SVG não encontrado")

            with open(os.path.join(temp_dir, svg_files[0]), 'r', encoding='utf-8') as f:
                svg_content = f.read()

            return Response(content=svg_content, media_type="image/svg+xml")
        
    except Exception as e:
        # Logar o erro
        print(f"Erro ao gerar gráfico SVG: {str(e)}")
        
        # Retornar erro ao cliente
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar gráfico SVG: {str(e)}"
        )

@router.post("/svg_chart_base64", response_model=SVGChartBase64Response)
async def generate_svg_chart_base64(request: SVGChartRequest):
    """
    Gera um gráfico astrológico em formato SVG e retorna a representação em Base64.
    
    Args:
        request (SVGChartRequest): Dados para a geração do gráfico SVG.
        
    Returns:
        SVGChartBase64Response: Conteúdo SVG do gráfico gerado em Base64 e como URI de dados.
        
    Raises:
        HTTPException: Se ocorrer um erro durante a geração do gráfico.
    """
    try:
        # Reutilizar o endpoint de geração de SVG
        svg_response = await generate_svg_chart(request)
        
        # Converter o conteúdo SVG para Base64
        svg_content = svg_response.body.decode("utf-8")
        base64_data = svg_to_base64(svg_content)
        
        # Retornar a resposta
        return SVGChartBase64Response(
            svg_base64=base64_data["svg_base64"],
            data_uri=base64_data["data_uri"]
        )
        
    except Exception as e:
        # Logar o erro
        print(f"Erro ao gerar gráfico SVG em Base64: {str(e)}")
        
        # Retornar erro ao cliente
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar gráfico SVG em Base64: {str(e)}"
        )
