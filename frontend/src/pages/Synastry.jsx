import { useState, useEffect } from 'react'
import LocationSearch from '../components/LocationSearch'
import { useInterpret } from '../hooks/useInterpret'
import { useAuth } from '../contexts/AuthContext'
import { useChartSession } from '../contexts/ChartSessionContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const TIMEZONES = [
  'Asia/Shanghai', 'Asia/Tokyo', 'Asia/Seoul', 'Asia/Hong_Kong',
  'Asia/Singapore', 'Asia/Kolkata', 'Asia/Dubai',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'America/New_York', 'America/Chicago', 'America/Los_Angeles',
  'America/Sao_Paulo', 'Australia/Sydney', 'Pacific/Auckland',
]

const EMPTY_FORM = {
  name: '', year: '', month: '', day: '',
  hour: '', minute: '',
  latitude: '', longitude: '',
  tz_str: 'Asia/Shanghai',
  house_system: 'Placidus',
  locationName: '',
}

const inputStyle = {
  backgroundColor: '#0d0d22',
  border: '1px solid #2a2a5a',
  color: '#e8e8ff',
  borderRadius: '6px',
  padding: '7px 10px',
  width: '100%',
  outline: 'none',
  fontSize: '0.875rem',
  boxSizing: 'border-box',
}

const labelStyle = {
  color: '#8888aa',
  fontSize: '0.7rem',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  display: 'block',
  marginBottom: '4px',
}

function SynastryManualForm({ formData, onChange }) {
  const field = (name, value) => onChange({ ...formData, [name]: value })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div>
        <label style={labelStyle}>姓名</label>
        <input
          style={inputStyle}
          value={formData.name}
          onChange={e => field('name', e.target.value)}
          placeholder="姓名"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
        <div>
          <label style={labelStyle}>年</label>
          <input style={inputStyle} type="number" value={formData.year}
            onChange={e => field('year', e.target.value)} placeholder="1990" />
        </div>
        <div>
          <label style={labelStyle}>月</label>
          <input style={inputStyle} type="number" min="1" max="12" value={formData.month}
            onChange={e => field('month', e.target.value)} placeholder="1" />
        </div>
        <div>
          <label style={labelStyle}>日</label>
          <input style={inputStyle} type="number" min="1" max="31" value={formData.day}
            onChange={e => field('day', e.target.value)} placeholder="1" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        <div>
          <label style={labelStyle}>时</label>
          <input style={inputStyle} type="number" min="0" max="23" value={formData.hour}
            onChange={e => field('hour', e.target.value)} placeholder="0" />
        </div>
        <div>
          <label style={labelStyle}>分</label>
          <input style={inputStyle} type="number" min="0" max="59" value={formData.minute}
            onChange={e => field('minute', e.target.value)} placeholder="0" />
        </div>
      </div>

      <LocationSearch
        initialValue={formData.locationName}
        latitude={formData.latitude}
        longitude={formData.longitude}
        onSelect={({ latitude, longitude, locationName }) =>
          onChange({ ...formData, latitude, longitude, locationName })
        }
      />

      <div>
        <label style={labelStyle}>时区</label>
        <select style={inputStyle} value={formData.tz_str} onChange={e => field('tz_str', e.target.value)}>
          {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
        </select>
      </div>

      <div>
        <label style={labelStyle}>宫位系统</label>
        <select style={inputStyle} value={formData.house_system} onChange={e => field('house_system', e.target.value)}>
          {['Placidus', 'Koch', 'Whole Sign', 'Equal', 'Regiomontanus', 'Campanus'].map(hs =>
            <option key={hs} value={hs}>{hs}</option>
          )}
        </select>
      </div>
    </div>
  )
}

