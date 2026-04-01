import { useState } from 'react'
import { apiFetch } from '../utils/apiFetch'
import { usePromptRating } from '../contexts/PromptRatingContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

/**
 * Generic hook for AI/RAG interpretation endpoints.
 *
 * Usage:
 *   const interp = useInterpret('/api/interpret/synastry')
 *   await interp.run({ aspects, ... })   // returns parsed JSON or null on error
 *   interp.loading / interp.result / interp.error
 *   interp.reset()                        // clear result + error
 */
export function useInterpret(endpoint) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const { registerResult } = usePromptRating()

  async function run(body, extraHeaders = {}) {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...extraHeaders },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => `HTTP ${res.status}`)
        let msg = text
        try { const j = JSON.parse(text); msg = j.detail || text } catch { /* use raw text */ }
        throw new Error(msg)
      }
      const json = await res.json()
      setResult(json)

      // 注册 log_id 到评分 context，用于导航拦截
      if (json?.log_id) {
        registerResult(json.log_id)
      }

      return json          // caller can use result immediately without waiting for re-render
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setResult(null)
    setError(null)
  }

  return { run, loading, result, error, reset }
}