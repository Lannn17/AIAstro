"""
region_router.py — GET /api/region  +  GET /api/geocode
IP 地理位置检测，返回 CN 或 GLOBAL。
地理编码代理：CN 调高德，GLOBAL 调 Nominatim（key 放后端 env，不暴露前端）。
"""
import os
import time
import httpx
from fastapi import APIRouter, Request, Query

AMAP_KEY = os.getenv("AMAP_KEY", "")

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
    """地理编码代理：CN → 高德，GLOBAL → Nominatim。"""
    if region == "CN":
        if not AMAP_KEY:
            return {"results": [], "error": "AMAP_KEY not configured"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://restapi.amap.com/v3/geocode/geo",
                    params={"address": q, "key": AMAP_KEY, "output": "json"},
                    timeout=5.0,
                )
            data = resp.json()
            geocodes = data.get("geocodes") or []
            results = [
                {
                    "place_id": f"amap_{i}",
                    "display_name": g["formatted_address"],
                    "lat": g["location"].split(",")[1],
                    "lon": g["location"].split(",")[0],
                }
                for i, g in enumerate(geocodes)
            ]
            return {"results": results}
        except Exception as e:
            return {"results": [], "error": str(e)}
    else:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": q, "format": "json", "limit": 6, "addressdetails": 1},
                    headers={"Accept-Language": "zh-CN,zh,en", "User-Agent": "AIAstro/1.0"},
                    timeout=5.0,
                )
            return {"results": resp.json()}
        except Exception as e:
            return {"results": [], "error": str(e)}
