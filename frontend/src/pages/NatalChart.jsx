import { useState, useEffect } from 'react'
import ChartForm from '../components/ChartForm'
import PlanetTable from '../components/PlanetTable'
import ChartWheel from '../components/ChartWheel'

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

  useEffect(() => { fetchSavedCharts() }, [])

  async function fetchSavedCharts() {
    try {
      const res = await fetch('/api/v1/charts')
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
      const res = await fetch('/api/v1/natal_chart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setResult(data)

      const svgRes = await fetch('/api/v1/svg_chart', {
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

      const res = await fetch('/api/v1/charts', {
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
      const res = await fetch(`/api/v1/charts/${summary.id}`)
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

  async function handleDelete(id, e) {
    e.stopPropagation()
    await fetch(`/api/v1/charts/${id}`, { method: 'DELETE' })
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
