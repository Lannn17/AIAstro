// frontend/src/components/FeedbackButton.jsx
import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const CALLER_OPTIONS = [
  { label: '本命盘解读',      value: 'interpret_planets' },
  { label: '行运分析',        value: 'transits_full_new' },
  { label: '合盘',            value: 'analyze_synastry' },
  { label: '太阳回归',        value: 'analyze_solar_return' },
  { label: '出生时间校正',    value: 'analyze_rectification' },
  { label: '其他 / 整体体验', value: 'other' },
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
      await fetch(`${API_BASE}/api/user/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ caller_label: selectedCaller, content: content.trim() }),
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