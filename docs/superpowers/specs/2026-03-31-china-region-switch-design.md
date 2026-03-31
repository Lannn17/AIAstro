# 国内/海外双模式切换 — 设计文档

**日期**: 2026-03-31
**状态**: 已批准，待实现

---

## 背景

Nominatim（地理编码）和 Google Gemini（AI 生成）在中国大陆需要 VPN 才能访问。本功能为大陆用户提供国内替代方案：高德地图 Geocoding API + DeepSeek AI，支持手动切换与自动检测（IP 识别）两种模式，优先级为手动 > 自动。

---

## 前置条件（实现前必须准备）

新增环境变量：

| 变量 | 用途 | 获取地址 |
|---|---|---|
| `VITE_AMAP_KEY` | 高德 Web 服务 Key（前端直调，**必须绑定域名白名单**） | console.amap.com |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | platform.deepseek.com |

已有变量（仍然必须）：

| 变量 | 说明 |
|---|---|
| `GOOGLE_API_KEY` | Gemini 仍然是 GLOBAL 模式的生成引擎，**两种模式下均为必填** |

**`VITE_AMAP_KEY` 安全说明**：该 key 会被 Vite 打包进前端 JS bundle，可被用户在 DevTools 中看到。高德域名白名单可防止他人从其他域名盗用。这对本项目而言是可接受的折中（与 Nominatim 无需 key 的现状相比无显著新增风险）。HF Spaces 部署时在 Space 的 Variables 中设置 `VITE_AMAP_KEY`，构建时注入。

---

## 架构总览

```
用户/IP检测 → RegionContext（全局状态）
  ├── LocationSearch
  │     ├── GLOBAL → Nominatim（直连浏览器，现有逻辑）
  │     └── CN     → 高德 Geocoding REST API（直连浏览器，VITE_AMAP_KEY）
  └── 所有 /api/* AI 接口（请求头带 X-Region）
        → FastAPI 中间件提取 X-Region → 设置 thread-local
        → _ModelsWithFallback.generate_content() 读 thread-local
              ├── GLOBAL → Gemini（现有逻辑不变）
              └── CN     → DeepSeek（openai 兼容接口）

地区判断优先级：
  1. localStorage['region']（手动设置）
  2. GET /api/region（IP 自动检测）
  3. 默认 GLOBAL
```

---

## 前端

### RegionContext (`frontend/src/contexts/RegionContext.jsx`)

**初始化逻辑**：
1. 读 `localStorage.getItem('region')` → 有值（`'CN'`/`'GLOBAL'`）则直接使用，`isAuto = false`
2. 无值 → 调 `GET /api/region` → 写入 state，`isAuto = true`
3. 请求失败/超时 → 默认 `'GLOBAL'`，`isAuto = false`

**提供**：
- `region`: `'CN' | 'GLOBAL'`
- `isAuto`: boolean（`true` = 当前值来自 IP 自动检测，未被手动覆盖）
- `setRegion(val)`: 手动切换，写入 localStorage，`isAuto` 变为 `false`
- `resetToAuto()`: 清除 `localStorage['region']`，重新调 `/api/region`，`isAuto` 恢复 `true`

**挂载**：在 `App.jsx` 中，`<RegionProvider>` 包裹在 `<AuthProvider>` 内层。

### LocationSearch 适配 (`frontend/src/components/LocationSearch.jsx`)

通过 `useRegion()` 读取 `region`，选择调用目标：

**GLOBAL 模式**（现有逻辑不变）：
```
GET https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=6&addressdetails=1
响应: [{ lat, lon, display_name, place_id }]
零结果 → setSearchFailed(true)（现有逻辑）
```

**CN 模式**：
```
GET https://restapi.amap.com/v3/geocode/geo?address={query}&key={VITE_AMAP_KEY}&output=json
响应: { geocodes: [{ location: "经度,纬度", formatted_address }] }

注意：高德 location 字段格式为 "longitude,latitude"（经度在前，与直觉相反）
解析：const [lng, lat] = location.split(',')
display_name = formatted_address

geocodes.length === 0 → setSearchFailed(true)（与 GLOBAL 模式行为一致）
```

两种模式统一通过 `onSelect({ latitude, longitude, locationName })` 输出，上层组件无需改动。

### 前端 API 调用封装 (`frontend/src/utils/apiFetch.js`)

新增统一封装函数，自动注入 `X-Region` 头，替代所有直接调用 `fetch('/api/...')` 的地方：

```js
// frontend/src/utils/apiFetch.js
import { useRegion } from '../contexts/RegionContext'

// 非 hook 版本（供普通函数、非组件代码使用）
let _getRegion = () => 'GLOBAL'
export function setRegionGetter(fn) { _getRegion = fn }

export async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Region': _getRegion(),
    ...options.headers,
  }
  return fetch(path, { ...options, headers })
}
```

在 `RegionContext.jsx` 初始化完成时调用 `setRegionGetter(() => region)`，使 `apiFetch` 始终能拿到最新的 region 值。

**迁移**：将以下文件中所有 `fetch('/api/...')` 替换为 `apiFetch('/api/...')`：
- `frontend/src/pages/SolarReturn.jsx`
- `frontend/src/pages/NatalChart.jsx`
- `frontend/src/pages/Transits.jsx`
- `frontend/src/pages/Synastry.jsx`
- `frontend/src/pages/Interpretations.jsx`
- `frontend/src/hooks/useInterpret.js`
- `frontend/src/pages/Analytics.jsx`
- `frontend/src/contexts/AuthContext.jsx`（auth 接口也一并迁移，保持统一）

