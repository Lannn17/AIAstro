import { useState, useEffect } from 'react'
import LocationSearch from '../components/LocationSearch'
import { SourcesSection } from '../components/AIPanel'
import { useAuth } from '../contexts/AuthContext'
import ReactMarkdown from 'react-markdown'
import { apiFetch } from '../utils/apiFetch'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const SECTION_STYLE = {
  backgroundColor: '#0d0d22',
  border: '1px solid #1e1e4a',
  borderRadius: '12px',
  padding: '20px',
  marginBottom: '16px',
}

const LABEL = { color: '#8888aa', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: '4px' }
const INPUT = { backgroundColor: '#0d0d22', border: '1px solid #2a2a5a', color: '#e8e8ff', borderRadius: '6px', padding: '7px 10px', width: '100%', outline: 'none', fontSize: '0.875rem', boxSizing: 'border-box' }
const BTN_PRIMARY = { backgroundColor: '#c9a84c', color: '#0a0a1a', border: 'none', borderRadius: '8px', padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }
const BTN_SECONDARY = { backgroundColor: 'transparent', color: '#6666aa', border: '1px solid #2a2a5a', borderRadius: '6px', padding: '6px 14px', cursor: 'pointer', fontSize: '0.8rem' }

const THEME_NAMES = {
  home_family: '家庭居所', relationships: '人际关系',
  career_public: '事业公众', inner_healing: '内在疗愈',
  money_resources: '财务资源', health_routine: '健康日常',
  learning_expansion: '学习扩展', self_identity: '自我身份',
}

