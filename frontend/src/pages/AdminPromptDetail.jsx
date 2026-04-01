// frontend/src/pages/AdminPromptDetail.jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../utils/apiFetch'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const EVAL_SCORES = [1, 2, 3, 4, 5]

export default function AdminPromptDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { authHeaders, isAdmin } = useAuth()

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

  // Load version + deployed version for comparison
  useEffect(() => {
    apiFetch(`${API_BASE}/api/admin/prompt-versions/${id}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(v => {
        setVersion(v)
        setDraftText(v.prompt_text || '')
        return apiFetch(`${API_BASE}/api/admin/prompt-versions?caller=${v.caller}`, {
          headers: authHeaders(),
        })
      })
      .then(r => r.json())
      .then(versions => {
        const arr = Array.isArray(versions) ? versions : []
        const dep = arr.find(v => v.status === 'deployed')
        setDeployed(dep || null)
      })
      .catch(e => console.error('Load version failed:', e))
  }, [id])

  // Load saved charts for test selection
  useEffect(() => {
    apiFetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : data.charts || []
        const filtered = list.filter(c => !c.is_guest)
        setCharts(filtered)
        if (filtered.length > 0) setSelectedChart(filtered[0].id)
      })
      .catch(() => setCharts([]))
  }, [])

  // Auto-save draft text with debounce
  function handleDraftChange(text) {
    setDraftText(text)
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      apiFetch(`${API_BASE}/api/admin/prompt-versions/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ prompt_text: text }),
      }).catch(e => console.error('Auto-save failed:', e))
    }, 1000)
  }

  async function handleRunTest() {
    if (!selectedChart) return
    setRunning(true)
    setTestResult(null)
    try {
      const resp = await apiFetch(`${API_BASE}/api/admin/prompt-versions/${id}/run-test`, {
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
      await apiFetch(`${API_BASE}/api/admin/prompt-evaluations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          log_id: testResult.log_id,
          score_overall: adminScore,
          notes: adminNote,
        }),
      })
    } catch (e) {
      console.error('Admin eval failed:', e)
    } finally {
      setSubmittingEval(false)
    }
  }

  async function handleRevise() {
    setRevising(true)
    try {
      const resp = await apiFetch(`${API_BASE}/api/admin/prompt-versions/${id}/revise`, {
        method: 'POST',
        headers: authHeaders(),
      })
      const newVersion = await resp.json()
      navigate(`/admin/prompts/${newVersion.id}`)
    } catch (e) {
      console.error('Revise failed:', e)
    } finally {
      setRevising(false)
    }
  }

  async function handleDeploy() {
    if (!window.confirm('确认将此草稿部署为新版本？当前线上版本将进入退役状态。')) return
    setDeploying(true)
    try {
      await apiFetch(`${API_BASE}/api/admin/prompt-versions/${id}/deploy`, {
        method: 'POST',
        headers: authHeaders(),
      })
      navigate('/admin/prompts')
    } catch (e) {
      console.error('Deploy failed:', e)
    } finally {
      setDeploying(false)
    }
  }

  if (!isAdmin) {
    return <p style={{ color: '#8888aa', padding: '24px' }}>无权限访问</p>
  }

  if (!version) {
    return <p style={{ color: '#8888aa', padding: '24px' }}>加载中…</p>
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <button
          onClick={() => navigate('/admin/prompts')}
          style={{ background: 'transparent', border: 'none', color: '#8888aa', cursor: 'pointer', fontSize: '0.9rem' }}
        >
          ← 返回
        </button>
        <h2 style={{ color: '#c9c9e0', margin: 0 }}>
          {version.caller} · {version.version_tag}{' '}
          <span style={{ color: '#c9a84c', fontSize: '0.85rem' }}>草稿</span>
        </h2>
      </div>

      {/* Prompt editor — left/right */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
        <div>
          <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>
            草稿 Prompt（可编辑，自动保存）
          </p>
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
          <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>
            当前线上版本（{deployed?.version_tag || '无'}，只读）
          </p>
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
          style={{
            background: '#1a1a2e', border: '1px solid #3a3a6a',
            borderRadius: '6px', color: '#c9c9e0', padding: '8px 12px',
          }}
        >
          {charts.map(c => (
            <option key={c.id} value={c.id}>{c.label || c.name || `Chart #${c.id}`}</option>
          ))}
        </select>
        <button
          onClick={handleRunTest}
          disabled={running || !selectedChart}
          style={{
            padding: '8px 22px',
            background: running ? '#3a3a6a' : '#c9a84c',
            border: 'none', borderRadius: '6px',
            color: running ? '#8888aa' : '#0a0a1a',
            fontWeight: 600,
            cursor: running ? 'not-allowed' : 'pointer',
          }}
        >
          {running ? '运行中…' : '运行测试'}
        </button>
      </div>

      {/* Test results — side by side */}
      {testResult && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
          <div>
            <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>
              草稿输出（{testResult.latency_ms}ms）
            </p>
            <div style={{
              background: '#0d0d1f', border: '1px solid #3a3a6a',
              borderRadius: '6px', padding: '12px', color: '#c9c9e0',
              fontSize: '0.85rem', minHeight: '150px',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              maxHeight: '400px', overflowY: 'auto',
            }}>
              {testResult.response_text || '（无输出）'}
            </div>
          </div>
          <div>
            <p style={{ color: '#8888aa', fontSize: '0.82rem', margin: '0 0 6px' }}>
              线上版本输出（对比）
            </p>
            <div style={{
              background: '#090914', border: '1px solid #2a2a4a',
              borderRadius: '6px', padding: '12px', color: '#5a5a8a',
              fontSize: '0.85rem', minHeight: '150px',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              maxHeight: '400px', overflowY: 'auto',
            }}>
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
            <div key={i} style={{
              background: '#12121f', border: '1px solid #2a2a4a',
              borderRadius: '8px', padding: '14px 18px', marginBottom: '10px',
            }}>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                <span style={{ color: '#c9a84c', fontSize: '0.82rem' }}>
                  {ev.type === 'ai_absolute' ? '绝对评分' : '对比评分'}
                </span>
                {ev.score_overall && (
                  <span style={{ color: '#c9c9e0', fontWeight: 700 }}>
                    {ev.score_overall.toFixed(1)} / 5
                  </span>
                )}
              </div>
              {ev.notes && (
                <p style={{ color: '#c9c9e0', fontSize: '0.85rem', margin: '0 0 8px' }}>
                  {ev.notes}
                </p>
              )}
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
        <div style={{
          background: '#12121f', border: '1px solid #2a2a4a',
          borderRadius: '8px', padding: '18px', marginBottom: '24px',
        }}>
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
            style={{
              width: '100%', background: '#0d0d1f',
              border: '1px solid #3a3a6a', borderRadius: '6px',
              color: '#c9c9e0', padding: '10px', resize: 'none',
              fontSize: '0.85rem', boxSizing: 'border-box',
            }}
          />
          <button
            onClick={handleSubmitAdminEval}
            disabled={submittingEval}
            style={{
              marginTop: '10px', padding: '8px 18px',
              background: '#2a3a5a', border: 'none',
              borderRadius: '6px', color: '#8888cc', cursor: 'pointer',
            }}
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
          style={{
            padding: '10px 22px', background: 'transparent',
            border: '1px solid #3a3a6a', borderRadius: '6px',
            color: '#8888aa', cursor: 'pointer',
          }}
        >
          {revising ? '创建中…' : '保存草稿并继续修改'}
        </button>
        <button
          onClick={handleDeploy}
          disabled={deploying}
          style={{
            padding: '10px 22px', background: '#2a4a2a',
            border: '1px solid #4a8a4a', borderRadius: '6px',
            color: '#4caf50', fontWeight: 600, cursor: 'pointer',
          }}
        >
          {deploying ? '部署中…' : '确认部署为下一版本'}
        </button>
      </div>
    </div>
  )
}