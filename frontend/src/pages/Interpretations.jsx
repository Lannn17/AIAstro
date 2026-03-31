import { useState } from 'react'
import { apiFetch } from '../utils/apiFetch'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const inputStyle = {
  backgroundColor: '#0d0d22',
  border: '1px solid #2a2a5a',
  color: '#e8e8ff',
  borderRadius: '6px',
  padding: '8px 12px',
  width: '100%',
  outline: 'none',
  fontSize: '0.875rem',
}

export default function Interpretations() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSearch(e) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await apiFetch(`${API_BASE}/api/interpret?query=${encodeURIComponent(query)}`)
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ✦ 解释
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          搜索星盘元素的文字解释
        </p>
      </div>

      <div style={{ maxWidth: '600px' }}>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            style={inputStyle}
            placeholder="例：太阳狮子座 / Sun in Leo"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <button type="submit" disabled={loading}
            style={{
              backgroundColor: '#c9a84c', color: '#0a0a1a',
              border: 'none', borderRadius: '6px',
              padding: '8px 18px', fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.5 : 1,
              whiteSpace: 'nowrap', fontSize: '0.875rem',
            }}>
            {loading ? '搜索中…' : '搜索'}
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3 rounded-lg text-sm"
            style={{ backgroundColor: '#2a1020', color: '#ff8888', border: '1px solid #5a2030' }}>
            ✗ {error}
          </div>
        )}

        {result && (
          <div className="mt-6 p-5 rounded-xl"
            style={{ backgroundColor: '#12122a', border: '1px solid #2a2a5a', color: '#e8e8ff', lineHeight: 1.8 }}>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.9rem' }}>
              {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
