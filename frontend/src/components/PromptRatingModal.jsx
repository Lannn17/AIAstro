// frontend/src/components/PromptRatingModal.jsx
import { useState } from 'react'
import { usePromptRating } from '../contexts/PromptRatingContext'
import { useAuth } from '../contexts/AuthContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

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
      await fetch(`${API_BASE}/api/user/prompt-evaluations`, {
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