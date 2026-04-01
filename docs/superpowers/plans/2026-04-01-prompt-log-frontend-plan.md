# Prompt Log Persistence — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build admin UI for prompt version management + test comparison, tab-switch rating modal for user evaluations, and a global feedback button accessible from all pages.

**Architecture:** New admin page at `/admin/prompts` added to React Router. `PromptRatingContext` tracks the most recent unrated AI log_id per page; tab navigation (NavLink clicks) is intercepted by a `useBlocker` hook to show the rating modal before switching. Global `FeedbackButton` floats bottom-right on all pages.

**Tech Stack:** React 18, React Router v6 (`useBlocker`), existing inline-style convention (no Tailwind), fetch against `/api/user/*` and `/api/admin/*` endpoints.

**Prereq:** Backend plan (`2026-04-01-prompt-log-backend-plan.md`) fully deployed — all API endpoints available.

**Spec:** `docs/superpowers/specs/2026-04-01-prompt-log-persistence-design.md`

---

### Task 1: Add `PromptRatingContext` — track unrated AI results

**Files:**
- Create: `frontend/src/contexts/PromptRatingContext.jsx`
- Modify: `frontend/src/App.jsx`

The context tracks: for the current page, was there a recent AI response, and has the user rated it?

- [ ] **Step 1: Create `PromptRatingContext.jsx`**

```jsx
// frontend/src/contexts/PromptRatingContext.jsx
import { createContext, useContext, useState, useCallback } from 'react'

const PromptRatingContext = createContext(null)

export function PromptRatingProvider({ children }) {
  // logId of the most recent AI result that hasn't been rated yet
  const [pendingLogId, setPendingLogId] = useState(null)
  // Skip count for soft-enforcement logic
  const [skipCount, setSkipCount] = useState(0)

  const registerResult = useCallback((logId) => {
    // Called by AI result components after receiving a response
    setPendingLogId(logId)
  }, [])

  const clearPending = useCallback(() => {
    setPendingLogId(null)
  }, [])

  const recordSkip = useCallback(() => {
    setSkipCount(n => n + 1)
  }, [])

  const resetSkipCount = useCallback(() => {
    setSkipCount(0)
  }, [])

  return (
    <PromptRatingContext.Provider value={{
      pendingLogId,
      skipCount,
      registerResult,
      clearPending,
      recordSkip,
      resetSkipCount,
    }}>
      {children}
    </PromptRatingContext.Provider>
  )
}

export function usePromptRating() {
  const ctx = useContext(PromptRatingContext)
  if (!ctx) throw new Error('usePromptRating must be used inside PromptRatingProvider')
  return ctx
}
```

- [ ] **Step 2: Wrap app with `PromptRatingProvider` in `App.jsx`**

In `App.jsx`, add import and wrap the content:
```jsx
import { PromptRatingProvider } from './contexts/PromptRatingContext'

// In the JSX return, wrap everything inside BrowserRouter with PromptRatingProvider:
<PromptRatingProvider>
  {/* existing content */}
</PromptRatingProvider>
```

- [ ] **Step 3: Verify no console errors**

Start frontend (`npm run dev`), open browser. No context errors in console.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/contexts/PromptRatingContext.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add PromptRatingContext for tracking unrated AI results"
```

---

### Task 2: Build `PromptRatingModal` + tab-switch interceptor

**Files:**
- Create: `frontend/src/components/PromptRatingModal.jsx`
- Modify: `frontend/src/App.jsx`

The modal appears when the user tries to navigate away from a page with an unrated AI result.

- [ ] **Step 1: Create `PromptRatingModal.jsx`**

```jsx
// frontend/src/components/PromptRatingModal.jsx
import { useState } from 'react'
import { usePromptRating } from '../contexts/PromptRatingContext'
import { useAuth } from '../contexts/AuthContext'

const OVERLAY = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 9999,
}
const CARD = {
  background: '#1a1a2e', border: '1px solid #3a3a6a',
  borderRadius: '12px', padding: '28px 32px',
  width: '380px', maxWidth: '90vw',
  display: 'flex', flexDirection: 'column', gap: '18px',
}
const SCORE_OPTS = [
  { label: '低', value: 1 },
  { label: '中', value: 3 },
  { label: '高', value: 5 },
]

