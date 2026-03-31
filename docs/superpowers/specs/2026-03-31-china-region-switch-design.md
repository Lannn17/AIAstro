# 国内/海外双模式切换 — 设计文档

**日期**: 2026-03-31
**状态**: 已批准，待实现

---

## 背景

Nominatim（地理编码）和 Google Gemini（AI 生成）在中国大陆需要 VPN 才能访问。本功能为大陆用户提供国内替代方案：高德地图 Geocoding API + DeepSeek AI，并支持手动切换与自动检测两种模式。

---

## 前置条件（实现前必须准备）

| 环境变量 | 用途 | 获取地址 |
|---|---|---|
| `VITE_AMAP_KEY` | 高德 Web 服务 Key（前端直调，绑定域名白名单） | console.amap.com |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | platform.deepseek.com |

---

## 架构总览

```
用户/IP检测 → RegionContext（全局状态）
  ├── LocationSearch
  │     ├── GLOBAL → Nominatim（直连，现有逻辑）
  │     └── CN     → 高德 Geocoding REST API（直连，VITE_AMAP_KEY）
  └── 所有 AI 接口（请求 body 带 region 字段）
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

- **初始化**：读 `localStorage.getItem('region')`；无值则调 `GET /api/region`；失败默认 `'GLOBAL'`
- **提供**：
  - `region`: `'CN' | 'GLOBAL'`
  - `isAuto`: boolean（当前值来自自动检测，未被手动覆盖）
  - `setRegion(val)`: 手动切换，写入 localStorage
- **挂载**：在 `App.jsx` 用 `<RegionProvider>` 包裹，位置在 `AuthProvider` 内层

### LocationSearch 适配 (`frontend/src/components/LocationSearch.jsx`)

通过 `useRegion()` 获取当前 region，根据值选择 API：

**GLOBAL 模式**（现有逻辑不变）：
```
GET https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=6&addressdetails=1
响应: [{ lat, lon, display_name, place_id }]
```

**CN 模式**：
```
GET https://restapi.amap.com/v3/geocode/geo?address={query}&key={VITE_AMAP_KEY}&output=json
响应: { geocodes: [{ location: "lng,lat", formatted_address }] }
解析: location.split(',') → [lng, lat]，display_name = formatted_address
```

两种模式统一通过 `onSelect({ latitude, longitude, locationName })` 回调输出，上层组件无需改动。

### 地区切换 UI (`App.jsx` 导航栏)

导航栏右侧新增切换按钮：
- 显示：`🌐 海外` / `🇨🇳 国内`
- `isAuto === true` 时，按钮下方显示「自动」角标
- 点击调用 `setRegion()`，立即生效
- 样式与现有 nav 元素一致（暗色背景，`0.75rem` 字体）

---

## 后端

### IP 检测接口 (`GET /api/region`)

新增路由（建议挂在 `auth_router` 或单独 `region_router`）：

```python
async def get_region(request: Request):
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
         or request.client.host
    # 调用免费 IP 地理位置服务（无需 key，超时 3s）
    resp = await httpx.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3)
    country = resp.json().get("countryCode", "")
    return {"region": "CN" if country == "CN" else "GLOBAL"}
    # 失败/超时 → 返回 "GLOBAL"
```

### DeepSeek 接入 (`astrology_api/app/rag.py`)

新增配置：
```python
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = "deepseek-chat"
```

在生成层（`rag_generate()` 或 `_ClientWithFallback`）新增 `region` 参数：
- `region == "CN"` 且 `DEEPSEEK_API_KEY` 存在 → 用 `openai` 库，`base_url="https://api.deepseek.com"`
- 其他 → 现有 Gemini 逻辑不变

所有现有 AI 端点 request body 新增：
```python
region: str = "GLOBAL"  # 可选，前端传入
```
透传至 `rag_generate(region=region)`。

### 依赖

后端新增：`httpx`（IP 检测异步请求，FastAPI 项目通常已有），`openai`（DeepSeek 兼容调用）。

---

## 数据流示意

```
[浏览器启动]
  → RegionContext 初始化
  → localStorage 有值？→ 直接用
  → 无值 → GET /api/region → ip-api.com → CN/GLOBAL
  → 写入 context state

[用户搜索地点]
  → LocationSearch 读 region
  → CN: fetch amap.com → 解析返回 → onSelect(lat, lng)
  → GLOBAL: fetch nominatim → 解析返回 → onSelect(lat, lng)

[用户触发 AI 分析]
  → 前端读 region → 加入 request body
  → 后端收到 region="CN" → DeepSeek 生成
  → 后端收到 region="GLOBAL" → Gemini 生成（现有逻辑）
```

---

## 不在本次范围内

- Qdrant 向量库的国内镜像（用户未反映问题，暂不处理）
- embedding 模型的国内替代（本地运行，无网络依赖）
- 用户账户级别的地区偏好持久化（localStorage 已足够）
