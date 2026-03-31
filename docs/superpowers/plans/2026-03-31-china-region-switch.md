# China Region Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CN/GLOBAL dual-mode support so mainland China users can use Gaode Maps geocoding and DeepSeek AI instead of Nominatim and Gemini.

**Architecture:** A `RegionContext` detects the user's region via IP (auto) or localStorage (manual). All `/api/*` calls carry `X-Region` header via `apiFetch` utility; backend middleware reads it into a `ContextVar` that routes `_ModelsWithFallback.generate_content()` to DeepSeek (CN) or Gemini (GLOBAL). `LocationSearch` uses Gaode REST API in CN mode, Nominatim in GLOBAL mode.

**Tech Stack:** React Context API, FastAPI middleware, `contextvars.ContextVar`, OpenAI Python SDK (DeepSeek-compatible), httpx, Gaode Geocoding REST API v3, ip-api.com (no key).

**Spec:** `docs/superpowers/specs/2026-03-31-china-region-switch-design.md`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `astrology_api/requirements.txt` | Add `httpx`, `openai` |
| Modify | `astrology_api/.env.example` | Document `DEEPSEEK_API_KEY` |
| Create | `frontend/.env` | `VITE_AMAP_KEY` for local dev |
| Modify | `.gitignore` | Ignore `frontend/.env` |
| Modify | `astrology_api/app/rag.py` | ContextVar, DeepSeek routing, adapters |
| Create | `astrology_api/app/api/region_router.py` | `GET /api/region` IP detection |
| Modify | `astrology_api/main.py` | Register region_router + region_middleware |
| Create | `frontend/src/utils/apiFetch.js` | Fetch wrapper with X-Region header |
| Create | `frontend/src/contexts/RegionContext.jsx` | Region state, init, setRegion, resetToAuto |
| Modify | `frontend/src/App.jsx` | RegionProvider wrapper + toggle UI |
| Modify | `frontend/src/hooks/useInterpret.js` | Migrate to apiFetch |
| Modify | `frontend/src/pages/NatalChart.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/pages/Transits.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/pages/Synastry.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/pages/SolarReturn.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/pages/Interpretations.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/pages/Analytics.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/contexts/AuthContext.jsx` | Migrate to apiFetch |
| Modify | `frontend/src/components/LocationSearch.jsx` | Gaode geocoding in CN mode |

---

## Task 1: Environment & Dependencies

**Files:**
- Modify: `astrology_api/requirements.txt`
- Modify: `astrology_api/.env.example`
- Create: `frontend/.env`
- Modify: `.gitignore`

- [ ] **Step 1: Add backend dependencies**

In `astrology_api/requirements.txt`, append after the RAG section:
```
# China region support
httpx>=0.27.0
openai>=1.0.0
```

- [ ] **Step 2: Document new env var in .env.example**

In `astrology_api/.env.example`, append:
```
# DeepSeek (CN region AI fallback)
DEEPSEEK_API_KEY=your_deepseek_key_here
```

- [ ] **Step 3: Create frontend/.env for local dev**

Create `frontend/.env`:
```
VITE_AMAP_KEY=your_amap_key_here
```

- [ ] **Step 4: Add frontend/.env to .gitignore**

Check current `.gitignore` content, then append `frontend/.env` to the root `.gitignore`. Verify `frontend/.env.example` is NOT ignored (we may add it later).

- [ ] **Step 5: Install backend deps**

```bash
cd astrology_api
pip install httpx openai
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(deps): add httpx, openai; document DEEPSEEK_API_KEY in .env.example"
```

---

## Task 2: rag.py — ContextVar + DeepSeek Routing

**Files:**
- Modify: `astrology_api/app/rag.py`

The goal is to add three things:
1. `ContextVar`-based region state (`set_thread_region`, `get_thread_region`)
2. A response adapter so DeepSeek responses look like Gemini responses to all callers
3. A helper to convert Gemini `contents` format → OpenAI messages format
4. DeepSeek routing branch inside `_ModelsWithFallback.generate_content()`

- [ ] **Step 1: Add imports and config at the top of rag.py**

After the existing `import threading` line, add:
```python
from contextvars import ContextVar
```

