"""
region_router.py — GET /api/region  +  GET /api/geocode  +  GET /_AMapService/{path}

IP 地理位置检测，返回 CN 或 GLOBAL。
地理编码代理：
  CN  → 前端使用高德 JS SDK，通过 /_AMapService 代理注入 jscode（安全密钥不暴露前端）
  GLOBAL → Nominatim（原生 WGS-84）
/_AMapService: 高德 JS API 安全代理，将 jscode 拼入后转发到 restapi.amap.com。
"""
import os
import math
import time
import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

router = APIRouter()

_region_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 86400  # 24 hours


# ── GCJ-02 → WGS-84 转换 ────────────────────────────────────────────────────

def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """将高德 GCJ-02 坐标转换为标准 WGS-84。"""
    a = 6378245.0
    ee = 0.00669342162296594323
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - ee * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (a / sqrt_magic * math.cos(rad_lat) * math.pi)
    return lng - d_lng, lat - d_lat


# ── IP 区域检测 ──────────────────────────────────────────────────────────────

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


# ── 高德 JS API 安全代理 ──────────────────────────────────────────────────────

@router.get("/_AMapService/{path:path}")
async def amap_service_proxy(path: str, request: Request):
    """将高德 JS SDK 请求代理到 restapi.amap.com，注入 jscode（安全密钥）。"""
    security_key = os.getenv("AMAP_SECURITY_KEY", "")
    params = dict(request.query_params)
    if security_key:
        params["jscode"] = security_key
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://restapi.amap.com/{path}",
                params=params,
                headers={"User-Agent": "AIAstro/1.0"},
                timeout=5.0,
            )
        return JSONResponse(content=resp.json())
    except Exception as e:
        return JSONResponse(content={"status": "0", "info": str(e)}, status_code=502)


# ── 地理编码代理 ─────────────────────────────────────────────────────────────

@router.get("/api/geocode")
async def geocode(
    q: str = Query(..., min_length=1),
    region: str = Query("GLOBAL"),
):
    """地理编码代理。GLOBAL → Nominatim。CN 由前端 JS SDK + /_AMapService 直接处理。"""
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
