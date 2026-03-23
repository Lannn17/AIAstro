import { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const VALID_LANGS = ['pt', 'en', 'es', 'zh', 'ja']

const ASPECT_COLOR = {
  Conjunction: '#ffffff',
  Opposition:  '#ff6666',
  Square:      '#ff9944',
  Trine:       '#66cc88',
  Sextile:     '#44aaff',
  Quincunx:    '#bb88ff',
  Semisquare:  '#ffaa44',
  Sesquiquadrate: '#ff8844',
}

const inputStyle = {
  width: '100%',
  background: '#0e0e24',
  border: '1px solid #2a2a5a',
  color: '#d0d0e0',
  borderRadius: '6px',
  padding: '8px 10px',
  fontSize: '0.85rem',
  boxSizing: 'border-box',
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function Transits() {
  const [savedCharts, setSavedCharts]     = useState([])
  const [selectedId, setSelectedId]       = useState('')
  const [selectedChart, setSelectedChart] = useState(null)
  const [transitDate, setTransitDate]     = useState(todayStr)
  const [transitTime, setTransitTime]     = useState('12:00')
  const [result, setResult]               = useState(null)
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState(null)
  const [interpretation, setInterpretation] = useState(null)
  const [interpretLoading, setInterpretLoading] = useState(false)
  const [interpretError, setInterpretError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/charts`)
      .then(r => r.ok ? r.json() : [])
      .then(setSavedCharts)
      .catch(() => {})
  }, [])

  async function handleSelectChart(id) {
    setSelectedId(id)
    setResult(null)
    setError(null)
    setInterpretation(null)
    setInterpretError(null)
    if (!id) { setSelectedChart(null); return }
    try {
      const r = await fetch(`${API_BASE}/api/charts/${id}`)
      if (r.ok) setSelectedChart(await r.json())
    } catch { setError('加载星盘失败') }
  }

  async function calculate() {
    if (!selectedChart) return
    setLoading(true)
    setError(null)
    setResult(null)

    const [year, month, day] = transitDate.split('-').map(Number)
    const [hour, minute]     = transitTime.split(':').map(Number)
    const lang = VALID_LANGS.includes(selectedChart.language) ? selectedChart.language : 'zh'

    try {
      const r = await fetch(`${API_BASE}/api/transits_to_natal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal: {
            name:         selectedChart.name || '',
            year:         selectedChart.birth_year,
            month:        selectedChart.birth_month,
            day:          selectedChart.birth_day,
            hour:         selectedChart.birth_hour,
            minute:       selectedChart.birth_minute,
            latitude:     selectedChart.latitude,
            longitude:    selectedChart.longitude,
            tz_str:       selectedChart.tz_str,
            house_system: selectedChart.house_system,
            language:     lang,
          },
          transit: {
            year, month, day, hour, minute,
            latitude:     selectedChart.latitude,
            longitude:    selectedChart.longitude,
            tz_str:       selectedChart.tz_str,
            house_system: selectedChart.house_system,
            language:     lang,
          },
        }),
      })
      if (!r.ok) throw new Error(`错误 ${r.status}`)
      setResult(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function interpretTransits() {
    if (!result || !selectedChart) return
    setInterpretLoading(true)
    setInterpretError(null)
    setInterpretation(null)

    // 使用保存的本命盘 chart_data 或从 result 中重建
    const natalChartData = selectedChart.chart_data
      ? (typeof selectedChart.chart_data === 'string'
          ? JSON.parse(selectedChart.chart_data)
          : selectedChart.chart_data)
      : {}

    const transitOnlyAspects = result.aspects.filter(a =>
      (a.p1_owner === 'transit' && a.p2_owner === 'natal') ||
      (a.p1_owner === 'natal'   && a.p2_owner === 'transit')
    ).sort((a, b) => a.orbit - b.orbit)

    try {
      const r = await fetch(`${API_BASE}/api/interpret/transit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal_chart:      natalChartData,
          transit_aspects:  transitOnlyAspects,
          transit_planets:  result.transit_planets,
          transit_date:     `${transitDate} ${transitTime}`,
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        throw new Error(err.detail || `错误 ${r.status}`)
      }
      setInterpretation(await r.json())
    } catch (e) {
      setInterpretError(e.message)
    } finally {
      setInterpretLoading(false)
    }
  }

  // 过滤行运-本命相位，按容许度排序
  const aspects = result
    ? result.aspects
        .filter(a =>
          (a.p1_owner === 'transit' && a.p2_owner === 'natal') ||
          (a.p1_owner === 'natal'   && a.p2_owner === 'transit')
        )
        .sort((a, b) => a.orbit - b.orbit)
    : []

  return (
    <div>
      {/* 页眉 */}
      <div className="mb-6">
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ♂ 行运
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          计算指定日期的行星对本命盘的影响
        </p>
      </div>

      <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
        {/* ── 左栏：控制面板 ── */}
        <div style={{ width: '260px', flexShrink: 0 }}>
          <div style={{ background: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '20px' }}>

            <Label>选择本命盘</Label>
            <select
              value={selectedId}
              onChange={e => handleSelectChart(e.target.value)}
              style={{ ...inputStyle, marginBottom: '4px' }}
            >
              <option value="">-- 请选择 --</option>
              {savedCharts.map(c => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
            {savedCharts.length === 0 && (
              <p style={{ color: '#555577', fontSize: '0.78rem', marginTop: '6px' }}>
                请先在「星盘」页面保存本命盘
              </p>
            )}

            <Label style={{ marginTop: '18px' }}>行运日期</Label>
            <input
              type="date"
              value={transitDate}
              onChange={e => setTransitDate(e.target.value)}
              style={inputStyle}
            />

            <Label style={{ marginTop: '12px' }}>行运时间</Label>
            <input
              type="time"
              value={transitTime}
              onChange={e => setTransitTime(e.target.value)}
              style={inputStyle}
            />

            <p style={{ color: '#555577', fontSize: '0.75rem', marginTop: '8px' }}>
              使用出生地点与时区
            </p>

            <button
              onClick={calculate}
              disabled={!selectedChart || loading}
              style={{
                width: '100%',
                marginTop: '18px',
                padding: '10px',
                background: selectedChart && !loading ? '#c9a84c' : '#1e1e3a',
                color:  selectedChart && !loading ? '#0a0a18' : '#3a3a5a',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 700,
                cursor: selectedChart && !loading ? 'pointer' : 'not-allowed',
                fontSize: '0.9rem',
                transition: 'background 0.2s',
              }}
            >
              {loading ? '计算中…' : '计算行运'}
            </button>

            {error && (
              <p style={{ color: '#ff6666', fontSize: '0.8rem', marginTop: '10px' }}>{error}</p>
            )}
          </div>
        </div>

        {/* ── 右栏：结果 ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!result && !loading && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '320px', background: '#12122a',
              border: '1px dashed #2a2a5a', borderRadius: '12px', color: '#3a3a6a',
            }}>
              选择本命盘并设定日期后点击「计算行运」
            </div>
          )}

          {loading && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '320px', color: '#8888aa',
            }}>
              计算中…
            </div>
          )}

          {result && (
            <>
              {/* 行运行星位置 */}
              <div style={{ background: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '20px', marginBottom: '20px' }}>
                <div style={{ color: '#c9a84c', fontSize: '0.9rem', fontWeight: 600, marginBottom: '14px' }}>
                  行运行星位置
                  <span style={{ color: '#555577', fontSize: '0.75rem', fontWeight: 400, marginLeft: '10px' }}>
                    {transitDate} {transitTime}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '8px' }}>
                  {Object.values(result.transit_planets).map(p => {
                    const name = p.name_original || p.name
                    const sign = p.sign_original || p.sign
                    return (
                      <div key={name} style={{ background: '#0e0e24', borderRadius: '8px', padding: '8px 12px' }}>
                        <span style={{ color: '#c9a84c', fontWeight: 600, fontSize: '0.85rem' }}>{name}</span>
                        <span style={{ color: '#d0d0e0', fontSize: '0.85rem', marginLeft: '8px' }}>{sign}</span>
                        {p.retrograde && (
                          <span style={{ color: '#ff8888', fontSize: '0.75rem', marginLeft: '6px' }}>℞</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* 行运-本命相位 */}
              <div style={{ background: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '20px' }}>
                <div style={{ color: '#c9a84c', fontSize: '0.9rem', fontWeight: 600, marginBottom: '14px' }}>
                  行运-本命相位
                  <span style={{ color: '#555577', fontSize: '0.75rem', fontWeight: 400, marginLeft: '10px' }}>
                    共 {aspects.length} 个
                  </span>
                </div>

                {aspects.length === 0 ? (
                  <p style={{ color: '#555577', fontSize: '0.85rem' }}>无相位数据</p>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ color: '#555577', borderBottom: '1px solid #2a2a5a' }}>
                        <th style={th}>行运行星</th>
                        <th style={{ ...th, textAlign: 'center' }}>相位</th>
                        <th style={th}>本命行星</th>
                        <th style={{ ...th, textAlign: 'right' }}>容许度</th>
                        <th style={{ ...th, textAlign: 'right' }}>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {aspects.map((a, i) => {
                        const isTP1 = a.p1_owner === 'transit'
                        const tPlanet = isTP1
                          ? (a.p1_name_original || a.p1_name)
                          : (a.p2_name_original || a.p2_name)
                        const nPlanet = isTP1
                          ? (a.p2_name_original || a.p2_name)
                          : (a.p1_name_original || a.p1_name)
                        const aspect  = a.aspect_original || a.aspect
                        const color   = ASPECT_COLOR[aspect] || '#d0d0e0'
                        const tight   = a.orbit <= 2

                        return (
                          <tr
                            key={i}
                            style={{
                              borderBottom: '1px solid #1a1a3a',
                              background: tight ? 'rgba(201,168,76,0.06)' : 'transparent',
                            }}
                          >
                            <td style={td}>{tPlanet}</td>
                            <td style={{ ...td, textAlign: 'center', color, fontWeight: 600 }}>{aspect}</td>
                            <td style={{ ...td, color: '#8888aa' }}>{nPlanet}</td>
                            <td style={{ ...td, textAlign: 'right', color: tight ? '#c9a84c' : '#555577' }}>
                              {a.orbit.toFixed(1)}°
                            </td>
                            <td style={{ ...td, textAlign: 'right', color: '#555577', fontSize: '0.78rem' }}>
                              {a.applying ? '入相' : '出相'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              {/* AI 解读区块 */}
              <div style={{ background: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <div style={{ color: '#c9a84c', fontSize: '0.9rem', fontWeight: 600 }}>
                    ✦ AI 行运解读
                  </div>
                  <button
                    onClick={interpretTransits}
                    disabled={interpretLoading}
                    style={{
                      padding: '6px 16px',
                      background: interpretLoading ? '#1e1e3a' : '#1a1a40',
                      color: interpretLoading ? '#3a3a5a' : '#c9a84c',
                      border: '1px solid #c9a84c44',
                      borderRadius: '6px',
                      cursor: interpretLoading ? 'not-allowed' : 'pointer',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      transition: 'background 0.2s',
                    }}
                  >
                    {interpretLoading ? '解读中…' : (interpretation ? '重新解读' : '生成解读')}
                  </button>
                </div>

                {interpretError && (
                  <p style={{ color: '#ff6666', fontSize: '0.82rem' }}>{interpretError}</p>
                )}

                {interpretLoading && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#8888aa', fontSize: '0.85rem', padding: '20px 0' }}>
                    <span style={{ animation: 'spin 1.2s linear infinite', display: 'inline-block' }}>◌</span>
                    正在分析行运相位，AI 解读通常需要 10-20 秒，请稍候…
                  </div>
                )}

                {interpretation && !interpretLoading && (
                  <div>
                    <div style={{
                      color: '#d0d0e0',
                      fontSize: '0.88rem',
                      lineHeight: '1.9',
                      whiteSpace: 'pre-wrap',
                      borderTop: '1px solid #1a1a3a',
                      paddingTop: '14px',
                    }}>
                      {interpretation.answer}
                    </div>
                    {interpretation.sources && interpretation.sources.some(s => s.cited) && (
                      <div style={{ marginTop: '16px', borderTop: '1px solid #1a1a3a', paddingTop: '12px' }}>
                        <div style={{ color: '#555577', fontSize: '0.75rem', marginBottom: '6px' }}>参考来源</div>
                        {interpretation.sources.filter(s => s.cited).map((s, i) => (
                          <div key={i} style={{ color: '#4a4a7a', fontSize: '0.75rem', marginBottom: '2px' }}>
                            · {s.source.replace('[EN]', '').split('(')[0].trim()}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {!interpretation && !interpretLoading && !interpretError && (
                  <p style={{ color: '#3a3a6a', fontSize: '0.83rem' }}>
                    点击「生成解读」，AI 将根据行运相位给出综合解析
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Label({ children, style }) {
  return (
    <div style={{ color: '#c9a84c', fontSize: '0.82rem', fontWeight: 600, marginBottom: '8px', ...style }}>
      {children}
    </div>
  )
}

const th = { textAlign: 'left', padding: '6px 10px', fontWeight: 400 }
const td = { padding: '8px 10px', color: '#d0d0e0' }