After the `_local = threading.local()` line, add:
```python
# Per-request region (CN / GLOBAL) — ContextVar is async-safe unlike threading.local
_region_var: ContextVar[str] = ContextVar('region', default='GLOBAL')

def set_thread_region(region: str) -> None:
    _region_var.set(region)

def get_thread_region() -> str:
    return _region_var.get()
```

After the `_FALLBACK_MODELS` list, add:
```python
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = "deepseek-chat"
```

- [ ] **Step 2: Add DeepSeek response adapter class**

Add these two classes immediately before the `_ModelsWithFallback` class definition:
```python
class _DSFinishReason:
    name = "STOP"

class _DSCandidate:
    finish_reason = _DSFinishReason()

class _DeepSeekResponse:
    """Minimal adapter so DeepSeek responses look like Gemini GenerateContentResponse."""
    def __init__(self, text: str):
        self.text = text
        self.candidates = [_DSCandidate()]
```

- [ ] **Step 3: Add contents → OpenAI messages converter**

Add this static method to `_ModelsWithFallback` (after `_serialize_contents`):
```python
@staticmethod
def _to_openai_messages(contents, config=None) -> list[dict]:
    """Convert Gemini contents + config to OpenAI chat messages format."""
    messages = []
    if config:
        si = getattr(config, 'system_instruction', None)
        if si:
            messages.append({"role": "system", "content": si if isinstance(si, str) else str(si)})
    if isinstance(contents, str):
        messages.append({"role": "user", "content": contents})
    elif isinstance(contents, list):
        for item in contents:
            role = getattr(item, 'role', 'user')
            if role == 'model':
                role = 'assistant'
            text = "".join(
                getattr(p, 'text', str(p))
                for p in getattr(item, 'parts', [])
            )
            messages.append({"role": role, "content": text})
    return messages
```

- [ ] **Step 4: Add DeepSeek routing branch in generate_content()**

Inside `_ModelsWithFallback.generate_content()`, after the line `_local.pending_rag_chunks = []` (the RAG chunks flush, around line 129) and BEFORE the existing `for m in chain:` loop (which starts after `t0 = time.time()`). The insertion point must be after `entry.rag_chunks` is populated — not just after `t0`. Full local block order: entry setup → `_local.pending_rag_chunks = []` → `chain = ...` → `t0 = time.time()` → **[insert DeepSeek block here]** → `for m in chain:`. Add:

```python
# ── DeepSeek path (CN region) ──────────────────────────────────────
if get_thread_region() == "CN" and DEEPSEEK_API_KEY:
    try:
        from openai import OpenAI as _OpenAI
        ds = _OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        msgs = self._to_openai_messages(contents, config)
        temp = getattr(config, 'temperature', 0.5) if config else 0.5
        completion = ds.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=msgs,
            temperature=temp,
        )
        text = completion.choices[0].message.content or ""
        _local.model_used = DEEPSEEK_MODEL
        entry.model_used = DEEPSEEK_MODEL
        entry.response_text = text[:5000]
        entry.finish_reason = "STOP"
        entry.response_tokens_est = len(text) // 2
        entry.latency_ms = int((time.time() - t0) * 1000)
        prompt_store.append(entry)
        return _DeepSeekResponse(text)
    except Exception as e:
        print(f"[DeepSeek] failed, falling back to Gemini: {e}", flush=True)
        # fall through to Gemini loop below
```

- [ ] **Step 5: Verify rag.py still imports cleanly**

```bash
cd astrology_api
python -c "from app.rag import set_thread_region, get_thread_region, client; print('OK')"
```

Expected: `OK` (no errors)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(rag): add ContextVar region routing; DeepSeek path in _ModelsWithFallback"
```

---

## Task 3: region_router.py — /api/region Endpoint

**Files:**
- Create: `astrology_api/app/api/region_router.py`

- [ ] **Step 1: Create the router file**

Create `astrology_api/app/api/region_router.py`:
```python
"""
region_router.py — GET /api/region
IP 地理位置检测，返回 CN 或 GLOBAL。
使用 ip-api.com（免费，无需 key）+ 24h in-memory cache。
"""
import time
import httpx
from fastapi import APIRouter, Request

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
```

- [ ] **Step 2: Write a quick integration test**

Create `astrology_api/tests/test_region.py` with complete setup (do NOT append to test_api.py to avoid conflicts):

```python
"""Tests for GET /api/region endpoint."""
import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from dotenv import load_dotenv
load_dotenv()