function ChartInputCol({ label, col, setCol, isAuthenticated, authHeaders, sessionCharts }) {
  const [savedCharts, setSavedCharts] = useState([])

  useEffect(() => {
    if (!isAuthenticated) return
    fetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      .then(r => r.json())
      .then(data => setSavedCharts(Array.isArray(data) ? data : []))
      .catch(() => setSavedCharts([]))
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  const chartList = isAuthenticated ? savedCharts : sessionCharts

  async function handleSelectChange(e) {
    const id = e.target.value
    if (!id) {
      setCol(prev => ({ ...prev, selectedId: null, formData: EMPTY_FORM }))
      return
    }
    let fd = { ...EMPTY_FORM }
    if (isAuthenticated) {
      try {
        const res = await fetch(`${API_BASE}/api/charts/${id}`, { headers: authHeaders() })
        if (res.ok) {
          const chart = await res.json()
          fd = {
            name: chart.name || '',
            year: chart.birth_year || '',
            month: chart.birth_month || '',
            day: chart.birth_day || '',
            hour: chart.birth_hour !== undefined ? chart.birth_hour : '',
            minute: chart.birth_minute !== undefined ? chart.birth_minute : '',
            latitude: chart.latitude || '',
            longitude: chart.longitude || '',
            tz_str: chart.tz_str || 'Asia/Shanghai',
            house_system: chart.house_system || 'Placidus',
            locationName: chart.location_name || '',
          }
        }
      } catch { /* keep EMPTY_FORM */ }
    } else {
      const chart = sessionCharts.find(c => String(c.id) === id)
      if (chart && chart.formData) {
        fd = { ...EMPTY_FORM, ...chart.formData }
      }
    }
    setCol(prev => ({ ...prev, selectedId: id, formData: fd }))
  }

  const tabBtnStyle = (active) => ({
    padding: '5px 12px',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '0.78rem',
    backgroundColor: active ? '#2a2a5a' : 'transparent',
    color: active ? '#c9a84c' : '#6666aa',
    transition: 'all 0.15s',
  })

  const previewStr = (() => {
    const f = col.formData
    if (!f.name) return null
    const hh = String(f.hour !== '' ? f.hour : 0).padStart(2, '0')
    const mm = String(f.minute !== '' ? f.minute : 0).padStart(2, '0')
    return `${f.name} · ${f.year}/${f.month}/${f.day} ${hh}:${mm}`
  })()

  return (
    <div style={{
      backgroundColor: '#12122a',
      border: '1px solid #2a2a5a',
      borderRadius: '10px',
      padding: '16px',
    }}>
      <div style={{ color: '#c9a84c', fontWeight: 600, fontSize: '0.95rem', marginBottom: '12px' }}>
        {label}
      </div>

      {/* Mode tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '12px' }}>
        <button
          style={tabBtnStyle(col.mode === 'select')}
          onClick={() => setCol(prev => ({ ...prev, mode: 'select' }))}
        >
          {isAuthenticated ? '从已保存选择' : '从会话选择'}
        </button>
        <button
          style={tabBtnStyle(col.mode === 'manual')}
          onClick={() => setCol(prev => ({ ...prev, mode: 'manual' }))}
        >
          手动填写
        </button>
      </div>

      {col.mode === 'select' && (
        <div>
          <label style={labelStyle}>选择星盘</label>
          <select
            style={inputStyle}
            value={col.selectedId || ''}
            onChange={handleSelectChange}
          >
            <option value="">— 请选择 —</option>
            {chartList.map(c => (
              <option key={c.id} value={String(c.id)}>
                {isAuthenticated
                  ? (c.birth_year ? `${c.name || ''} · ${c.birth_year}/${c.birth_month}/${c.birth_day}` : (c.label || c.name))
                  : (c.name || c.id)}
              </option>
            ))}
          </select>
          {chartList.length === 0 && (
            <div style={{ color: '#4a4a6a', fontSize: '0.78rem', marginTop: '8px' }}>
              {isAuthenticated ? '暂无已保存的星盘' : '本次会话暂无星盘，请先在星盘页生成'}
            </div>
          )}
        </div>
      )}

      {col.mode === 'manual' && (
        <SynastryManualForm
          formData={col.formData}
          onChange={(fd) => setCol(prev => ({ ...prev, formData: fd }))}
        />
      )}

      {previewStr && (
        <div style={{
          marginTop: '12px',
          padding: '8px 10px',
          backgroundColor: '#0d0d22',
          borderRadius: '6px',
          border: '1px solid #2a2a5a',
          color: '#a0a0cc',
          fontSize: '0.8rem',
        }}>
          {previewStr}
        </div>
      )}
    </div>
  )
}

function colReady(col) {
  const f = col.formData
  return !!(f.name && f.year && f.month && f.day &&
    f.hour !== '' && f.minute !== '' &&
    f.latitude && f.longitude && f.tz_str)
}

export default function Synastry() {
  const { isAuthenticated, authHeaders } = useAuth()
  const { sessionCharts } = useChartSession()

  const [col1, setCol1] = useState({ mode: 'select', selectedId: null, formData: { ...EMPTY_FORM } })
  const [col2, setCol2] = useState({ mode: 'select', selectedId: null, formData: { ...EMPTY_FORM } })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [svgContent, setSvgContent] = useState(null)
  const interp = useInterpret('/api/interpret/synastry')

  const canCalculate = colReady(col1) && colReady(col2)

  function makeChart(col) {
    return {
      name: col.formData.name,
      year: Number(col.formData.year),
      month: Number(col.formData.month),
      day: Number(col.formData.day),
      hour: Number(col.formData.hour),
      minute: Number(col.formData.minute),
      latitude: Number(col.formData.latitude),
      longitude: Number(col.formData.longitude),
      tz_str: col.formData.tz_str,
      house_system: col.formData.house_system || 'Placidus',
      language: 'zh',
    }
  }

  async function handleCalculate() {
    setLoading(true)
    setResult(null)
    setSvgContent(null)
    interp.reset()
    try {
      const syRes = await fetch(`${API_BASE}/api/synastry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chart1: makeChart(col1), chart2: makeChart(col2), language: 'zh' }),
      })
      if (!syRes.ok) throw new Error(await syRes.text())
      const syData = await syRes.json()
      setResult(syData)

      const svgRes = await fetch(`${API_BASE}/api/svg_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal_chart: makeChart(col1),
          transit_chart: makeChart(col2),
          chart_type: 'transit',
          theme: 'dark',
          language: 'zh',
        }),
      })
      if (svgRes.ok) setSvgContent(await svgRes.text())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  function handleInterpret() {
    if (!result?.aspects) return
    interp.run({
      chart1_summary: { name: col1.formData.name },
      chart2_summary: { name: col2.formData.name },
      aspects: result.aspects,
      chart1_planets: result.chart1_planets || {},
      chart2_planets: result.chart2_planets || {},
    })
  }

  return (
    <div>
      <div className="mb-6">
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ♀♂ 合盘
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          比较两张星盘的相位关系与缘分分析
        </p>
      </div>

      {/* Dual chart input columns */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        <ChartInputCol
          label="甲方星盘"
          col={col1}
          setCol={setCol1}
          isAuthenticated={isAuthenticated}
          authHeaders={authHeaders}
          sessionCharts={sessionCharts}
        />
        <ChartInputCol
          label="乙方星盘"
          col={col2}
          setCol={setCol2}
          isAuthenticated={isAuthenticated}
          authHeaders={authHeaders}
          sessionCharts={sessionCharts}
        />
      </div>

      {/* Calculate button */}
      <div style={{ marginTop: '16px' }}>
        <button
          onClick={handleCalculate}
          disabled={!canCalculate || loading}
          style={{
            padding: '10px 28px',
            borderRadius: '8px',
            cursor: canCalculate && !loading ? 'pointer' : 'not-allowed',
            backgroundColor: canCalculate ? '#2a2a5a' : '#1a1a3a',
            border: '1px solid #4a4a8a',
            color: canCalculate ? '#c9a84c' : '#4a4a6a',
            fontSize: '0.9rem',
          }}
        >
          {loading ? '计算中…' : '计算合盘'}
        </button>
      </div>

      {/* Double-wheel SVG */}
      {svgContent && (
        <div
          style={{ marginTop: '24px' }}
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
      )}

      {/* Aspect table */}
      {result?.aspects?.length > 0 && (
        <div style={{ marginTop: '24px', overflowX: 'auto' }}>
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.82rem',
            backgroundColor: 'transparent',
          }}>
            <thead>
              <tr style={{ color: '#8888aa', borderBottom: '1px solid #2a2a5a' }}>
                <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>方向</th>
                <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>甲行星</th>
                <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>相位</th>
                <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>乙行星</th>
                <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>容许度</th>
              </tr>
            </thead>
            <tbody>
              {result.aspects.map((a, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: '1px solid #1a1a3a',
                    color: a.double_whammy ? '#c9a84c' : '#ccc',
                  }}
                >
                  <td style={{ padding: '5px 8px' }}>
                    {a.direction === 'p1_to_p2' ? '甲→乙' : '乙→甲'}
                  </td>
                  <td style={{ padding: '5px 8px' }}>
                    {a.p1_name}
                  </td>
                  <td style={{ padding: '5px 8px' }}>
                    {a.aspect}
                  </td>
                  <td style={{ padding: '5px 8px' }}>
                    {a.p2_name}
                  </td>
                  <td style={{ padding: '5px 8px' }}>
                    {typeof a.orbit === 'number' ? a.orbit.toFixed(1) : a.orbit}°{a.double_whammy ? ' ★' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* AI interpretation */}
      {result && (
        <div style={{ marginTop: '24px' }}>
          <button
            onClick={handleInterpret}
            disabled={interp.loading}
            style={{
              padding: '8px 20px', borderRadius: '8px',
              cursor: interp.loading ? 'not-allowed' : 'pointer',
              backgroundColor: '#2a2a5a', border: '1px solid #4a4a8a',
              color: interp.loading ? '#5a5a8a' : '#c9a84c', fontSize: '0.85rem',
            }}
          >
            {interp.loading ? '生成中…' : '生成 AI 解读'}
          </button>

          {interp.error && (
            <div style={{ color: '#cc4444', fontSize: '0.82rem', marginTop: '8px' }}>
              {interp.error}
            </div>
          )}

          {interp.result && !interp.result.texture_labels && (
            <pre style={{ marginTop: '16px', color: '#ccc', whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
              {interp.result.answer}
            </pre>
          )}

          {interp.result?.texture_labels && (
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Texture */}
              <div style={{ padding: '12px 14px', backgroundColor: '#12122a', borderRadius: '8px', border: '1px solid #2a2a5a' }}>
                <div style={{ color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '6px' }}>关系质感</div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  {interp.result.texture_labels.map(label => (
                    <span key={label} style={{ padding: '3px 10px', backgroundColor: '#2a2a5a', borderRadius: '12px', color: '#c9a84c', fontSize: '0.82rem' }}>
                      {label}
                    </span>
                  ))}
                </div>
                <div style={{ color: '#a0a0cc', fontSize: '0.82rem' }}>{interp.result.texture_reasoning}</div>
              </div>

              {/* Relationship rankings */}
              <div style={{ padding: '12px 14px', backgroundColor: '#12122a', borderRadius: '8px', border: '1px solid #2a2a5a' }}>
                <div style={{ color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px' }}>最可能形成的关系</div>
                {interp.result.relationship_rankings.map((r, i) => (
                  <div key={i} style={{ marginBottom: '12px', paddingBottom: '12px', borderBottom: i < 2 ? '1px solid #1a1a3a' : 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                      <span style={{ color: '#c9a84c', fontWeight: 600 }}>{r.type}</span>
                      <span style={{ color: '#6666aa', fontSize: '0.78rem' }}>{r.score} / 100</span>
                    </div>
                    <div style={{ color: '#6666aa', fontSize: '0.75rem', marginBottom: '4px' }}>
                      {r.key_aspects.join(' · ')}
                    </div>
                    <div style={{ color: '#a0a0cc', fontSize: '0.82rem', lineHeight: 1.6 }}>{r.summary}</div>
                  </div>
                ))}
              </div>

              {/* Dimensions */}
              <div style={{ padding: '12px 14px', backgroundColor: '#12122a', borderRadius: '8px', border: '1px solid #2a2a5a' }}>
                <div style={{ color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px' }}>各维度分析</div>
                {Object.entries({
                  attraction: '吸引力', emotional: '情感连结', communication: '沟通',
                  stability: '稳定性', growth: '成长激励', friction: '摩擦张力',
                }).map(([key, label]) => {
                  const d = interp.result.dimensions[key]
                  if (!d) return null
                  return (
                    <div key={key} style={{ marginBottom: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                        <span style={{ color: '#8888cc', fontSize: '0.8rem' }}>{label}</span>
                        <span style={{ color: '#c9a84c', fontSize: '0.8rem' }}>{d.score}</span>
                      </div>
                      <div style={{ height: '4px', backgroundColor: '#1a1a3a', borderRadius: '2px', marginBottom: '6px' }}>
                        <div style={{ width: `${d.score}%`, height: '100%', backgroundColor: '#4a4a9a', borderRadius: '2px' }} />
                      </div>
                      <div style={{ color: '#a0a0cc', fontSize: '0.8rem', lineHeight: 1.6 }}>{d.analysis}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
