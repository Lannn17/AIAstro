import { useState } from 'react'
import { apiFetch } from '../utils/apiFetch'

const CALLERS = ['', 'analyze_planets', 'analyze_transits', 'analyze_synastry', 'analyze_progressions', 'solar_return']

export default function PromptLogModal({ onClose }) {
  const [logs, setLogs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [caller, setCaller] = useState('')
  const [expanded, setExpanded] = useState(null)

  async function fetchLogs() {
    setLoading(true)
    try {
      const q = caller ? `?caller=${caller}` : ''
      const res = await apiFetch(`/api/debug/admin/prompts${q}`)
      if (!res.ok) throw new Error(`${res.status}`)
      setLogs(await res.json())
      setExpanded(null)
    } catch (e) {
      setLogs([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
      <div style={{ background: '#0e0e1e', border: '1px solid #3a3a6a', borderRadius: '12px', width: '100%', maxWidth: '860px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid #2a2a4a' }}>
          <span style={{ color: '#9a8acc', fontSize: '0.8rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Prompt 调用日志</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6666aa', cursor: 'pointer', fontSize: '1.1rem' }}>✕</button>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', gap: '10px', padding: '12px 18px', borderBottom: '1px solid #1a1a3a', alignItems: 'center' }}>
          <select
            value={caller}
            onChange={e => setCaller(e.target.value)}
            style={{ background: '#1a1a30', border: '1px solid #3a3a6a', color: '#c0c0e0', borderRadius: '6px', padding: '6px 10px', fontSize: '0.82rem' }}
          >
            {CALLERS.map(c => <option key={c} value={c}>{c || '全部'}</option>)}
          </select>
          <button
            onClick={fetchLogs}
            disabled={loading}
            style={{ background: '#2a1a4a', border: '1px solid #6a5a9a', color: '#c0a8f0', borderRadius: '6px', padding: '6px 16px', fontSize: '0.82rem', cursor: 'pointer' }}
          >
            {loading ? '加载中…' : '查询'}
          </button>
        </div>

        {/* List */}
        <div style={{ overflowY: 'auto', flex: 1, padding: '8px 0' }}>
          {!logs && (
            <div style={{ color: '#5555aa', fontSize: '0.82rem', padding: '24px', textAlign: 'center' }}>点击「查询」加载日志</div>
          )}
          {logs?.length === 0 && (
            <div style={{ color: '#5555aa', fontSize: '0.82rem', padding: '24px', textAlign: 'center' }}>暂无记录</div>
          )}
          {logs?.map(log => (
            <div key={log.id} style={{ borderBottom: '1px solid #1a1a3a' }}>
              {/* Row */}
              <div
                onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                style={{ display: 'flex', gap: '12px', padding: '10px 18px', cursor: 'pointer', alignItems: 'flex-start' }}
                onMouseEnter={e => e.currentTarget.style.background = '#141428'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{ minWidth: '120px', color: '#6666aa', fontSize: '0.75rem', paddingTop: '2px' }}>{log.timestamp}</div>
                <div style={{ minWidth: '140px', color: '#a07de0', fontSize: '0.78rem', paddingTop: '2px' }}>{log.caller}</div>
                <div style={{ minWidth: '60px', color: '#5588aa', fontSize: '0.75rem', paddingTop: '2px' }}>{log.latency_ms}ms</div>
                <div style={{ color: '#9090b8', fontSize: '0.78rem', lineHeight: 1.5, flex: 1 }}>{log.prompt_preview}</div>
                <div style={{ color: '#4444aa', fontSize: '0.72rem', paddingTop: '2px' }}>{expanded === log.id ? '▲' : '▼'}</div>
              </div>
              {/* Expanded */}
              {expanded === log.id && (
                <div style={{ padding: '0 18px 14px', background: '#080814' }}>
                  <div style={{ color: '#6666aa', fontSize: '0.72rem', marginBottom: '6px', letterSpacing: '0.06em' }}>FULL PROMPT — {log.model_used} · ~{log.prompt_tokens_est} tokens</div>
                  <pre style={{ color: '#a0a0c8', fontSize: '0.76rem', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#0a0a1a', border: '1px solid #1a1a3a', borderRadius: '6px', padding: '12px', margin: 0, maxHeight: '400px', overflowY: 'auto' }}>
                    {log.prompt_text}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
