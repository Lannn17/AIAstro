import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
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
  const [chatSummary, setChatSummary] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  const [rectifyOpen, setRectifyOpen] = useState(false)
  const [rectifyEvents, setRectifyEvents] = useState([
    { year: '', month: '', day: '', event_type: 'marriage', weight: 2 }
  ])
  const [approxHour, setApproxHour] = useState('')
  const [timeRangeHours, setTimeRangeHours] = useState('')
  const [rectifyLoading, setRectifyLoading] = useState(false)
  const [rectifyResult, setRectifyResult] = useState(null)
  const [rectifyError, setRectifyError] = useState(null)

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
    setMessages([])
    setChatSummary('')

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
    setMessages([])
    setChatSummary('')
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

  // 滚动摘要：当消息超过8条时，把旧消息压缩成摘要并裁掉，保持 token 消耗恒定
  async function maybeCompress(allMessages) {
    if (allMessages.length < 8) return
    const toSummarize = allMessages.slice(0, -4)  // 除最近4条外全部压缩
    const keep        = allMessages.slice(-4)
    try {
      const res = await fetch(`${API_BASE}/api/interpret/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: toSummarize,
          chart_name: result?.input_data?.name || '',
        }),
      })
      if (!res.ok) return  // 摘要失败时静默保留原历史，不影响主流程
      const { summary } = await res.json()
      setChatSummary(prev => prev ? `${prev}\n${summary}` : summary)
      setMessages(keep)
    } catch { /* 静默失败 */ }
  }

  async function handleChat(e) {
    e.preventDefault()
    if (!chatInput.trim() || !result) return
    const question = chatInput.trim()
    const historySnapshot = messages.slice(-4)  // 最近2轮原始历史
    setChatInput('')
    setMessages(prev => [...prev, { role: 'user', text: question }])
    setChatLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/interpret/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: question,
          chart_data: result,
          k: 5,
          history: historySnapshot,
          summary: chatSummary,
        }),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setMessages(prev => {
        const next = [...prev, { role: 'assistant', text: data.answer, sources: data.sources }]
        maybeCompress(next)  // 后台异步压缩，不阻塞 UI
        return next
      })
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: `⚠ ${e.message}` }])
    } finally {
      setChatLoading(false)
    }
  }

  async function handleRectify() {
    if (!lastFormData) return
    const events = rectifyEvents
      .filter(e => e.year && e.month && e.day)
      .map(e => ({ year: Number(e.year), month: Number(e.month), day: Number(e.day), event_type: e.event_type, weight: Number(e.weight) }))
    if (events.length === 0) { setRectifyError('请至少填写一个完整事件'); return }
    setRectifyLoading(true)
    setRectifyError(null)
    setRectifyResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/rectify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          birth_year: lastFormData.year, birth_month: lastFormData.month, birth_day: lastFormData.day,
          latitude: lastFormData.latitude, longitude: lastFormData.longitude,
          tz_str: lastFormData.tz_str, house_system: lastFormData.house_system,
          events,
          approx_hour: approxHour !== '' ? Number(approxHour) : null,
          approx_minute: null,
          time_range_hours: timeRangeHours !== '' ? Number(timeRangeHours) : null,
          natal_chart_data: result || {},
        }),
      })
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `错误 ${res.status}`) }
      setRectifyResult(await res.json())
    } catch (e) { setRectifyError(e.message) }
    finally { setRectifyLoading(false) }
  }

  function addEvent() {
    if (rectifyEvents.length >= 5) return
    setRectifyEvents(prev => [...prev, { year: '', month: '', day: '', event_type: 'other', weight: 1 }])
  }
  function removeEvent(i) { setRectifyEvents(prev => prev.filter((_, idx) => idx !== i)) }
  function updateEvent(i, field, value) { setRectifyEvents(prev => prev.map((e, idx) => idx === i ? { ...e, [field]: value } : e)) }

  async function handleDelete(id, e) {
    e.stopPropagation()
    if (!window.confirm('确认删除该星盘？此操作无法撤销。')) return
    await fetch(`${API_BASE}/api/charts/${id}`, { method: 'DELETE' })
    if (savedId === id) {
      setSavedId(null)
      setResult(null)
      setSvgContent(null)
      setLastFormData(null)
    }
    await fetchSavedCharts()
  }

  const labelStyle = { color: '#9a8acc', fontSize: '0.78rem', fontWeight: 600, marginBottom: '6px' }
  const inputSm = { background: '#0e0e24', border: '1px solid #2a2a5a', color: '#d0d0e0', borderRadius: '5px', padding: '6px 8px', fontSize: '0.82rem', boxSizing: 'border-box' }

  return (
    <div className="page-layout">

      {/* Saved charts sidebar */}
      <div className="page-sidebar">
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
      <div className="page-main">

        {/* Left column: form */}
        <div className="page-form-col">
          <ChartForm onSubmit={handleSubmit} loading={loading} />

          {error && (
            <div className="mt-4 p-3 rounded-lg text-sm"
              style={{ backgroundColor: '#2a1020', color: '#ff8888', border: '1px solid #5a2030' }}>
              ✗ {error}
            </div>
          )}

          {result && !savedId && !loading && svgContent && (
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

          {/* Chat toggle button */}
          {result && svgContent && (
            <button
              className="mt-4 w-full py-2 rounded-lg tracking-wider"
              onClick={() => { setChatOpen(o => !o); setRectifyOpen(false) }}
              style={{
                backgroundColor: chatOpen ? '#c9a84c' : 'transparent',
                border: '1px solid #c9a84c',
                color: chatOpen ? '#0a0a1a' : '#c9a84c',
                fontSize: '0.88rem',
                cursor: 'pointer',
                fontWeight: chatOpen ? 600 : 400,
              }}
            >
              ✦ 占星对话
            </button>
          )}

          {/* Rectify toggle button */}
          {result && (
            <button
              className="mt-2 w-full py-2 rounded-lg tracking-wider"
              onClick={() => { setRectifyOpen(o => !o); setChatOpen(false) }}
              style={{
                backgroundColor: rectifyOpen ? '#7a6aaa' : 'transparent',
                border: '1px solid #7a6aaa',
                color: rectifyOpen ? '#ffffff' : '#9a8acc',
                fontSize: '0.88rem',
                cursor: 'pointer',
                fontWeight: rectifyOpen ? 600 : 400,
              }}
            >
              ◈ 校对出生时间
            </button>
          )}
        </div>

        {/* Right column: results or chat */}
        <div className="page-result-col">

          {/* Chart results */}
          {!chatOpen && (
            <>
              {!result && !loading && (
                <div className="flex items-center justify-center rounded-xl"
                  style={{ height: '400px', backgroundColor: '#12122a', border: '1px dashed #2a2a5a', color: '#3a3a6a', fontSize: '2rem' }}>
                  ✦
                </div>
              )}
              {loading && (
                <div className="flex items-center justify-center rounded-xl"
                  style={{ height: '400px', backgroundColor: '#12122a', border: '1px solid #2a2a5a', color: '#8888aa', fontSize: '0.9rem' }}>
                  计算中…
                </div>
              )}
              {result && (
                <div className="space-y-6">
                  {svgContent && <ChartWheel svgContent={svgContent} language={result.input_data?.language} />}
                  <PlanetTable planets={result.planets} language={result.input_data?.language} />
                </div>
              )}
            </>
          )}

          {/* Chat panel */}
          {chatOpen && result && (
            <div className="chat-panel">
              {/* Header */}
              <div style={{
                padding: '12px 16px', borderBottom: '1px solid #2a2a5a',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <span style={{ color: '#c9a84c', fontSize: '0.75rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  ✦ 占星对话
                </span>
              </div>

              {/* Messages */}
              <div style={{
                flex: 1, padding: '16px',
                display: 'flex', flexDirection: 'column', gap: '14px',
                overflowY: 'auto',
              }}>
                {messages.length === 0 && (
                  <div style={{ color: '#3a3a6a', fontSize: '0.88rem' }}>
                    问我关于你星盘的任何问题…
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '92%',
                    backgroundColor: msg.role === 'user' ? '#1e1e50' : '#1a1a35',
                    border: `1px solid ${msg.role === 'user' ? '#3a3a8a' : '#2a2a5a'}`,
                    borderRadius: '10px',
                    padding: '12px 16px',
                    fontSize: '0.95rem',
                    color: '#e8e8ff',
                    lineHeight: 1.75,
                  }}>
                    {msg.role === 'user' ? msg.text : (<>
                      <ReactMarkdown components={{
                        h1: ({children}) => <div style={{fontSize:'1.05rem', fontWeight:700, color:'#c9a84c', marginBottom:'6px'}}>{children}</div>,
                        h2: ({children}) => <div style={{fontSize:'1rem', fontWeight:700, color:'#c9a84c', marginBottom:'5px'}}>{children}</div>,
                        h3: ({children}) => <div style={{fontSize:'0.95rem', fontWeight:700, color:'#c9a84c', marginBottom:'4px', marginTop:'12px'}}>{children}</div>,
                        p: ({children}) => <p style={{margin:'5px 0'}}>{children}</p>,
                        strong: ({children}) => <strong style={{color:'#e8c96c'}}>{children}</strong>,
                        ul: ({children}) => <ul style={{paddingLeft:'20px', margin:'5px 0'}}>{children}</ul>,
                        ol: ({children}) => <ol style={{paddingLeft:'20px', margin:'5px 0'}}>{children}</ol>,
                        li: ({children}) => <li style={{marginBottom:'4px'}}>{children}</li>,
                        hr: () => <hr style={{border:'none', borderTop:'1px solid #2a2a5a', margin:'10px 0'}} />,
                      }}>
                        {msg.text}
                      </ReactMarkdown>
                      {msg.sources?.length > 0 && (
                        <div style={{ marginTop: '12px', borderTop: '1px solid #2a2a5a', paddingTop: '10px' }}>
                          <div style={{ color: '#555577', fontSize: '0.72rem', marginBottom: '6px', letterSpacing: '0.05em' }}>
                            RAG 检索来源
                            <span style={{ marginLeft: '8px', color: '#3a3a6a' }}>
                              ✓ 已引用 · ○ 未引用
                            </span>
                          </div>
                          {msg.sources.map((s, si) => {
                            const name = s.source.replace('[EN]', '').split('(')[0].trim()
                            const cited = s.cited
                            return (
                              <div key={si} style={{ fontSize: '0.75rem', marginBottom: '4px', display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center' }}>
                                <span style={{ color: cited ? '#8888cc' : '#444466' }}>
                                  <span style={{ marginRight: '5px', color: cited ? '#66cc88' : '#333355' }}>
                                    {cited ? '✓' : '○'}
                                  </span>
                                  {name}
                                </span>
                                <span style={{ color: s.score >= 0.5 ? '#c9a84c' : '#444466', flexShrink: 0 }}>
                                  {s.score.toFixed(3)}
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </>)}
                  </div>
                ))}
                {chatLoading && (
                  <div style={{ color: '#6666aa', fontSize: '0.88rem' }}>思考中…</div>
                )}
              </div>

              {/* Input */}
              <form onSubmit={handleChat} style={{
                display: 'flex', gap: '8px', padding: '12px 16px',
                borderTop: '1px solid #2a2a5a',
              }}>
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  placeholder="问关于星盘的问题…"
                  disabled={chatLoading}
                  autoFocus
                  style={{
                    flex: 1,
                    backgroundColor: '#0d0d22',
                    border: '1px solid #2a2a5a',
                    color: '#e8e8ff',
                    borderRadius: '6px',
                    padding: '10px 14px',
                    fontSize: '0.95rem',
                    outline: 'none',
                  }}
                />
                <button type="submit" disabled={chatLoading || !chatInput.trim()}
                  style={{
                    backgroundColor: '#c9a84c', color: '#0a0a1a',
                    border: 'none', borderRadius: '6px',
                    padding: '10px 18px', fontWeight: 600,
                    fontSize: '0.95rem',
                    cursor: chatLoading ? 'not-allowed' : 'pointer',
                    opacity: chatLoading || !chatInput.trim() ? 0.5 : 1,
                  }}>
                  发送
                </button>
              </form>
            </div>
          )}
          {/* Rectification panel */}
          {rectifyOpen && result && (
            <div style={{ backgroundColor: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '24px' }}>
              <div style={{ color: '#9a8acc', fontSize: '0.75rem', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '20px' }}>
                ◈ 出生时间校对
              </div>

              {/* 大致时间（可选） */}
              <div style={{ marginBottom: '16px' }}>
                <div style={labelStyle}>大致出生时间（可选）</div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <input type="number" min="0" max="23" placeholder="小时 0-23"
                    value={approxHour} onChange={e => setApproxHour(e.target.value)}
                    style={{ ...inputSm, width: '110px' }} />
                  <input type="number" min="0.5" max="12" step="0.5" placeholder="范围 ± 小时"
                    value={timeRangeHours} onChange={e => setTimeRangeHours(e.target.value)}
                    style={{ ...inputSm, width: '110px' }} />
                  <span style={{ color: '#555577', fontSize: '0.75rem' }}>不填 = 全天扫描</span>
                </div>
              </div>

              {/* 事件列表 */}
              <div style={{ marginBottom: '12px' }}>
                <div style={{ ...labelStyle, marginBottom: '10px' }}>重大人生事件（最多 5 条）</div>
                {rectifyEvents.map((ev, i) => (
                  <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input type="number" placeholder="年" value={ev.year} onChange={e => updateEvent(i, 'year', e.target.value)}
                      style={{ ...inputSm, width: '62px' }} />
                    <input type="number" placeholder="月" min="1" max="12" value={ev.month} onChange={e => updateEvent(i, 'month', e.target.value)}
                      style={{ ...inputSm, width: '46px' }} />
                    <input type="number" placeholder="日" min="1" max="31" value={ev.day} onChange={e => updateEvent(i, 'day', e.target.value)}
                      style={{ ...inputSm, width: '46px' }} />
                    <select value={ev.event_type} onChange={e => updateEvent(i, 'event_type', e.target.value)}
                      style={{ ...inputSm, flex: 1, minWidth: '100px' }}>
                      <option value="marriage">结婚</option>
                      <option value="divorce">离婚</option>
                      <option value="career_up">升职/突破</option>
                      <option value="career_down">失业/受挫</option>
                      <option value="bereavement">亲人离世</option>
                      <option value="illness">重大疾病</option>
                      <option value="relocation">搬迁</option>
                      <option value="accident">意外事故</option>
                      <option value="other">其他</option>
                    </select>
                    <select value={ev.weight} onChange={e => updateEvent(i, 'weight', e.target.value)}
                      style={{ ...inputSm, width: '78px' }}>
                      <option value={1}>一般</option>
                      <option value={2}>重要</option>
                      <option value={3}>非常重要</option>
                    </select>
                    {rectifyEvents.length > 1 && (
                      <button onClick={() => removeEvent(i)}
                        style={{ background: 'none', border: 'none', color: '#4a3a5a', cursor: 'pointer', fontSize: '0.85rem', padding: '0 4px' }}
                        onMouseEnter={e => e.currentTarget.style.color = '#cc6666'}
                        onMouseLeave={e => e.currentTarget.style.color = '#4a3a5a'}>✕</button>
                    )}
                  </div>
                ))}
                {rectifyEvents.length < 5 && (
                  <button onClick={addEvent}
                    style={{ color: '#7a6aaa', background: 'none', border: '1px dashed #4a4a7a', borderRadius: '6px', padding: '4px 12px', cursor: 'pointer', fontSize: '0.8rem', marginTop: '4px' }}>
                    + 添加事件
                  </button>
                )}
              </div>

              <button onClick={handleRectify} disabled={rectifyLoading}
                style={{ width: '100%', padding: '10px', marginTop: '8px', background: rectifyLoading ? '#1e1e3a' : '#7a6aaa', color: rectifyLoading ? '#3a3a5a' : '#ffffff', border: 'none', borderRadius: '8px', fontWeight: 700, cursor: rectifyLoading ? 'not-allowed' : 'pointer', fontSize: '0.9rem' }}>
                {rectifyLoading ? '扫描中… 约 25-40 秒' : '开始校对'}
              </button>

              {rectifyError && <p style={{ color: '#ff7070', fontSize: '0.88rem', marginTop: '10px' }}>{rectifyError}</p>}

              {rectifyResult && !rectifyLoading && (
                <div style={{ marginTop: '20px', borderTop: '1px solid #2a2a4a', paddingTop: '20px' }}>
                  <div style={{ color: '#9a8acc', fontSize: '0.75rem', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '14px' }}>
                    Top 3 候选时间
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
                    {rectifyResult.top3.map((t, i) => (
                      <div key={i} style={{ background: i === 0 ? '#1e1a38' : '#14142a', border: `1px solid ${i === 0 ? '#7a6aaa' : '#2a2a5a'}`, borderRadius: '10px', padding: '16px 18px' }}>
                        {/* 头部：时间 + 标签 */}
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: t.reason ? '12px' : '0' }}>
                          <span style={{ color: '#e0e0f0', fontSize: '1.4rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                            {String(t.hour).padStart(2, '0')}:{String(t.minute).padStart(2, '0')}
                          </span>
                          {t.asc_sign && (
                            <span style={{ color: '#8888aa', fontSize: '0.82rem' }}>上升 {t.asc_sign}</span>
                          )}
                          <span style={{ marginLeft: 'auto', color: i === 0 ? '#c9a84c' : '#7a6aaa', fontSize: '0.72rem', fontWeight: 600 }}>
                            {i === 0 ? '★ 推荐' : `候选 ${i + 1}`}
                          </span>
                          <span style={{ color: '#555577', fontSize: '0.72rem' }}>评分 {t.score}</span>
                        </div>
                        {/* 分析理由（Markdown） */}
                        {t.reason && (
                          <div style={{ borderTop: '1px solid #2a2a4a', paddingTop: '10px' }}
                            className="rectify-reason">
                            <ReactMarkdown>{t.reason}</ReactMarkdown>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  {/* 综合分析（Markdown） */}
                  {rectifyResult.overall && (
                    <div style={{ background: '#0f0f28', border: '1px solid #3a3a6a', borderRadius: '10px', padding: '16px 18px' }}>
                      <div style={{ color: '#9a8acc', fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '10px' }}>综合推荐与验证建议</div>
                      <div className="rectify-overall">
                        <ReactMarkdown>{rectifyResult.overall}</ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
