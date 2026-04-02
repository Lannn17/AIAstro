"""
region_router.py — GET /api/region  +  GET /api/geocode

IP 地理位置检测，返回 CN 或 GLOBAL。
地理编码代理：
  CN     → 后端调用高德 REST API（Web服务 Key），自动转换 GCJ-02 → WGS-84
  GLOBAL → Nominatim（原生 WGS-84）
"""
import os
import math
import time
import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# ── 环境变量 ─────────────────────────────────────────────────────────────────
AMAP_KEY = os.environ.get("AMAP_KEY", "")

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
    """
    地理编码代理。
    CN     → 高德 REST API（后端代理，无 CORS 问题）
    GLOBAL → Nominatim
    返回统一格式: { results: [{ display_name, lat, lon, address: {...} }] }
    坐标系: 统一返回 WGS-84（高德 GCJ-02 会自动转换）
    """
    try:
        async with httpx.AsyncClient() as client:

            # ── CN 走高德 REST API ──
            if region == "CN" and AMAP_KEY:
                resp = await client.get(
                    "https://restapi.amap.com/v3/geocode/geo",
                    params={
                        "address": q,
                        "key": AMAP_KEY,
                    },
                    timeout=5.0,
                )
                data = resp.json()

                print(f"[AMAP] query={q}, status={data.get('status')}, "
                      f"info={data.get('info')}, count={data.get('count')}",
                      flush=True)

                # 高德返回失败时打印详细信息
                if data.get("status") != "1":
                    print(f"[AMAP] ❌ Error response: {data}", flush=True)
                    return {"results": [], "error": data.get("info", "高德请求失败")}

                results = []
                for geo in data.get("geocodes", []):
                    loc = geo.get("location", "")
                    if not loc or "," not in loc:
                        continue
                    gcj_lng, gcj_lat = map(float, loc.split(","))
                    # 高德返回 GCJ-02，转为 WGS-84（占星需要真实经纬度）
                    wgs_lng, wgs_lat = gcj02_to_wgs84(gcj_lng, gcj_lat)
                    results.append({
                        "display_name": geo.get("formatted_address", q),
                        "lat": str(round(wgs_lat, 6)),
                        "lon": str(round(wgs_lng, 6)),
                        "address": {
                            "country": geo.get("country", ""),
                            "state": geo.get("province", ""),
                            "city": geo.get("city", "") if isinstance(geo.get("city"), str) else "",
                            "county": geo.get("district", ""),
                        },
                    })

                print(f"[AMAP] ✅ Returned {len(results)} results for '{q}'", flush=True)
                return {"results": results}

            # ── CN 但没有 AMAP_KEY，给出提示 ──
            elif region == "CN" and not AMAP_KEY:
                print("[AMAP] ❌ AMAP_KEY not set!", flush=True)
                # 降级到 Nominatim
                pass

            # ── GLOBAL 走 Nominatim ──
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": q,
                    "format": "json",
                    "limit": 6,
                    "addressdetails": 1,
                },
                headers={
                    "Accept-Language": "zh-CN,zh,en",
                    "User-Agent": "AIAstro/1.0",
                },
                timeout=5.0,
            )
            return {"results": resp.json()}

    except Exception as e:
        print(f"[GEOCODE] ❌ Error: {e}", flush=True)
        return {"results": [], "error": str(e)}