import { useState, useEffect } from 'react'
import ChartForm from '../components/ChartForm'
import PlanetTable from '../components/PlanetTable'
import ChartWheel from '../components/ChartWheel'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export default function NatalChart() {
  const [result, setResult] = useState(null)
  const [svgContent, setSvgContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lastFormData, setLastFormData] = useState(null)
  const [lastLocationName, setLastLocationName] = useState(null)

  const [savedCharts, setSavedCharts] = useState([])
  const [saving, setSaving] = useState(false)
  const [savedId, setSavedId] = useState(null)  // id of currently loaded saved chart

  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatMode, setChatMode] = useState('interpret')

  useEffect(() => { fetchSavedCharts() }, [])

  async function fetchSavedCharts() {
    try {
      const res = await fetch(`${API_BASE}/api/charts`)
      if (res.ok) setSavedCharts(await res.json())
    } catch { /* network error, keep empty list */ }
  }

  async function handleSubmit(formData, locationName) {
    setLoading(true)
    setError(null)
    setResult(null)
    setSvgContent(null)
    setSavedId(null)
    setLastFormData(formData)
    setLastLocationName(locationName)

    try {
      const res = await fetch(`${API_BASE}/api/natal_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setResult(data)

      const svgRes = await fetch(`${API_BASE}/api/svg_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal_chart: formData,
          chart_type: 'natal',
          show_aspects: true,
          language: formData.language || 'zh',
          theme: 'dark',
        }),
      })
      if (svgRes.ok) setSvgContent(await svgRes.text())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!result || !lastFormData) return
    setSaving(true)
    try {
      const label = lastFormData.name
        ? `${lastFormData.name} · ${lastFormData.birth_year}/${lastFormData.birth_month}/${lastFormData.birth_day}`
        : `星盘 ${lastFormData.birth_year}/${lastFormData.birth_month}/${lastFormData.birth_day}`

      const res = await fetch(`${API_BASE}/api/charts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label,
          name: lastFormData.name || null,
          birth_year: lastFormData.year,
          birth_month: lastFormData.month,
          birth_day: lastFormData.day,
          birth_hour: lastFormData.hour,
          birth_minute: lastFormData.minute,
          location_name: lastLocationName || null,
          latitude: lastFormData.latitude,
          longitude: lastFormData.longitude,
          tz_str: lastFormData.tz_str,
          house_system: lastFormData.house_system,
          language: lastFormData.language,
          chart_data: result,
          svg_data: svgContent || null,
        }),
      })
      if (!res.ok) throw new Error()
      const saved = await res.json()
      setSavedId(saved.id)
      await fetchSavedCharts()
    } catch {
      setError('保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleLoad(summary) {
    setSavedId(summary.id)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/charts/${summary.id}`)
      if (!res.ok) throw new Error()
      const chart = await res.json()
      setLastFormData({
        name: chart.name || '',
        year: chart.birth_year,
        month: chart.birth_month,
        day: chart.birth_day,
        hour: chart.birth_hour,
        minute: chart.birth_minute,
        latitude: chart.latitude,
        longitude: chart.longitude,
        tz_str: chart.tz_str,
        house_system: chart.house_system,
        language: chart.language,
      })
      setLastLocationName(chart.location_name)
      if (chart.chart_data) setResult(chart.chart_data)
      if (chart.svg_data) setSvgContent(chart.svg_data)
    } catch {
      setError('加载失败')
      setSavedId(null)
    }
  }

  async function handleChat(e) {
    e.preventDefault()
    if (!chatInput.trim() || !result) return
    const question = chatInput.trim()
    setChatInput('')
    setMessages(prev => [...prev, { role: 'user', text: question }])
    setChatLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/interpret/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: question, chart_data: result, k: 5, mode: chatMode }),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', text: data.answer }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: `⚠ ${e.message}` }])
    } finally {
      setChatLoading(false)
    }
  }

  async function handleDelete(id, e) {
    e.stopPropagation()
    await fetch(`${API_BASE}/api/charts/${id}`, { method: 'DELETE' })
    if (savedId === id) {
      setSavedId(null)
      setResult(null)
      setSvgContent(null)
      setLastFormData(null)
    }
    await fetchSavedCharts()
  }

  return (
    <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start', width: '100%' }}>

      {/* Saved charts sidebar */}
      <div style={{ flex: '0 0 200px', minWidth: '160px' }}>
        <div style={{
          backgroundColor: '#12122a',
          border: '1px solid #2a2a5a',
          borderRadius: '10px',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '10px 14px',
            borderBottom: '1px solid #2a2a5a',
            color: '#c9a84c',
            fontSize: '0.7rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}>
            已保存星盘
          </div>
          {savedCharts.length === 0 ? (
            <div style={{ padding: '16px 14px', color: '#3a3a6a', fontSize: '0.75rem' }}>暂无记录</div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {savedCharts.map(c => (
                <li
                  key={c.id}
                  onClick={() => handleLoad(c)}
                  style={{
                    padding: '10px 14px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #1a1a35',
                    backgroundColor: savedId === c.id ? '#1e1e40' : 'transparent',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: '6px',
                  }}
                  onMouseEnter={e => { if (savedId !== c.id) e.currentTarget.style.backgroundColor = '#16163a' }}
                  onMouseLeave={e => { if (savedId !== c.id) e.currentTarget.style.backgroundColor = 'transparent' }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      color: savedId === c.id ? '#c9a84c' : '#c8c8e8',
                      fontSize: '0.78rem',
                      fontWeight: 500,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {c.name || '无名'}
                    </div>
                    <div style={{ color: '#6666aa', fontSize: '0.68rem', marginTop: '2px' }}>
                      {c.birth_year}/{c.birth_month}/{c.birth_day}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(c.id, e)}
                    style={{
                      background: 'none', border: 'none', color: '#4a3a5a',
                      cursor: 'pointer', fontSize: '0.75rem', padding: '0',
                      flexShrink: 0, lineHeight: 1,
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = '#cc6666'}
                    onMouseLeave={e => e.currentTarget.style.color = '#4a3a5a'}
                  >✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', gap: '24px', alignItems: 'flex-start', flexWrap: 'wrap' }}>

        {/* Left column: form */}
        <div style={{ flex: '0 0 380px', minWidth: '280px' }}>
          <ChartForm onSubmit={handleSubmit} loading={loading} />

          {error && (
            <div className="mt-4 p-3 rounded-lg text-sm"
              style={{ backgroundColor: '#2a1020', color: '#ff8888', border: '1px solid #5a2030' }}>
              ✗ {error}
            </div>
          )}

          {result && !savedId && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="mt-3 w-full py-2 rounded-lg tracking-wider transition-opacity"
              style={{
                backgroundColor: 'transparent',
                border: '1px solid #c9a84c',
                color: '#c9a84c',
                fontSize: '0.85rem',
                opacity: saving ? 0.5 : 1,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              {saving ? '保存中…' : '✦ 保存此星盘'}
            </button>
          )}

          {savedId && (
            <div className="mt-3" style={{ color: '#4a8a4a', fontSize: '0.78rem', textAlign: 'center' }}>
              ✓ 已保存
            </div>
          )}

          {/* Chat box */}
          {result && (
            <div className="mt-6" style={{
              backgroundColor: '#12122a',
              border: '1px solid #2a2a5a',
              borderRadius: '10px',
              overflow: 'hidden',
            }}>
              <div style={{
                padding: '10px 14px',
                borderBottom: '1px solid #2a2a5a',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
                <span style={{ color: '#c9a84c', fontSize: '0.7rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  ✦ 占星对话
                </span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {['interpret', 'rag'].map(m => (
                    <button key={m} onClick={() => setChatMode(m)} style={{
                      fontSize: '0.65rem', padding: '2px 8px', borderRadius: '4px', border: 'none',
                      cursor: 'pointer',
                      backgroundColor: chatMode === m ? '#c9a84c' : '#1e1e40',
                      color: chatMode === m ? '#0a0a1a' : '#6666aa',
                      fontWeight: chatMode === m ? 600 : 400,
                    }}>
                      {m === 'interpret' ? 'AI解读' : 'RAG测试'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Messages */}
              <div style={{ padding: '12px 14px', maxHeight: '320px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {messages.length === 0 && (
                  <div style={{ color: '#3a3a6a', fontSize: '0.78rem' }}>
                    问我关于你星盘的任何问题…
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '90%',
                    backgroundColor: msg.role === 'user' ? '#1e1e50' : '#1a1a35',
                    border: `1px solid ${msg.role === 'user' ? '#3a3a8a' : '#2a2a5a'}`,
                    borderRadius: '8px',
                    padding: '8px 12px',
                    fontSize: '0.82rem',
                    color: '#e8e8ff',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                  }}>
                    {msg.text}
                  </div>
                ))}
                {chatLoading && (
                  <div style={{ color: '#6666aa', fontSize: '0.78rem' }}>思考中…</div>
                )}
              </div>

              {/* Input */}
              <form onSubmit={handleChat} style={{
                display: 'flex', gap: '8px', padding: '10px 14px',
                borderTop: '1px solid #2a2a5a',
              }}>
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  placeholder="问关于星盘的问题…"
                  disabled={chatLoading}
                  style={{
                    flex: 1,
                    backgroundColor: '#0d0d22',
                    border: '1px solid #2a2a5a',
                    color: '#e8e8ff',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    fontSize: '0.82rem',
                    outline: 'none',
                  }}
                />
                <button type="submit" disabled={chatLoading || !chatInput.trim()}
                  style={{
                    backgroundColor: '#c9a84c', color: '#0a0a1a',
                    border: 'none', borderRadius: '6px',
                    padding: '6px 14px', fontWeight: 600,
                    fontSize: '0.82rem',
                    cursor: chatLoading ? 'not-allowed' : 'pointer',
                    opacity: chatLoading || !chatInput.trim() ? 0.5 : 1,
                  }}>
                  发送
                </button>
              </form>
            </div>
          )}
        </div>

        {/* Right column: results */}
        <div style={{ flex: '1 1 400px', minWidth: '300px' }}>
          {!result && !loading && (
            <div className="flex items-center justify-center rounded-xl"
              style={{
                height: '400px',
                backgroundColor: '#12122a',
                border: '1px dashed #2a2a5a',
                color: '#3a3a6a',
                fontSize: '2rem',
              }}>
              ✦
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center rounded-xl"
              style={{
                height: '400px',
                backgroundColor: '#12122a',
                border: '1px solid #2a2a5a',
                color: '#8888aa',
                fontSize: '0.9rem',
              }}>
              计算中…
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {svgContent && <ChartWheel svgContent={svgContent} language={result.input_data?.language} />}
              <PlanetTable planets={result.planets} language={result.input_data?.language} />
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
