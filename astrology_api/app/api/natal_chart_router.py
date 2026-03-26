"""
Router para os endpoints de mapa natal.

Este módulo contém os endpoints relacionados ao cálculo de mapas natais.
"""
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional
from pydantic import BaseModel

from ..schemas.models import NatalChartRequest, NatalChartResponse
from ..core.calculations import (
    create_astrological_subject,
    get_planet_data,
    get_houses_data,
    get_aspects_data
)
from ..core.utils import validate_date, validate_timezone, validate_time
router = APIRouter(
    prefix="/api",
    tags=["Natal Chart"],
)

@router.post("/natal_chart", response_model=NatalChartResponse)
async def calculate_natal_chart(request: NatalChartRequest):
    """
    Calcula um mapa natal com base nos dados fornecidos.
    
    Args:
        request (NatalChartRequest): Dados para o cálculo do mapa natal.
        
    Returns:
        NatalChartResponse: Dados do mapa natal calculado.
        
    Raises:
        HTTPException: Se ocorrer um erro durante o cálculo.
    """
    try:
        # Validar os dados de entrada
        if not validate_date(request.year, request.month, request.day):
            raise HTTPException(status_code=400, detail="Data inválida")
        
        if not validate_time(request.hour, request.minute):
            raise HTTPException(status_code=400, detail="Hora inválida")
        
        if not validate_timezone(request.tz_str):
            raise HTTPException(status_code=400, detail="Fuso horário inválido")
        
        # Criar o objeto AstrologicalSubject
        subject = create_astrological_subject(
            name=request.name if request.name else "NatalChart",
            year=request.year,
            month=request.month,
            day=request.day,
            hour=request.hour,
            minute=request.minute,
            longitude=request.longitude,
            latitude=request.latitude,
            tz_str=request.tz_str,
            house_system=request.house_system
        )
        
        # Obter os dados dos planetas
        planets = get_planet_data(subject, request.language)
        
        # Obter os dados das casas
        houses = get_houses_data(subject, request.language)
        
        # Obter os dados dos aspectos
        aspects = get_aspects_data(subject, request.language)
        
        # Criar a resposta
        response = NatalChartResponse(
            input_data=request,
            planets=planets,
            houses=houses,
            ascendant=houses["1"],
            midheaven=houses["10"],
            aspects=aspects,
            house_system=request.house_system,
            interpretations=None  # Implementação futura
        )
        
        return response
        
    except Exception as e:
        # Logar o erro
        print(f"Erro ao calcular mapa natal: {str(e)}")
        
        # Retornar erro ao cliente
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular mapa natal: {str(e)}"
        )



# ── 行星逐一解读 ──────────────────────────────────────────────────

class InterpretPlanetsRequest(BaseModel):
    natal_chart: Dict[str, Any]
    language: str = 'zh'
    chart_id: Optional[int] = None   # 已保存星盘的 ID，用于缓存
    cache_only: bool = False          # True = 只读缓存，未命中时返回空而非调 AI


@router.post("/interpret_planets")
async def interpret_planets(body: InterpretPlanetsRequest):
    """为本命盘每颗行星生成解读，并附综合概述。有 chart_id 时读写缓存。"""
    import hashlib, json as _json
    from ..db import db_get_planet_cache, db_save_planet_cache

    # 计算 chart_hash：基于决定星盘内容的输入参数
    input_data = body.natal_chart.get("input_data", {})
    hash_src = _json.dumps({
        k: input_data.get(k)
        for k in ("year","month","day","hour","minute","latitude","longitude","tz_str","house_system")
    }, sort_keys=True)
    chart_hash = hashlib.md5(hash_src.encode()).hexdigest()

    # 有 chart_id → 检查缓存
    if body.chart_id:
        cached = db_get_planet_cache(body.chart_id, chart_hash)
        if cached:
            return {"analyses": _json.loads(cached), "sources": [], "from_cache": True, "model_used": "cached"}

    # 只读缓存模式：未命中时返回空，不调 AI
    if body.cache_only:
        return {"analyses": None, "sources": [], "from_cache": False}

    try:
        import asyncio
        from ..rag import analyze_planets
        result = analyze_planets(body.natal_chart, body.language)
        analyses = result.get("analyses", {})
        sources  = result.get("sources", [])

        # 有 chart_id → 写入缓存（只缓存 analyses，不缓存 sources）
        if body.chart_id and analyses:
            db_save_planet_cache(body.chart_id, chart_hash, _json.dumps(analyses, ensure_ascii=False))

        # 异步写入 analytics
        from ..api.interpret_router import _log_analytics
        asc = body.natal_chart.get("ascendant", {})
        query = f"planets {asc.get('sign_original') or asc.get('sign', '')} natal chart"
        asyncio.create_task(_log_analytics(query, {"sources": sources}))

        return {"analyses": analyses, "sources": sources, "from_cache": False, "model_used": result.get("model_used")}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Interpret planets error: {e}")
