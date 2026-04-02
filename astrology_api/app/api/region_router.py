"""
region_router.py — GET /api/region  +  GET /api/geocode
IP 地理位置检测，返回 CN 或 GLOBAL。
地理编码代理：统一使用 Nominatim，无需 key。
"""
import time
import httpx
from fastapi import APIRouter, Request, Query

router = APIRouter()

_region_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 86400  # 24 hours


@router.get("/api/region")
async def get_region(request: Request):
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "")

    now = time.time()
    if ip and ip in _region_cache:
        cached_region, ts = _region_cache[ip]
        if now - ts < _CACHE_TTL:
            return {"region": cached_region}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}?fields=countryCode",
                timeout=3.0,
            )
        country = resp.json().get("countryCode", "")
        region = "CN" if country == "CN" else "GLOBAL"
    except Exception:
        region = "GLOBAL"

    if ip:
        _region_cache[ip] = (region, now)
    return {"region": region}


@router.get("/api/geocode")
async def geocode(
    q: str = Query(..., min_length=1),
    region: str = Query("GLOBAL"),
):
    """地理编码代理：Nominatim 服务端代理，环境严格隔离。
    CN：限定 countrycodes=cn，优先中文结果，失败直接报错不 fallback。
    GLOBAL：全球搜索，中英文结果。
    """
    params = {"q": q, "format": "json", "limit": 6, "addressdetails": 1}
    if region == "CN":
        params["countrycodes"] = "cn"
        params["accept-language"] = "zh-CN,zh"
    else:
        params["accept-language"] = "zh-CN,zh,en"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={"Accept-Language": "zh-CN,zh" if region == "CN" else "zh-CN,zh,en",
                         "User-Agent": "AIAstro/1.0"},
                timeout=5.0,
            )
        results = resp.json()
        return {"results": results, "region": region}
    except Exception as e:
        # 严格隔离：不 fallback，直接返回错误
        return {"results": [], "error": str(e), "region": region}
