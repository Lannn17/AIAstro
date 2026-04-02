"""
region_router.py — GET /api/region  +  GET /api/geocode

IP 地理位置检测，返回 CN 或 GLOBAL。
地理编码代理：
  CN  → 高德 API（GCJ-02）→ 转换为 WGS-84 后返回
  GLOBAL → Nominatim（原生 WGS-84）
两者严格隔离，不互相 fallback。
"""
import os
import math
import time
import httpx
from fastapi import APIRouter, Request, Query

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


# ── 地理编码代理 ─────────────────────────────────────────────────────────────

@router.get("/api/geocode")
async def geocode(
    q: str = Query(..., min_length=1),
    region: str = Query("GLOBAL"),
):
    """地理编码代理。CN → 高德（GCJ-02 → WGS-84）；GLOBAL → Nominatim。严格隔离不 fallback。"""
    if region == "CN":
        amap_key = os.getenv("AMAP_KEY", "")
        if not amap_key:
            return {"results": [], "error": "AMAP_KEY not configured"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://restapi.amap.com/v3/geocode/geo",
                    params={"address": q, "key": amap_key, "output": "json"},
                    timeout=5.0,
                )
            data = resp.json()
            print(f"[geocode/CN] q={q!r} status={data.get('status')} info={data.get('info')} infocode={data.get('infocode')} count={data.get('count')} raw={data}", flush=True)
            if data.get("status") != "1":
                return {"results": [], "error": data.get("info", "Amap error")}
            geocodes = data.get("geocodes") or []
            results = []
            for i, g in enumerate(geocodes):
                raw_lng, raw_lat = (float(v) for v in g["location"].split(","))
                wgs_lng, wgs_lat = gcj02_to_wgs84(raw_lng, raw_lat)
                results.append({
                    "place_id": f"amap_{i}",
                    "display_name": g["formatted_address"],
                    "lat": str(round(wgs_lat, 6)),
                    "lon": str(round(wgs_lng, 6)),
                })
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
