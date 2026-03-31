import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../utils/apiFetch'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export default function Analytics() {
  const { authHeaders, isAuthenticated } = useAuth()
  const [summary, setSummary] = useState([])
  const [records, setRecords] = useState([])
  const [report, setReport] = useState('')
  const [loadingData, setLoadingData] = useState(true)
  const [loadingReport, setLoadingReport] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!isAuthenticated) { setLoadingData(false); return }
    const headers = authHeaders()
    apiFetch(`${API_BASE}/api/admin/analytics`, { headers })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setSummary(d.summary); setRecords(d.records) })
      .catch(e => setError(`加载失败: ${e}`))
      .finally(() => setLoadingData(false))
  }, [isAuthenticated])

  async function handleGenerateReport() {
    setLoadingReport(true)
    setReport('')
    try {
      const res = await apiFetch(`${API_BASE}/api/admin/analytics/report`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) throw new Error(res.status)
      const d = await res.json()
      setReport(d.report)
    } catch (e) {
      setReport(`生成失败: ${e.message}`)
    } finally {
      setLoadingReport(false)
    }
  }

  if (!isAuthenticated) {
    return (
      <div style={{ color: '#8888aa', padding: '40px', textAlign: 'center' }}>
        请先登录
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 16px', color: '#c8c8e8' }}>
      <h1 style={{ color: '#c9a84c', fontSize: '1.3rem', marginBottom: '24px' }}>
        ✦ RAG 质量分析
      </h1>

      {/* 生成报告按钮 */}
      <button
        onClick={handleGenerateReport}
        disabled={loadingReport}
        style={{
          padding: '10px 24px', marginBottom: '24px',
          backgroundColor: loadingReport ? '#2a2a4a' : '#c9a84c',
          color: loadingReport ? '#8888aa' : '#0a0a1a',
          border: 'none', borderRadius: '8px',
          fontWeight: 600, fontSize: '0.95rem',
          cursor: loadingReport ? 'not-allowed' : 'pointer',
        }}
      >
        {loadingReport ? '生成中…' : '✦ 生成 AI 分析报告'}
      </button>

      {/* AI 报告 */}
      {report && (
        <div style={{
          backgroundColor: '#0d0d22', border: '1px solid #2a2a5a',
          borderRadius: '10px', padding: '20px', marginBottom: '32px',
          whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: '0.95rem',
        }}>
          {report}
        </div>
      )}

      {error && <div style={{ color: '#ff6666', marginBottom: '16px' }}>{error}</div>}

      {/* 聚合摘要表 */}
      {!loadingData && summary.length > 0 && (
        <>
          <h2 style={{ color: '#8888aa', fontSize: '0.9rem', marginBottom: '12px', letterSpacing: '0.1em' }}>
            各类问题 RAG 统计
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '32px', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2a5a', color: '#8888aa' }}>
                {['类型', '数量', '平均检索分', '书籍引用率'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summary.map(r => (
                <tr key={r.label} style={{ borderBottom: '1px solid #1a1a3a' }}>
                  <td style={{ padding: '8px 12px', color: '#c9a84c' }}>{r.label}</td>
                  <td style={{ padding: '8px 12px' }}>{r.count}</td>
                  <td style={{ padding: '8px 12px', color: r.avg_score < 0.6 ? '#ff8866' : '#88cc88' }}>
                    {r.avg_score.toFixed(3)}
                  </td>
                  <td style={{ padding: '8px 12px' }}>{(r.cite_rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* 原始记录表 */}
      {!loadingData && records.length > 0 && (
        <>
          <h2 style={{ color: '#8888aa', fontSize: '0.9rem', marginBottom: '12px', letterSpacing: '0.1em' }}>
            最近 {records.length} 条记录
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2a5a', color: '#8888aa' }}>
                {['#', '类型', 'RAG分', '引用', '时间'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 10px', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid #12122a' }}>
                  <td style={{ padding: '6px 10px', color: '#4a4a6a' }}>{r.id}</td>
                  <td style={{ padding: '6px 10px', color: '#c9a84c' }}>{r.label}</td>
                  <td style={{ padding: '6px 10px', color: r.max_rag_score < 0.6 ? '#ff8866' : '#88cc88' }}>
                    {r.max_rag_score.toFixed(3)}
                  </td>
                  <td style={{ padding: '6px 10px' }}>{r.any_cited ? '✓' : '—'}</td>
                  <td style={{ padding: '6px 10px', color: '#6666aa' }}>
                    {r.created_at?.slice(0, 16).replace('T', ' ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {!loadingData && summary.length === 0 && (
        <div style={{ color: '#6666aa', textAlign: 'center', padding: '40px' }}>
          暂无数据 — 在占星对话模块积累对话后再来查看
        </div>
      )}
    </div>
  )
}