from main import app

client = TestClient(app)


def test_region_endpoint_returns_valid_response():
    """GET /api/region should return region: CN or GLOBAL."""
    response = client.get("/api/region")
    assert response.status_code == 200
    data = response.json()
    assert "region" in data
    assert data["region"] in ("CN", "GLOBAL")


def test_region_endpoint_respects_forwarded_for():
    """X-Forwarded-For header should be used for IP lookup."""
    response = client.get("/api/region", headers={"X-Forwarded-For": "8.8.8.8"})
    assert response.status_code == 200
    assert response.json()["region"] == "GLOBAL"
```

- [ ] **Step 3: Run the test**

```bash
cd astrology_api
pytest tests/test_region.py -v
```

Expected: Both tests PASS (`8.8.8.8` is a Google US IP → GLOBAL; TestClient IP → GLOBAL)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(api): add GET /api/region endpoint with IP detection and TTL cache"
```

---

## Task 4: main.py — Middleware + Router Registration

**Files:**
- Modify: `astrology_api/main.py`

- [ ] **Step 1: Import region_router and rag at the top of main.py**

Add these imports near the other router imports:
```python
from app.api.region_router import router as region_router
from app import rag
```

- [ ] **Step 2: Register region_router**

After `app.include_router(admin_router)`, add:
```python
app.include_router(region_router)
```

- [ ] **Step 3: Add region middleware**

After the existing `CORSMiddleware` block and before the router includes, add:
```python
@app.middleware("http")
async def region_middleware(request: Request, call_next):
    region = request.headers.get("X-Region", "GLOBAL")
    rag.set_thread_region(region)
    response = await call_next(request)
    return response
```