export default function SolarReturn() {
  const { isAuthenticated, authHeaders } = useAuth()
  const [savedCharts, setSavedCharts] = useState([])
  const [selectedChartId, setSelectedChartId] = useState('')
  const [selectedChart, setSelectedChart] = useState(null)
  const [location, setLocation] = useState({ latitude: '', longitude: '', locationName: '' })
  const [svgContent, setSvgContent] = useState('')
  const [srData, setSrData] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [error, setError] = useState('')
  const currentYear = new Date().getFullYear()

  useEffect(() => {
    if (!isAuthenticated) return
    apiFetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      .then(r => r.json())
      .then(data => setSavedCharts(Array.isArray(data) ? data : []))
      .catch(() => setSavedCharts([]))
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleChartSelect(e) {
    const id = e.target.value
    setSelectedChartId(id)
    setSelectedChart(null)
    setSrData(null)
    setSvgContent('')
    setReport(null)
    if (!id) return
    try {
      const res = await apiFetch(`${API_BASE}/api/charts/${id}`, { headers: authHeaders() })
      if (res.ok) setSelectedChart(await res.json())
    } catch { /* ignore */ }
  }

  const canCalculate = selectedChart && location.latitude && location.longitude

  async function handleCalculate() {
    if (!canCalculate) return
    setLoading(true)
    setError('')
    setSrData(null)
    setSvgContent('')
    setReport(null)
    try {
      const srRes = await apiFetch(`${API_BASE}/api/solar-return`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          natal_chart: {
            name: selectedChart.name,
            year: selectedChart.birth_year, month: selectedChart.birth_month,
            day: selectedChart.birth_day,   hour: selectedChart.birth_hour,
            minute: selectedChart.birth_minute,
            latitude: selectedChart.latitude, longitude: selectedChart.longitude,
            tz_str: selectedChart.tz_str,     house_system: selectedChart.house_system,
            language: 'zh',
          },
          return_year: currentYear,
          location_latitude: parseFloat(location.latitude),
          location_longitude: parseFloat(location.longitude),
          location_tz_str: selectedChart.tz_str,
          language: 'zh',
          include_natal_comparison: false,
          include_interpretations: false,
        }),
      })
      if (!srRes.ok) throw new Error(`SR calculation failed: ${srRes.status}`)
      const sr = await srRes.json()
      setSrData(sr)

      const svgRes = await apiFetch(`${API_BASE}/api/svg_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          natal_chart: {
            name: selectedChart.name,
            year: selectedChart.birth_year, month: selectedChart.birth_month,
            day: selectedChart.birth_day,   hour: selectedChart.birth_hour,
            minute: selectedChart.birth_minute,
            latitude: selectedChart.latitude, longitude: selectedChart.longitude,
            tz_str: selectedChart.tz_str,     house_system: selectedChart.house_system,
            language: 'zh',
          },
          chart_type: 'transit',
          transit_chart: {
            year: parseInt(sr.return_date?.slice(0, 4) || currentYear),
            month: parseInt(sr.return_date?.slice(5, 7) || 1),
            day: parseInt(sr.return_date?.slice(8, 10) || 1),
            hour: parseInt(sr.return_date?.slice(11, 13) || 0),
            minute: parseInt(sr.return_date?.slice(14, 16) || 0),
            latitude: parseFloat(location.latitude),
            longitude: parseFloat(location.longitude),
            tz_str: selectedChart.tz_str,
            house_system: selectedChart.house_system,
            language: 'zh',
          },
          language: 'zh',
        }),
      })
      if (svgRes.ok) setSvgContent(await svgRes.text())
    } catch (err) {
      setError(err.message || '计算失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  async function handleGenerateReport(forceRefresh = false) {
    if (!srData || !selectedChart) return
    setReportLoading(true)
    setError('')
    try {
      const srPlanets = srData.return_planets || {}
      const srHouses  = srData.return_houses  || {}
      const srAscDegree = parseFloat(srHouses['1']?.longitude || 0)

      const natalRes = await apiFetch(`${API_BASE}/api/natal_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          name: selectedChart.name,
          year: selectedChart.birth_year, month: selectedChart.birth_month,
          day: selectedChart.birth_day,   hour: selectedChart.birth_hour,
          minute: selectedChart.birth_minute,
          latitude: selectedChart.latitude, longitude: selectedChart.longitude,
          tz_str: selectedChart.tz_str,   house_system: selectedChart.house_system,
          language: 'zh',
        }),
      })
      const natalData = natalRes.ok ? await natalRes.json() : {}

      const res = await apiFetch(`${API_BASE}/api/interpret/solar-return`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          chart_id: parseInt(selectedChartId),
          natal_chart_data: natalData,
          sr_planets: srPlanets,
          sr_houses: srHouses,
          sr_asc_degree: srAscDegree,
          return_year: currentYear,
          location_lat: parseFloat(location.latitude),
          location_lon: parseFloat(location.longitude),
          language: 'zh',
          force_refresh: forceRefresh,
        }),
      })
      if (!res.ok) throw new Error(`报告生成失败: ${res.status}`)
      setReport(await res.json())
    } catch (err) {
      setError(err.message || '报告生成失败')
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    if (srData && selectedChartId && !report && !reportLoading) {
      handleGenerateReport(false)
    }
  }, [srData]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!isAuthenticated) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#8888aa' }}>
        请先登录并保存本命盘，方可使用太阳回归功能。
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', padding: '0 16px 40px' }}>
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ☀ 太阳回归 {currentYear}
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          基于当年太阳回归盘分析年度主题与人生重点
        </p>
      </div>

      {/* Input Area */}
      <div style={SECTION_STYLE}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          <div>
            <label style={LABEL}>选择本命盘</label>
            <select style={INPUT} value={selectedChartId} onChange={handleChartSelect}>
              <option value="">-- 请选择已保存的星盘 --</option>
              {savedCharts.map(c => (
                <option key={c.id} value={c.id}>{c.label || c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <LocationSearch
              label="当前所在地"
              initialValue={location.locationName}
              latitude={location.latitude}
              longitude={location.longitude}
              onSelect={({ latitude, longitude, locationName }) =>
                setLocation({ latitude, longitude, locationName })
              }
            />
          </div>
        </div>
        <button
          style={{ ...BTN_PRIMARY, opacity: canCalculate ? 1 : 0.5 }}
          disabled={!canCalculate || loading}
          onClick={handleCalculate}
        >
          {loading ? '计算中…' : `计算 ${currentYear} 年太阳回归盘`}
        </button>
        {error && <p style={{ color: '#ff6666', fontSize: '0.8rem', marginTop: '8px' }}>{error}</p>}
      </div>

      {/* SVG Bi-Wheel */}
      {svgContent && (
        <div style={SECTION_STYLE}>
          <p style={{ color: '#8888aa', fontSize: '0.75rem', marginBottom: '12px' }}>
            外圈：{currentYear} 太阳回归盘 &nbsp;|&nbsp; 内圈：本命盘
          </p>
          <div
            style={{ width: '100%', maxWidth: '700px', margin: '0 auto' }}
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </div>
      )}

      {/* AI Annual Report */}
      {(reportLoading || report) && (
        <div style={SECTION_STYLE}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ color: '#c9a84c', fontSize: '1rem', fontWeight: 600, margin: 0 }}>
              {currentYear} 年度报告
            </h2>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {report?.model_used && (
                <span style={{ color: '#6666aa', fontSize: '0.7rem', border: '1px solid #2a2a5a', borderRadius: '4px', padding: '2px 8px' }}>
                  {report.model_used === 'cached' ? '缓存' : report.model_used}
                </span>
              )}
              <button style={BTN_SECONDARY} disabled={reportLoading} onClick={() => handleGenerateReport(true)}>
                {reportLoading ? '生成中…' : '重新生成'}
              </button>
            </div>
          </div>

          {reportLoading && !report ? (
            <div style={{ color: '#6666aa', fontSize: '0.85rem' }}>AI 正在分析年度星盘…</div>
          ) : report && (
            <>
              {report.keywords?.length > 0 && (
                <div style={{ marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {report.keywords.map((kw, i) => (
                    <span key={i} style={{ backgroundColor: '#1a1a3a', color: '#c9a84c', borderRadius: '20px', padding: '4px 12px', fontSize: '0.82rem', border: '1px solid #2a2a5a' }}>
                      {kw}
                    </span>
                  ))}
                </div>
              )}

              {report.summary && (
                <div style={{ marginBottom: '16px', color: '#ccccee', fontSize: '0.88rem', lineHeight: 1.7 }}>
                  <ReactMarkdown>{report.summary}</ReactMarkdown>
                </div>
              )}

              {report.themes?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: '#8888aa', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '12px' }}>年度核心主题</h3>
                  {report.themes.map((t, i) => (
                    <div key={i} style={{ backgroundColor: '#0a0a1e', border: '1px solid #1e1e4a', borderRadius: '8px', padding: '14px', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ color: '#c9a84c', fontWeight: 600, fontSize: '0.9rem' }}>
                          {i + 1}. {t.name_zh || THEME_NAMES[t.theme] || t.theme}
                        </span>
                        <span style={{ color: '#6666aa', fontSize: '0.75rem' }}>得分 {t.score}</span>
                      </div>
                      <div style={{ height: '4px', backgroundColor: '#1e1e4a', borderRadius: '2px', marginBottom: '10px' }}>
                        <div style={{ height: '100%', width: `${Math.min(t.score * 10, 100)}%`, backgroundColor: '#c9a84c', borderRadius: '2px' }} />
                      </div>
                      {t.analysis && (
                        <p style={{ color: '#aaaacc', fontSize: '0.84rem', lineHeight: 1.6, margin: 0 }}>{t.analysis}</p>
                      )}
                      {t.evidence?.length > 0 && (
                        <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {t.evidence.map((ev, j) => (
                            <span key={j} style={{ color: '#666688', fontSize: '0.72rem', backgroundColor: '#12122a', borderRadius: '4px', padding: '2px 8px', border: '1px solid #1e1e3a' }}>{ev}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {report.domains && Object.keys(report.domains).length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: '#8888aa', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '12px' }}>八大生活领域</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
                    {Object.entries(report.domains).map(([key, text]) => (
                      <div key={key} style={{ backgroundColor: '#0a0a1e', border: '1px solid #1e1e4a', borderRadius: '8px', padding: '12px' }}>
                        <div style={{ color: '#9999cc', fontSize: '0.75rem', fontWeight: 600, marginBottom: '6px' }}>
                          {THEME_NAMES[key] || key}
                        </div>
                        <p style={{ color: '#aaaacc', fontSize: '0.82rem', lineHeight: 1.6, margin: 0 }}>{text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {report.suggestions?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: '#8888aa', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '10px' }}>实用建议</h3>
                  {report.suggestions.map((s, i) => (
                    <div key={i} style={{ display: 'flex', gap: '10px', marginBottom: '8px', alignItems: 'flex-start' }}>
                      <span style={{ color: '#c9a84c', fontWeight: 700, minWidth: '20px' }}>{i + 1}.</span>
                      <span style={{ color: '#aaaacc', fontSize: '0.84rem', lineHeight: 1.6 }}>{s}</span>
                    </div>
                  ))}
                </div>
              )}

              <SourcesSection sources={report.sources} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
