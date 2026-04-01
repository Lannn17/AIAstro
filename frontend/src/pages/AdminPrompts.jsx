// frontend/src/pages/AdminPrompts.jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../utils/apiFetch'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

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
  const { authHeaders, isAuthenticated, isAdmin } = useAuth()
  const navigate = useNavigate()
  const [caller, setCaller] = useState(Object.keys(CALLER_LABELS)[0])
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(false)
  const [showRetired, setShowRetired] = useState(false)

  useEffect(() => {
    if (!isAuthenticated || !isAdmin) return
    setLoading(true)
    apiFetch(`${API_BASE}/api/admin/prompt-versions?caller=${caller}`, {
      headers: authHeaders(),
    })
      .then(r => r.json())
      .then(data => setVersions(Array.isArray(data) ? data : []))
      .catch(() => setVersions([]))
      .finally(() => setLoading(false))
  }, [caller, isAuthenticated, isAdmin])

  const visible = versions.filter(v =>
    showRetired || !['superseded', 'retired'].includes(v.status)
  )

  async function handleNewDraft() {
    const deployed = versions.find(v => v.status === 'deployed')
    try {
      const resp = await apiFetch(`${API_BASE}/api/admin/prompt-versions`, {
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
    } catch (e) {
      console.error('Create draft failed:', e)
    }
  }

  if (!isAdmin) {
    return <p style={{ color: '#8888aa', padding: '24px' }}>无权限访问</p>
  }

  return (
    <div style={{ padding: '24px', maxWidth: '860px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <h2 style={{ color: '#c9c9e0', margin: 0 }}>Prompt 版本管理</h2>
        <select
          value={caller}
          onChange={e => setCaller(e.target.value)}
          style={{
            background: '#1a1a2e', border: '1px solid #3a3a6a',
            borderRadius: '6px', color: '#c9c9e0',
            padding: '6px 12px', fontSize: '0.9rem',
          }}
        >
          {Object.entries(CALLER_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button
          onClick={handleNewDraft}
          style={{
            marginLeft: 'auto', padding: '8px 18px',
            background: '#c9a84c', border: 'none',
            borderRadius: '6px', color: '#0a0a1a',
            fontWeight: 600, cursor: 'pointer',
          }}
        >
          + 新建草稿
        </button>
      </div>

      <label style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        color: '#8888aa', fontSize: '0.85rem',
        marginBottom: '16px', cursor: 'pointer',
      }}>
        <input
          type="checkbox"
          checked={showRetired}
          onChange={e => setShowRetired(e.target.checked)}
          style={{ accentColor: '#c9a84c' }}
        />
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
                <span style={{ fontWeight: 700, color: '#c9c9e0', minWidth: '50px' }}>
                  {v.version_tag}
                </span>
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