Also add `from fastapi import Request` to the imports if not already present (check — it's not currently imported in main.py).

- [ ] **Step 4: Restart backend and verify**

Kill the backend and restart:
```bash
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8001') do taskkill /F /PID %a
cd astrology_api && uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Then verify the new endpoint exists:
```bash
curl http://127.0.0.1:8001/api/region
```

Expected output: `{"region":"GLOBAL"}` (or `{"region":"CN"}` if running from China)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(api): register region_router; add region_middleware to extract X-Region header"
```

---

## Task 5: apiFetch.js — Fetch Wrapper

**Files:**
- Create: `frontend/src/utils/apiFetch.js`

- [ ] **Step 1: Create the utility**

Create `frontend/src/utils/apiFetch.js`:
```js
/**
 * apiFetch — drop-in replacement for fetch('/api/...')
 * Automatically injects X-Region header from the current RegionContext value.
 *
 * Usage:
 *   import { apiFetch } from '../utils/apiFetch'
 *   const res = await apiFetch('/api/natal_chart', { method: 'POST', body: JSON.stringify(data) })
 *
 * RegionContext calls setRegionGetter() on mount/update to keep the getter current.
 */

let _getRegion = () => 'GLOBAL'

/** Called by RegionContext to wire up the region getter. */
export function setRegionGetter(fn) {
  _getRegion = fn
}

/** Fetch wrapper that adds Content-Type and X-Region headers. */
export async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Region': _getRegion(),
    ...options.headers,
  }
  return fetch(path, { ...options, headers })
}
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "feat(ui): add apiFetch utility with automatic X-Region header injection"
```

---

## Task 6: RegionContext.jsx

**Files:**
- Create: `frontend/src/contexts/RegionContext.jsx`

- [ ] **Step 1: Create the context**

Create `frontend/src/contexts/RegionContext.jsx`:
```jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { setRegionGetter } from '../utils/apiFetch'

const RegionContext = createContext({ region: 'GLOBAL', isAuto: false })

export function useRegion() {
  return useContext(RegionContext)
}

export function RegionProvider({ children }) {
  const [region, setRegionState] = useState('GLOBAL')
  const [isAuto, setIsAuto] = useState(false)

  // Wire apiFetch to always use the latest region value
  useEffect(() => {
    setRegionGetter(() => region)
  }, [region])

  // On mount: check localStorage first, then IP detect
  useEffect(() => {
    const stored = localStorage.getItem('region')
    if (stored === 'CN' || stored === 'GLOBAL') {
      setRegionState(stored)
      setIsAuto(false)
    } else {
      // Auto-detect via backend IP check
      fetch('/api/region')
        .then(r => r.json())
        .then(data => {
          const detected = data.region === 'CN' ? 'CN' : 'GLOBAL'
          setRegionState(detected)
          setIsAuto(true)
        })
        .catch(() => {
          setRegionState('GLOBAL')
          setIsAuto(false)
        })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function setRegion(val) {
    localStorage.setItem('region', val)
    setRegionState(val)
    setIsAuto(false)
  }

  function resetToAuto() {
    localStorage.removeItem('region')
    setIsAuto(true)
    fetch('/api/region')
      .then(r => r.json())
      .then(data => {
        setRegionState(data.region === 'CN' ? 'CN' : 'GLOBAL')
      })
      .catch(() => setRegionState('GLOBAL'))
  }

  return (
    <RegionContext.Provider value={{ region, isAuto, setRegion, resetToAuto }}>
      {children}
    </RegionContext.Provider>
  )
}
```

- [ ] **Step 2: Wrap App with RegionProvider in App.jsx**

In `frontend/src/App.jsx`, add the import:
```js
import { RegionProvider } from './contexts/RegionContext'
```

Change the `App` default export from:
```jsx
export default function App() {
  return (
    <AuthProvider>
      <ChartSessionProvider>
        <AppInner />
      </ChartSessionProvider>
    </AuthProvider>
  )
}
```
To:
```jsx
export default function App() {
  return (
    <AuthProvider>
      <RegionProvider>
        <ChartSessionProvider>
          <AppInner />
        </ChartSessionProvider>
      </RegionProvider>
    </AuthProvider>
  )
}
```

- [ ] **Step 3: Start frontend and verify no console errors**

```bash
cd frontend && npm run dev
```

Open browser → DevTools console. Should see no errors. Check Network tab: `GET /api/region` is called on page load and returns `{"region":"GLOBAL"}`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(ui): add RegionContext with IP auto-detect and manual override"
```

---

## Task 7: Migrate All /api/* Calls to apiFetch

**Files:**
- Modify: `frontend/src/hooks/useInterpret.js`
- Modify: `frontend/src/pages/NatalChart.jsx`
- Modify: `frontend/src/pages/Transits.jsx`
- Modify: `frontend/src/pages/Synastry.jsx`
- Modify: `frontend/src/pages/SolarReturn.jsx`
- Modify: `frontend/src/pages/Interpretations.jsx`
- Modify: `frontend/src/pages/Analytics.jsx`
- Modify: `frontend/src/contexts/AuthContext.jsx`

**Pattern for each file:**
1. Add import: `import { apiFetch } from '../utils/apiFetch'` (adjust relative path as needed)
2. Replace every `fetch('/api/` or `` fetch(`/api/ `` or `fetch(\`${API_BASE}/api` with `apiFetch(`
3. Remove duplicate `'Content-Type': 'application/json'` from headers (apiFetch adds it automatically); keep any custom headers

- [ ] **Step 1: Migrate useInterpret.js**

`frontend/src/hooks/useInterpret.js` — this is the most important file as it handles all AI interpretation endpoints.

Add import at top:
```js
import { apiFetch } from '../utils/apiFetch'
```

Change the fetch call from:
```js
const res = await fetch(`${API_BASE}${endpoint}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', ...extraHeaders },
  body: JSON.stringify(body),
})
```
To:
```js
const res = await apiFetch(`${API_BASE}${endpoint}`, {
  method: 'POST',
  headers: { ...extraHeaders },
  body: JSON.stringify(body),
})
```

- [ ] **Step 2: Migrate remaining 7 files**

For each of the remaining files, grep for `fetch('/api`, `` fetch(`/api ``, or `` fetch(`${API_BASE} `` and replace with `apiFetch(`. Add the import at the top.

Files to update:
- `frontend/src/pages/NatalChart.jsx`
- `frontend/src/pages/Transits.jsx`
- `frontend/src/pages/Synastry.jsx`
- `frontend/src/pages/SolarReturn.jsx`
- `frontend/src/pages/Interpretations.jsx`
- `frontend/src/pages/Analytics.jsx`
- `frontend/src/contexts/AuthContext.jsx`

For each file:
```js
// Add near top of file imports:
import { apiFetch } from '../utils/apiFetch'  // adjust path depth

// Pattern A — bare path (most pages):
// Replace:
fetch('/api/natal_chart', { ..., headers: { 'Content-Type': 'application/json', ... } })
// With:
apiFetch('/api/natal_chart', { ..., headers: { /* remove Content-Type, keep others */ } })

// Pattern B — API_BASE prefix (used in NatalChart.jsx, AuthContext.jsx, others that define API_BASE):
// Replace:
fetch(`${API_BASE}/api/natal_chart`, { ..., headers: { 'Content-Type': 'application/json', ... } })
// With:
apiFetch(`${API_BASE}/api/natal_chart`, { ..., headers: { /* remove Content-Type, keep others */ } })
// IMPORTANT: preserve the ${API_BASE} prefix — do NOT drop it
```

> Note: `AuthContext.jsx` is in `contexts/` — relative import path is `'../utils/apiFetch'`.
> Pages in `pages/` — relative import path is `'../utils/apiFetch'`.

- [ ] **Step 3: Smoke test in browser**

With frontend running (`npm run dev`), open the app and:
- Load the 本命盘 (natal chart) page — no errors
- Try a natal chart calculation — should succeed
- Open DevTools Network tab — all `/api/*` requests should have `X-Region: GLOBAL` header visible

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(ui): migrate all /api/* fetch calls to apiFetch for X-Region header"
```

---

## Task 8: LocationSearch — Gaode CN Mode

**Files:**
- Modify: `frontend/src/components/LocationSearch.jsx`

- [ ] **Step 1: Add Gaode search function**

In `LocationSearch.jsx`, add this helper function before the component definition:

```js
const AMAP_KEY = import.meta.env.VITE_AMAP_KEY || ''

async function searchAmap(query) {
  const res = await fetch(
    `https://restapi.amap.com/v3/geocode/geo?address=${encodeURIComponent(query)}&key=${AMAP_KEY}&output=json`
  )
  const data = await res.json()
  if (!data.geocodes || data.geocodes.length === 0) return []
  return data.geocodes.map((g, i) => ({
    place_id: `amap_${i}`,           // synthetic unique key
    display_name: g.formatted_address,
    lat: g.location.split(',')[1],    // "lng,lat" → lat is index 1
    lon: g.location.split(',')[0],    // lng is index 0
  }))
}
```

- [ ] **Step 2: Import useRegion and wire the search**

Add import:
```js
import { useRegion } from '../contexts/RegionContext'
```

Inside the component, add:
```js
const { region } = useRegion()
```

In the `handleInput` debounce, replace the existing `fetch(nominatim...)` block with:
```js
debounceRef.current = setTimeout(async () => {
  setSearching(true)
  try {
    let data
    if (region === 'CN') {
      data = await searchAmap(value)
    } else {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(value)}&format=json&limit=6&addressdetails=1`,
        { headers: { 'Accept-Language': 'zh-CN,zh,en' } }
      )
      data = await res.json()
    }
    setSuggestions(data)
    if (data.length === 0) setSearchFailed(true)
  } catch {
    setSearchFailed(true)
  } finally {
    setSearching(false)
  }
}, 500)
```

- [ ] **Step 3: Verify GLOBAL mode still works**

With `VITE_AMAP_KEY` not set (or set to empty), the component should still use Nominatim when `region === 'GLOBAL'`. Test by typing "Beijing" in any location field — should show Nominatim results as before.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(ui): add Gaode geocoding in LocationSearch for CN region mode"
```

---

## Task 9: Region Toggle UI in App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add RegionToggle component**

In `App.jsx`, add this component after the `UserBadge` component definition:

```jsx
function RegionToggle() {
  const { region, isAuto, setRegion, resetToAuto } = useRegion()

  function handleClick(val) {
    if (region === val) {
      // Clicking active item resets to auto-detect
      resetToAuto()
    } else {
      setRegion(val)
    }
  }

  const btnBase = {
    padding: '4px 8px',
    border: '1px solid #2a2a5a',
    borderRadius: '5px',
    fontSize: '0.72rem',
    cursor: 'pointer',
    background: 'transparent',
    color: '#8888aa',
    whiteSpace: 'nowrap',
    lineHeight: 1.2,
  }

  const btnActive = {
    ...btnBase,
    borderColor: '#c9a84c',
    color: '#c9a84c',
  }

  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexShrink: 0 }}>
      <button
        style={region === 'GLOBAL' ? btnActive : btnBase}
        onClick={() => handleClick('GLOBAL')}
        title={region === 'GLOBAL' && isAuto ? '自动检测（点击重置）' : undefined}
      >
        🌐 海外
      </button>
      <button
        style={region === 'CN' ? btnActive : btnBase}
        onClick={() => handleClick('CN')}
        title={region === 'CN' && isAuto ? '自动检测（点击重置）' : undefined}
      >
        🇨🇳 国内
      </button>
      {isAuto && (
        <span style={{ fontSize: '0.65rem', color: '#555577', marginLeft: '2px' }}>
          自动
        </span>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add import and place toggle in the header**

Add import at top of App.jsx:
```js
import { useRegion } from './contexts/RegionContext'
```

In the `AppInner` header section, after `<UserBadge />`, add `<RegionToggle />`:
```jsx
{/* User badge */}
<UserBadge />
{/* Region toggle */}
<RegionToggle />
```

- [ ] **Step 3: Verify the toggle appears and works**

With the frontend running:
1. Nav bar should show `🌐 海外` and `🇨🇳 国内` buttons, with "自动" badge if auto-detected
2. Click `🇨🇳 国内` → active button highlights gold, "自动" badge disappears
3. Click `🇨🇳 国内` again → reverts to auto (badge reappears)
4. Reload page → manually set preference persists

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(ui): add RegionToggle to nav bar with auto-detect badge"
```