> 直连高德 / Nominatim 的地理编码 fetch 保持原样，不经过 `apiFetch`。

### 地区切换 UI (`App.jsx` 导航栏)

导航栏右侧新增切换区：
- 显示：`🌐 海外` / `🇨🇳 国内`
- `isAuto === true` 时按钮旁显示「自动」角标（小字，灰色）
- **点击当前激活项** → 调用 `resetToAuto()`（清除手动设置，恢复自动检测），角标重现
- **点击非激活项** → 调用 `setRegion()`，立即切换，角标消失
- 样式与现有 nav 元素一致（暗色背景，`0.75rem` 字体）

---

## 后端

### 新增依赖 (`astrology_api/requirements.txt`)

新增两行：
```
httpx
openai
```

### IP 检测接口 (`GET /api/region`)

新增路由（挂在独立 `region_router` 或 `auth_router`）。使用简单 in-memory dict 做 24 小时 TTL 缓存，避免 ip-api.com 限速（45 req/min）：

```python
import httpx
from fastapi import Request

_region_cache: dict[str, tuple[str, float]] = {}  # ip -> (region, timestamp)
_CACHE_TTL = 86400  # 24 hours

async def get_region(request: Request):
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    ip = forwarded or request.client.host

    now = time.time()
    if ip in _region_cache:
        region, ts = _region_cache[ip]
        if now - ts < _CACHE_TTL:
            return {"region": region}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3
            )
        country = resp.json().get("countryCode", "")
        region = "CN" if country == "CN" else "GLOBAL"
    except Exception:
        region = "GLOBAL"

    _region_cache[ip] = (region, now)
    return {"region": region}
```

### 后端路由层：region 中间件/依赖

新增 FastAPI 中间件（`main.py`），从请求头提取 `X-Region` 并写入 ContextVar：

```python
@app.middleware("http")
async def region_middleware(request: Request, call_next):
    region = request.headers.get("X-Region", "GLOBAL")
    rag.set_thread_region(region)   # 见下
    response = await call_next(request)
    return response
```

这样**无需修改任何 Pydantic 模型或路由函数签名**。

### DeepSeek 接入 (`astrology_api/app/rag.py`)

**新增配置**：
```python
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = "deepseek-chat"
```

**新增 ContextVar region 管理**（使用 `contextvars.ContextVar` 而非 `threading.local`，确保异步并发下每个请求独立隔离，`threading.local` 在 FastAPI async 路由中多请求共享同一线程时会发生竞态）：

```python
from contextvars import ContextVar

_region_var: ContextVar[str] = ContextVar('region', default='GLOBAL')

def set_thread_region(region: str):
    _region_var.set(region)

def get_thread_region() -> str:
    return _region_var.get()
```

**在 `_ModelsWithFallback.generate_content()` 中路由**（统一拦截点，覆盖 rag.py 中全部 `client.models.generate_content()` 调用）：

```python
def generate_content(self, model, contents, config=None, **kwargs):
    if get_thread_region() == "CN" and DEEPSEEK_API_KEY:
        # DeepSeek openai-compatible path
        from openai import OpenAI as _OpenAI
        ds_client = _OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        # 提取 prompt 文本，调用 ds_client.chat.completions.create(...)
        # 返回统一格式结果
        ...
    else:
        # 现有 Gemini fallback 逻辑不变
        ...
```

路由发生在 `_ModelsWithFallback` 层，**覆盖 rag.py 中所有** `client.models.generate_content()` 调用（包括 `classify_query`、`chat_with_chart`、`rag_generate` 等全部 ~15 处），无需逐一修改。

---

## 数据流

```
[浏览器启动]
  RegionContext 初始化
  → localStorage 有值 → 直接用（isAuto=false）
  → 无值 → GET /api/region → ip-api.com（带缓存）→ CN/GLOBAL（isAuto=true）

[用户搜索地点]
  LocationSearch 读 region
  → CN:     fetch amap.com → 解析 "lng,lat" → onSelect(lat, lng)
  → GLOBAL: fetch nominatim → onSelect(lat, lng)
  两种模式零结果均触发 searchFailed UI

[用户触发 AI 分析]
  前端 fetch /api/... 带头 X-Region: CN/GLOBAL
  → 中间件设置 _local.region
  → _ModelsWithFallback.generate_content() 读 _local.region
  → CN:     DeepSeek API
  → GLOBAL: Gemini（现有 fallback 逻辑）
```

---

## 不在本次范围内

- Qdrant 向量库的国内镜像（用户未反映访问问题）
- embedding 模型替换（`intfloat/multilingual-e5-small` 本地运行，无网络依赖）
- 用户账户级地区偏好持久化（localStorage 已足够）
- `/api/region` 缓存持久化（进程重启后缓存清空，重新检测一次即可）
- `_region_cache` 容量上限（已知限制：dict 无主动淘汰，长期运行下 IP 条目会持续积累；24h TTL 下实际增长缓慢，生产流量大时可考虑加 `len > 10000` 时清空旧条目）