export default function PromptRatingModal({ onClose, onProceed }) {
  const { pendingLogId, clearPending, recordSkip, resetSkipCount, skipCount } = usePromptRating()
  const { authHeaders } = useAuth()
  const [score, setScore] = useState(null)
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showNudge, setShowNudge] = useState(false)

  async function handleSubmit() {
    if (!score) return
    setSubmitting(true)
    try {
      await fetch('/api/user/prompt-evaluations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ log_id: pendingLogId, score, notes }),
      })
      resetSkipCount()
      clearPending()
      onProceed()
    } catch (e) {
      console.error('Rating submit failed:', e)
      onProceed()
    } finally {
      setSubmitting(false)
    }
  }

  function handleClose() {
    recordSkip()
    clearPending()
    if (skipCount + 1 >= 3) {
      setShowNudge(true)
      return
    }
    onClose()
  }

  if (showNudge) {
    return (
      <div style={OVERLAY}>
        <div style={CARD}>
          <p style={{ color: '#c9c9e0', margin: 0 }}>
            你的反馈帮助我们持续优化分析质量，只需 3 秒。
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <button
              onClick={() => { setShowNudge(false); onProceed() }}
              style={{ padding: '8px 18px', background: 'transparent', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#8888aa', cursor: 'pointer' }}
            >
              跳过
            </button>
            <button
              onClick={() => setShowNudge(false)}
              style={{ padding: '8px 18px', background: '#c9a84c', border: 'none', borderRadius: '6px', color: '#0a0a1a', fontWeight: 600, cursor: 'pointer' }}
            >
              去评分
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={OVERLAY}>
      <div style={CARD}>
        <p style={{ color: '#c9c9e0', margin: 0, fontSize: '1rem', lineHeight: 1.5 }}>
          你认为该分析在多大程度上展示了差异化？
        </p>
        <div style={{ display: 'flex', gap: '12px' }}>
          {SCORE_OPTS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setScore(opt.value)}
              style={{
                flex: 1, padding: '10px 0',
                background: score === opt.value ? '#c9a84c' : 'transparent',
                border: `1px solid ${score === opt.value ? '#c9a84c' : '#3a3a6a'}`,
                borderRadius: '8px',
                color: score === opt.value ? '#0a0a1a' : '#8888aa',
                fontWeight: score === opt.value ? 700 : 400,
                cursor: 'pointer', fontSize: '1rem',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <textarea
          placeholder="可选：文字反馈"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={3}
          style={{
            background: '#0d0d1f', border: '1px solid #3a3a6a', borderRadius: '6px',
            color: '#c9c9e0', padding: '10px', resize: 'none', fontSize: '0.9rem',
          }}
        />
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            onClick={handleClose}
            style={{ padding: '8px 18px', background: 'transparent', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#8888aa', cursor: 'pointer' }}
          >
            关闭
          </button>
          <button
            onClick={handleSubmit}
            disabled={!score || submitting}
            style={{
              padding: '8px 18px',
              background: score ? '#c9a84c' : '#3a3a6a',
              border: 'none', borderRadius: '6px',
              color: score ? '#0a0a1a' : '#5a5a8a',
              fontWeight: 600, cursor: score ? 'pointer' : 'not-allowed',
            }}
          >
            {submitting ? '提交中…' : '提交'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add navigation blocker in `App.jsx`**

Add these imports to `App.jsx`:
```jsx
import { useState, useEffect } from 'react'  // useState already used elsewhere; add if not present
import { useBlocker } from 'react-router-dom'
import PromptRatingModal from './components/PromptRatingModal'
import { usePromptRating } from './contexts/PromptRatingContext'
```

Add `NavigationRatingGuard` as a new function in `App.jsx`:
```jsx
function NavigationRatingGuard() {
  const { pendingLogId } = usePromptRating()
  const [showModal, setShowModal] = useState(false)
  const [blocker, setBlockerRef] = useState(null)

  const b = useBlocker(
    ({ currentLocation, nextLocation }) =>
      !!pendingLogId && currentLocation.pathname !== nextLocation.pathname
  )

  useEffect(() => {
    if (b.state === 'blocked') {
      setBlockerRef(b)
      setShowModal(true)
    }
  }, [b.state])

  if (!showModal) return null

  return (
    <PromptRatingModal
      onClose={() => { setShowModal(false); b.proceed() }}
      onProceed={() => { setShowModal(false); b.proceed() }}
    />
  )
}
```

The complete final JSX structure of `AppInner` (the component that sits inside `BrowserRouter`) must look like this after both Task 1 and Task 2 changes are merged:

```jsx
function AppInner() {
  // ... existing state/hooks ...
  return (
    <PromptRatingProvider>          {/* Task 1 — wraps everything inside the router */}
      <LoginModal ... />
      <WelcomeModal ... />
      <header>...</header>
      <main>
        <Routes>
          {/* existing routes */}
        </Routes>
      </main>
      <NavigationRatingGuard />     {/* Task 2 — inside router & PromptRatingProvider */}
      <FeedbackButton />            {/* Task 4 — added later */}
    </PromptRatingProvider>
  )
}
```

`NavigationRatingGuard` must be **inside** `PromptRatingProvider` (needs context) and **inside** `BrowserRouter` (needs router context for `useBlocker`).

- [ ] **Step 3: Test the blocker**

1. Navigate to Transits page, trigger an AI analysis (if backend is available)
2. Click to navigate to another tab
3. Rating modal should appear
4. Click Close → modal disappears, navigation proceeds
5. Do this 3 times → nudge message appears

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PromptRatingModal.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add tab-switch rating modal with navigation blocker"
```

---

### Task 3: Wire `registerResult` into AI result components

**Files:**
- Modify: `frontend/src/components/AIPanel.jsx` (or whichever component renders AI analysis results)
- Modify: relevant page components that receive AI responses

> The backend returns a `log_id` in AI responses once Task 10 of the backend plan is done. Each AI result component should call `registerResult(log_id)` after the response arrives.

- [ ] **Step 1: Identify the components that hold AI results**

The pattern in this app: each page (e.g. `NatalChart.jsx`, `Transits.jsx`) calls the API and stores the result in local state, then passes it to `AIPanel.jsx` as a `result` prop. Wire `registerResult` at the page level (where `result.log_id` first arrives), not inside `AIPanel`.

Pages to update (check each for `fetch('/api/interpret_planets'` etc.):
- `frontend/src/pages/NatalChart.jsx` — calls `/api/interpret_planets`
- `frontend/src/pages/Transits.jsx` — calls `/api/interpret/transits_full`
- `frontend/src/pages/Synastry.jsx` — calls `/api/synastry`
- `frontend/src/pages/SolarReturn.jsx` — calls `/api/solar-return`

- [ ] **Step 2: Add `log_id` to backend API responses**

The backend's `_persist_prompt_log` in `client.py` should return the log_id. Modify the relevant API endpoints to include `"log_id"` in their response. Example for `interpret_router.py`:

```python
# In the response dict, add:
return {
    "analyses": analyses,
    "sources": sources,
    "log_id": last_log_id,  # from prompt_store last entry
}
```

The simplest approach: after `prompt_store.append(entry)`, expose `entry.id` in the response. Add a method to `PromptLogStore` in `prompt_log.py`:
```python
def get_last_id(self) -> str | None:
    with self._lock:
        return self._buffer[-1].id if self._buffer else None
```
Then call `prompt_store.get_last_id()` in each API endpoint after the AI call completes, and include it in the response dict.

- [ ] **Step 3: In each AI result component, call `registerResult`**

```jsx
import { usePromptRating } from '../contexts/PromptRatingContext'

// In component:
const { registerResult } = usePromptRating()

// After AI response arrives:
useEffect(() => {
  if (result?.log_id) {
    registerResult(result.log_id)
  }
}, [result?.log_id])
```

- [ ] **Step 4: Verify end-to-end**

1. Trigger an AI analysis on NatalChart page
2. Navigate to Transits tab
3. Rating modal should appear with the correct log_id being submitted

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/pages/
git commit -m "feat(frontend): wire registerResult into AI result components for rating tracking"
```

---

### Task 4: Build global `FeedbackButton` component

**Files:**
- Create: `frontend/src/components/FeedbackButton.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Create `FeedbackButton.jsx`**

```jsx
// frontend/src/components/FeedbackButton.jsx
import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

// value = internal caller key sent to backend (matches prompt_versions.caller)
const CALLER_OPTIONS = [
  { label: '本命盘解读',    value: 'interpret_planets' },
  { label: '行运分析',      value: 'transits_full_new' },
  { label: '合盘',          value: 'analyze_synastry' },
  { label: '太阳回归',      value: 'analyze_solar_return' },
  { label: '出生时间校正',  value: 'analyze_rectification' },
  { label: '其他 / 整体体验', value: null },
]

const OVERLAY = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 9998,
}
const CARD = {
  background: '#1a1a2e', border: '1px solid #3a3a6a',
  borderRadius: '12px', padding: '28px 32px',
  width: '400px', maxWidth: '92vw',
  display: 'flex', flexDirection: 'column', gap: '16px',
}

export default function FeedbackButton() {
  const [open, setOpen] = useState(false)
  const [selectedCaller, setSelectedCaller] = useState(null)
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const { authHeaders } = useAuth()

  function handleOpen() {
    setOpen(true)
    setSelectedCaller(null)
    setContent('')
    setDone(false)
  }

  async function handleSubmit() {
    if (!content.trim() || !selectedCaller) return
    setSubmitting(true)
    try {
      await fetch('/api/user/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ caller_label: selectedCaller || '其他', content: content.trim() }),
      })
      setDone(true)
      setTimeout(() => setOpen(false), 1500)
    } catch (e) {
      console.error('Feedback submit failed:', e)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={handleOpen}
        title="反馈"
        style={{
          position: 'fixed', bottom: '24px', right: '24px',
          width: '44px', height: '44px', borderRadius: '50%',
          background: '#1a1a2e', border: '1px solid #3a3a6a',
          color: '#8888aa', fontSize: '1.2rem', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9990, transition: 'border-color 0.15s',
          boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = '#c9a84c'}
        onMouseLeave={e => e.currentTarget.style.borderColor = '#3a3a6a'}
      >
        💬
      </button>

      {/* Modal */}
      {open && (
        <div style={OVERLAY} onClick={e => e.target === e.currentTarget && setOpen(false)}>
          <div style={CARD}>
            {done ? (
              <p style={{ color: '#c9a84c', textAlign: 'center', margin: 0 }}>感谢你的反馈！</p>
            ) : (
              <>
                <p style={{ color: '#c9c9e0', margin: 0, fontWeight: 600 }}>你想反馈哪个功能？</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {CALLER_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '10px',
                        cursor: 'pointer', color: '#c9c9e0', padding: '6px 0',
                      }}
                    >
                      <input
                        type="radio"
                        name="caller"
                        value={opt.value}
                        checked={selectedCaller === opt.value}
                        onChange={() => setSelectedCaller(opt.value)}
                        style={{ accentColor: '#c9a84c' }}
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
                <textarea
                  placeholder="请输入你的反馈…"
                  value={content}
                  onChange={e => setContent(e.target.value)}
                  rows={4}
                  style={{
                    background: '#0d0d1f', border: '1px solid #3a3a6a', borderRadius: '6px',
                    color: '#c9c9e0', padding: '10px', resize: 'none', fontSize: '0.9rem',
                  }}
                />
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                  <button
                    onClick={() => setOpen(false)}
                    style={{ padding: '8px 18px', background: 'transparent', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#8888aa', cursor: 'pointer' }}
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={!content.trim() || !selectedCaller || submitting}
                    style={{
                      padding: '8px 18px',
                      background: content.trim() && selectedCaller ? '#c9a84c' : '#3a3a6a',
                      border: 'none', borderRadius: '6px',
                      color: content.trim() && selectedCaller ? '#0a0a1a' : '#5a5a8a',
                      fontWeight: 600,
                      cursor: content.trim() && selectedCaller ? 'pointer' : 'not-allowed',
                    }}
                  >
                    {submitting ? '提交中…' : '提交'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 2: Add `FeedbackButton` to `App.jsx`**

Import and place it inside the router (so it has access to auth context) but outside Routes:

```jsx
import FeedbackButton from './components/FeedbackButton'

// In the JSX, after </Routes>:
<FeedbackButton />
```

- [ ] **Step 3: Test the feedback button**

1. Open any page in the app
2. Click the 💬 button in the bottom-right
3. Select a category, type a message, click Submit
4. "感谢你的反馈！" appears, modal closes after 1.5s
5. Check `user_feedback` table in Turso — row should appear

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/FeedbackButton.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add global FeedbackButton with category selection and text input"
```

---

### Task 5: Build Admin prompt versions list page

**Files:**
- Create: `frontend/src/pages/AdminPrompts.jsx`
- Modify: `frontend/src/App.jsx` (add route + nav item for admin users)

- [ ] **Step 1: Create `AdminPrompts.jsx`**

```jsx
// frontend/src/pages/AdminPrompts.jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const CALLER_LABELS = {
  interpret_planets: '本命盘行星解读',
  transits_single: '单日行运',
  transits_full_new: '行运完整分析（新）',
  transits_full_summary: '行运完整分析（综述）',
  generate: 'RAG 基础问答',
  chat_with_chart: '星盘对话',
  analyze_synastry: '合盘分析',
  analyze_solar_return: '太阳回归',
  analyze_rectification: '出生时间校正',
  generate_asc_quiz: '上升测验',
  calc_confidence: '置信度计算',
  system: '系统 Prompt',
}

const STATUS_BADGE = {
  deployed:   { bg: '#1a3a1a', color: '#4caf50', label: '线上' },
  draft:      { bg: '#2a2a0a', color: '#c9a84c', label: '草稿' },
  superseded: { bg: '#1a1a2e', color: '#5a5a8a', label: '已取代' },
  retired:    { bg: '#1a1a2e', color: '#5a5a8a', label: '已退役' },
}

export default function AdminPrompts() {
  const { authHeaders, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [caller, setCaller] = useState(Object.keys(CALLER_LABELS)[0])
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(false)
  const [showRetired, setShowRetired] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) return
    setLoading(true)
    fetch(`/api/admin/prompt-versions?caller=${caller}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setVersions)
      .finally(() => setLoading(false))
  }, [caller, isAuthenticated])

  const visible = versions.filter(v =>
    showRetired || !['superseded', 'retired'].includes(v.status)
  )

  async function handleNewDraft() {
    const deployed = versions.find(v => v.status === 'deployed')
    const resp = await fetch('/api/admin/prompt-versions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        caller,
        prompt_text: deployed?.prompt_text || '',
        system_instruction: deployed?.system_instruction || '',
      }),
    })
    const newVersion = await resp.json()
    navigate(`/admin/prompts/${newVersion.id}`)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '860px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
        <h2 style={{ color: '#c9c9e0', margin: 0 }}>Prompt 版本管理</h2>
        <select
          value={caller}
          onChange={e => setCaller(e.target.value)}
          style={{ background: '#1a1a2e', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#c9c9e0', padding: '6px 12px', fontSize: '0.9rem' }}
        >
          {Object.entries(CALLER_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button
          onClick={handleNewDraft}
          style={{ marginLeft: 'auto', padding: '8px 18px', background: '#c9a84c', border: 'none', borderRadius: '6px', color: '#0a0a1a', fontWeight: 600, cursor: 'pointer' }}
        >
          + 新建草稿
        </button>
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#8888aa', fontSize: '0.85rem', marginBottom: '16px', cursor: 'pointer' }}>
        <input type="checkbox" checked={showRetired} onChange={e => setShowRetired(e.target.checked)} style={{ accentColor: '#c9a84c' }} />
        显示已退役/已取代版本
      </label>

      {loading ? (
        <p style={{ color: '#8888aa' }}>加载中…</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {visible.map(v => {
            const badge = STATUS_BADGE[v.status] || STATUS_BADGE.retired
            return (
              <div
                key={v.id}
                onClick={() => v.status === 'draft' && navigate(`/admin/prompts/${v.id}`)}
                style={{
                  background: v.status === 'deployed' ? '#0f1f0f' : '#12121f',
                  border: `1px solid ${v.status === 'deployed' ? '#2a4a2a' : '#2a2a4a'}`,
                  borderRadius: '8px', padding: '14px 18px',
                  display: 'flex', alignItems: 'center', gap: '16px',
                  cursor: v.status === 'draft' ? 'pointer' : 'default',
                  transition: 'border-color 0.15s',
                }}
              >
                <span style={{ fontWeight: 700, color: '#c9c9e0', minWidth: '50px' }}>{v.version_tag}</span>
                <span style={{
                  padding: '2px 10px', borderRadius: '12px',
                  background: badge.bg, color: badge.color,
                  fontSize: '0.78rem', fontWeight: 600,
                }}>
                  {badge.label}
                </span>
                <span style={{ color: '#5a5a8a', fontSize: '0.82rem' }}>
                  {v.created_at?.slice(0, 10)}
                </span>
                {v.status === 'draft' && (
                  <span style={{ marginLeft: 'auto', color: '#c9a84c', fontSize: '0.82rem' }}>
                    点击查看 →
                  </span>
                )}
              </div>
            )
          })}
          {visible.length === 0 && (
            <p style={{ color: '#5a5a8a' }}>暂无版本</p>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add route in `App.jsx`**

```jsx
import AdminPrompts from './pages/AdminPrompts'
import AdminPromptDetail from './pages/AdminPromptDetail'  // created in Task 6
```

Add routes inside `<Routes>`:
```jsx
<Route path="/admin/prompts" element={<AdminPrompts />} />
<Route path="/admin/prompts/:id" element={<AdminPromptDetail />} />
```

`NAV_ITEMS` is a module-level constant that cannot access auth state. Add the admin item dynamically inside `AppInner` where `useAuth()` is accessible:

```jsx
function AppInner() {
  const { isAuthenticated, isAdmin } = useAuth()
  // ...
  const navItems = [
    ...NAV_ITEMS,
    ...(isAuthenticated && isAdmin ? [{ path: '/admin/prompts', label: '管理' }] : []),
  ]
  // Replace NAV_ITEMS with navItems when rendering the nav links
}
```

- [ ] **Step 3: Test the page**

Navigate to `/admin/prompts`. Should show the seeded v1 entries for each caller.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminPrompts.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add admin prompt versions list page"
```

---

### Task 6: Build Admin prompt detail / test comparison page

**Files:**
- Create: `frontend/src/pages/AdminPromptDetail.jsx`

- [ ] **Step 1: Create `AdminPromptDetail.jsx`**

```jsx
// frontend/src/pages/AdminPromptDetail.jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function AdminPromptDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { authHeaders } = useAuth()

  const [version, setVersion] = useState(null)
  const [deployed, setDeployed] = useState(null)
  const [draftText, setDraftText] = useState('')
  const [charts, setCharts] = useState([])
  const [selectedChart, setSelectedChart] = useState(null)
  const [running, setRunning] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [adminNote, setAdminNote] = useState('')
  const [adminScore, setAdminScore] = useState(null)
  const [submittingEval, setSubmittingEval] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [revising, setRevising] = useState(false)
  const saveTimer = useRef(null)

  // Load version
  useEffect(() => {
    fetch(`/api/admin/prompt-versions/${id}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(v => {
        setVersion(v)
        setDraftText(v.prompt_text || '')
        // Load deployed version for comparison
        return fetch(`/api/admin/prompt-versions?caller=${v.caller}`, { headers: authHeaders() })
      })
      .then(r => r.json())
      .then(versions => {
        const dep = versions.find(v => v.status === 'deployed')
        setDeployed(dep || null)
      })
  }, [id])

  // Load admin's saved charts for test selection
  useEffect(() => {
    fetch('/api/charts', { headers: authHeaders() })
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : data.charts || []
        setCharts(list.filter(c => !c.is_guest))
        if (list.length > 0) setSelectedChart(list[0].id)
      })
  }, [])

  // Auto-save draft text with debounce
  function handleDraftChange(text) {
    setDraftText(text)
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      fetch(`/api/admin/prompt-versions/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ prompt_text: text }),
      })
    }, 1000)
  }

  async function handleRunTest() {
    if (!selectedChart) return
    setRunning(true)
    setTestResult(null)
    try {
      const resp = await fetch(`/api/admin/prompt-versions/${id}/run-test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ chart_id: selectedChart }),
      })
      setTestResult(await resp.json())
    } catch (e) {
      console.error('run-test failed:', e)
    } finally {
      setRunning(false)
    }
  }

  async function handleSubmitAdminEval() {
    if (!testResult?.log_id) return
    setSubmittingEval(true)
    try {
      await fetch('/api/admin/prompt-evaluations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          log_id: testResult.log_id,
          score_overall: adminScore,
          notes: adminNote,
        }),
      })
    } finally {
      setSubmittingEval(false)
    }
  }

  async function handleRevise() {
    setRevising(true)
    try {
      const resp = await fetch(`/api/admin/prompt-versions/${id}/revise`, {
        method: 'POST', headers: authHeaders(),
      })
      const newVersion = await resp.json()
      navigate(`/admin/prompts/${newVersion.id}`)
    } finally {
      setRevising(false)
    }
  }

  async function handleDeploy() {
    if (!window.confirm(`确认将此草稿部署为新版本？当前线上版本将进入退役状态。`)) return
    setDeploying(true)
    try {
      await fetch(`/api/admin/prompt-versions/${id}/deploy`, {
        method: 'POST', headers: authHeaders(),
      })
      navigate('/admin/prompts')
    } finally {
      setDeploying(false)
    }
  }

  if (!version) return <p style={{ color: '#8888aa', padding: '24px' }}>加载中…</p>

  const EVAL_SCORES = [1, 2, 3, 4, 5]

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <button onClick={() => navigate('/admin/prompts')} style={{ background: 'transparent', border: 'none', color: '#8888aa', cursor: 'pointer', fontSize: '0.9rem' }}>← 返回</button>
        <h2 style={{ color: '#c9c9e0', margin: 0 }}>
          {version.caller} · {version.version_tag} <span style={{ color: '#c9a84c', fontSize: '0.85rem' }}>草稿</span>
        </h2>
      </div>

      {/* Prompt editor — left/right */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
        <div>
          <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>草稿 Prompt（可编辑，自动保存）</p>
          <textarea
            value={draftText}
            onChange={e => handleDraftChange(e.target.value)}
            style={{
              width: '100%', height: '300px', background: '#0d0d1f',
              border: '1px solid #3a3a6a', borderRadius: '6px',
              color: '#c9c9e0', padding: '12px', fontSize: '0.85rem',
              resize: 'vertical', boxSizing: 'border-box',
            }}
          />
        </div>
        <div>
          <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>当前线上版本（{deployed?.version_tag || '无'}，只读）</p>
          <textarea
            readOnly
            value={deployed?.prompt_text || '（暂无线上版本）'}
            style={{
              width: '100%', height: '300px', background: '#0a0a17',
              border: '1px solid #2a2a4a', borderRadius: '6px',
              color: '#5a5a8a', padding: '12px', fontSize: '0.85rem',
              resize: 'vertical', boxSizing: 'border-box',
            }}
          />
        </div>
      </div>

      {/* Run test */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <select
          value={selectedChart || ''}
          onChange={e => setSelectedChart(Number(e.target.value))}
          style={{ background: '#1a1a2e', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#c9c9e0', padding: '8px 12px' }}
        >
          {charts.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <button
          onClick={handleRunTest}
          disabled={running || !selectedChart}
          style={{
            padding: '8px 22px', background: running ? '#3a3a6a' : '#c9a84c',
            border: 'none', borderRadius: '6px', color: running ? '#8888aa' : '#0a0a1a',
            fontWeight: 600, cursor: running ? 'not-allowed' : 'pointer',
          }}
        >
          {running ? '运行中…' : '运行测试'}
        </button>
      </div>

      {/* Test results */}
      {testResult && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
          <div>
            <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>草稿输出（{testResult.latency_ms}ms）</p>
            <div style={{ background: '#0d0d1f', border: '1px solid #3a3a6a', borderRadius: '6px', padding: '12px', color: '#c9c9e0', fontSize: '0.85rem', minHeight: '150px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {testResult.response_text || '（无输出）'}
            </div>
          </div>
          <div>
            <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>线上版本输出（对比）</p>
            <div style={{ background: '#090914', border: '1px solid #2a2a4a', borderRadius: '6px', padding: '12px', color: '#5a5a8a', fontSize: '0.85rem', minHeight: '150px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {testResult.deployed_response || '（无对比数据）'}
            </div>
          </div>
        </div>
      )}

      {/* AI Evaluations */}
      {testResult?.evaluations?.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <p style={{ color: '#c9c9e0', fontWeight: 600, marginBottom: '12px' }}>AI 评价</p>
          {testResult.evaluations.map((ev, i) => (
            <div key={i} style={{ background: '#12121f', border: '1px solid #2a2a4a', borderRadius: '8px', padding: '14px 18px', marginBottom: '10px' }}>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                <span style={{ color: '#c9a84c', fontSize: '0.82rem' }}>{ev.type === 'ai_absolute' ? '绝对评分' : '对比评分'}</span>
                {ev.score_overall && <span style={{ color: '#c9c9e0', fontWeight: 700 }}>{ev.score_overall.toFixed(1)} / 5</span>}
              </div>
              {ev.notes && <p style={{ color: '#c9c9e0', fontSize: '0.85rem', margin: '0 0 8px' }}>{ev.notes}</p>}
              {ev.suggestions?.length > 0 && (
                <ul style={{ color: '#f0a84c', fontSize: '0.82rem', margin: 0, paddingLeft: '18px' }}>
                  {ev.suggestions.map((s, j) => <li key={j}>{s}</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Admin evaluation */}
      {testResult && (
        <div style={{ background: '#12121f', border: '1px solid #2a2a4a', borderRadius: '8px', padding: '18px', marginBottom: '24px' }}>
          <p style={{ color: '#c9c9e0', fontWeight: 600, margin: '0 0 12px' }}>管理员评价</p>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            {EVAL_SCORES.map(s => (
              <button
                key={s}
                onClick={() => setAdminScore(s)}
                style={{
                  width: '36px', height: '36px', borderRadius: '6px',
                  background: adminScore === s ? '#c9a84c' : 'transparent',
                  border: `1px solid ${adminScore === s ? '#c9a84c' : '#3a3a6a'}`,
                  color: adminScore === s ? '#0a0a1a' : '#8888aa',
                  fontWeight: adminScore === s ? 700 : 400,
                  cursor: 'pointer',
                }}
              >
                {s}
              </button>
            ))}
          </div>
          <textarea
            placeholder="文字评价（可选）"
            value={adminNote}
            onChange={e => setAdminNote(e.target.value)}
            rows={3}
            style={{ width: '100%', background: '#0d0d1f', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#c9c9e0', padding: '10px', resize: 'none', fontSize: '0.85rem', boxSizing: 'border-box' }}
          />
          <button
            onClick={handleSubmitAdminEval}
            disabled={submittingEval}
            style={{ marginTop: '10px', padding: '8px 18px', background: '#2a3a5a', border: 'none', borderRadius: '6px', color: '#8888cc', cursor: 'pointer' }}
          >
            {submittingEval ? '保存中…' : '保存评价'}
          </button>
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
        <button
          onClick={handleRevise}
          disabled={revising}
          style={{ padding: '10px 22px', background: 'transparent', border: '1px solid #3a3a6a', borderRadius: '6px', color: '#8888aa', cursor: 'pointer' }}
        >
          {revising ? '创建中…' : '保存草稿并继续修改'}
        </button>
        <button
          onClick={handleDeploy}
          disabled={deploying}
          style={{ padding: '10px 22px', background: '#2a4a2a', border: '1px solid #4a8a4a', borderRadius: '6px', color: '#4caf50', fontWeight: 600, cursor: 'pointer' }}
        >
          {deploying ? '部署中…' : `确认部署为下一版本`}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Test the full admin flow**

1. Go to `/admin/prompts`, select `interpret_planets`
2. Click `+ 新建草稿` → should navigate to detail page with current v1 content pre-filled
3. Edit the prompt text (auto-saves after 1 second)
4. Select a saved chart, click `运行测试`
5. Verify both output panels populate, AI evaluations appear
6. Fill in admin score + notes, click `保存评价`
7. Click `保存草稿并继续修改` → new draft version created (v1.2)
8. Go back, click the new draft, click `确认部署` → becomes v2

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AdminPromptDetail.jsx
git commit -m "feat(frontend): add admin prompt detail page with test comparison and evaluation"
```

---