---

## Task 10: test.md + Final Verification

- [ ] **Step 1: Write test checklist to test.md**

Append to `test.md`:

```markdown
---

# 国内/海外双模式切换（2026-03-31）

> 前置条件：`VITE_AMAP_KEY` 和 `DEEPSEEK_API_KEY` 已配置

## 1. Region 自动检测

- [ ] 清除 localStorage → 刷新页面 → Network 面板看到 `GET /api/region` → 返回 `{"region":"GLOBAL"}` → 导航栏显示「自动」角标

## 2. 手动切换

- [ ] 点击「🇨🇳 国内」→ 按钮高亮，「自动」消失，localStorage['region'] = "CN"
- [ ] 刷新页面 → 仍显示国内模式（无自动角标）
- [ ] 再次点击「🇨🇳 国内」（当前激活项）→ 清除 localStorage，恢复自动，「自动」角标重现

## 3. 地理编码（需 VITE_AMAP_KEY）

- [ ] 国内模式 → 出生地搜索「北京」→ 出现高德返回结果（非 Nominatim）→ 选择后坐标显示 ✓
- [ ] 海外模式 → 出生地搜索「Paris」→ 出现 Nominatim 结果 → 选择后坐标正确

## 4. AI 分析（需 DEEPSEEK_API_KEY）

- [ ] 国内模式 → 计算本命盘 → 触发行星解读 → DevTools: 请求头含 `X-Region: CN`
- [ ] 后端日志：显示 `[model_used: deepseek-chat]`（或模型标签显示 deepseek）
- [ ] 海外模式 → 同一操作 → 使用 Gemini 模型

## 5. 边界情况

- [ ] `VITE_AMAP_KEY` 为空 → 国内模式搜索 → 搜索失败，显示「未找到地点」（不崩溃）
- [ ] 网络断开 → `/api/region` 超时 → 默认 GLOBAL 模式，无报错
```

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "test(region): add manual test checklist for CN/GLOBAL region switch"
```

---

## Summary

| Task | Commits | Key deliverable |
|---|---|---|
| 1 | 1 | Dependencies + env docs |
| 2 | 1 | DeepSeek routing in rag.py |
| 3 | 1 | `/api/region` endpoint |
| 4 | 1 | Middleware wiring |
| 5 | 1 | `apiFetch` utility |
| 6 | 1 | `RegionContext` + App wrapper |
| 7 | 1 | All API calls migrated |
| 8 | 1 | Gaode geocoding |
| 9 | 1 | Region toggle UI |
| 10 | 1 | Test checklist |
| **Total** | **10** | |
