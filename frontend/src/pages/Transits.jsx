import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useChartSession } from '../contexts/ChartSessionContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

// ── 符号表 ──────────────────────────────────────────────────────

const PLANET_SYMBOLS = {
  sun: '☉', moon: '☽', mercury: '☿', venus: '♀', mars: '♂',
  jupiter: '♃', saturn: '♄', uranus: '♅', neptune: '♆', pluto: '♇',
  mean_node: '☊', true_node: '☊', mean_south_node: '☋', true_south_node: '☋', chiron: '⚷', mean_lilith: '⚸',
}

const ASPECT_ZH = {
  Conjunction: '合相', Opposition: '对分相', Square: '刑相',
  Trine: '三分相', Sextile: '六分相', Quincunx: '补十二分相',
}

const ASPECT_COLOR = {
  Conjunction: '#ffffff', Opposition: '#ff6666', Square: '#ff9944',
  Trine: '#66cc88', Sextile: '#44aaff', Quincunx: '#bb88ff',
}

const TONE_COLOR = {
  '顺势': '#66cc88',
  '挑战': '#ff9944',
  '转化': '#bb88ff',
}

function planetKey(name) {
  const map = {
    '太阳': 'sun', '月亮': 'moon', '水星': 'mercury', '金星': 'venus',
    '火星': 'mars', '木星': 'jupiter', '土星': 'saturn', '天王星': 'uranus',
    '海王星': 'neptune', '冥王星': 'pluto', '北交点': 'mean_node', '南交点': 'mean_south_node',
    '凯龙星': 'chiron', '黑月莉莉丝': 'mean_lilith',
    'Sun': 'sun', 'Moon': 'moon', 'Mercury': 'mercury', 'Venus': 'venus',
    'Mars': 'mars', 'Jupiter': 'jupiter', 'Saturn': 'saturn',
    'Uranus': 'uranus', 'Neptune': 'neptune', 'Pluto': 'pluto',
  }
  return map[name] || name.toLowerCase().replace(' ', '_')
}

// ── 样式常量 ─────────────────────────────────────────────────────

const inputStyle = {
  width: '100%', background: '#0e0e24', border: '1px solid #2a2a5a',
  color: '#d0d0e0', borderRadius: '6px', padding: '8px 10px',
  fontSize: '0.85rem', boxSizing: 'border-box',
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

// ── 组件 ─────────────────────────────────────────────────────────

export default function Transits() {
  const { isAuthenticated, authHeaders } = useAuth()
  const { sessionChart } = useChartSession()

  const [savedCharts, setSavedCharts]     = useState([])
  const [selectedId, setSelectedId]       = useState('')
  const [selectedChart, setSelectedChart] = useState(null)
  const [queryDate, setQueryDate]         = useState(todayStr)
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState(null)
  const [result, setResult]               = useState(null)   // {active_transits, overall}
  const [forceRefresh, setForceRefresh]   = useState(false)

  useEffect(() => {
    if (!isAuthenticated) return
    fetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(setSavedCharts)
      .catch(() => {})
  }, [isAuthenticated])

  async function handleSelectChart(id) {
    setSelectedId(id)
    setResult(null)
    setError(null)
    if (!id) { setSelectedChart(null); return }
    if (id === '__session__') {
      if (!sessionChart) { setSelectedChart(null); return }
      const f = sessionChart.formData
      setSelectedChart({
        birth_year: f.year, birth_month: f.month, birth_day: f.day,
        birth_hour: f.hour, birth_minute: f.minute,
        latitude: f.latitude, longitude: f.longitude,
        tz_str: f.tz_str, house_system: f.house_system,
        language: f.language,
        chart_data: sessionChart.chartData,
        location_name: sessionChart.locationName,
      })
      return
    }
    try {
      const headers = authHeaders()
      const r = await fetch(`${API_BASE}/api/charts/${id}`, { headers })
      if (r.ok) setSelectedChart(await r.json())
    } catch { setError('加载星盘失败') }
  }

  async function generate(force = false) {
    if (!selectedChart) return
    setLoading(true)
    setError(null)
    setResult(null)
    setForceRefresh(force)

    const c = selectedChart
    const natalInfo = {
      year: c.birth_year, month: c.birth_month, day: c.birth_day,
      hour: c.birth_hour, minute: c.birth_minute,
      latitude: c.latitude, longitude: c.longitude,
      tz_str: c.tz_str, house_system: c.house_system,
    }
    const natalChartData = c.chart_data
      ? (typeof c.chart_data === 'string' ? JSON.parse(c.chart_data) : c.chart_data)
      : {}

    try {
      const r = await fetch(`${API_BASE}/api/interpret/transits_full`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chart_id:         selectedId === '__session__' ? 0 : Number(selectedId),
          natal_info:       natalInfo,
          natal_chart_data: natalChartData,
          query_date:       queryDate,
          language:         'zh',
          force_refresh:    force,
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        throw new Error(err.detail || `错误 ${r.status}`)
      }
      setResult(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* 页眉 */}
      <div className="mb-6">
        <h1 style={{ color: '#c9a84c', fontSize: '1.4rem', fontWeight: 600, letterSpacing: '0.08em' }}>
          ♂ 行运
        </h1>
        <p style={{ color: '#8888aa', fontSize: '0.8rem', marginTop: '4px' }}>
          查看指定日期的活跃行运相位及 AI 解读
        </p>
      </div>

      <div className="transits-layout">

        {/* ── 左栏：控制面板 ── */}
        <div className="transits-control">
          <div style={{ background: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '20px' }}>

            <Label>选择本命盘</Label>
            <select
              value={selectedId}
              onChange={e => handleSelectChart(e.target.value)}
              style={{ ...inputStyle, marginBottom: '4px' }}
            >
              <option value="">-- 请选择 --</option>
              {sessionChart && (
                <option value="__session__">
                  {sessionChart.formData?.name || '当前星盘'}（未保存）
                </option>
              )}
              {savedCharts.map(c => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
            {savedCharts.length === 0 && !sessionChart && (
              <p style={{ color: '#555577', fontSize: '0.78rem', marginTop: '6px' }}>
                请先在「星盘」页面计算本命盘
              </p>
            )}

            <Label style={{ marginTop: '18px' }}>查询日期</Label>
            <input
              type="date"
              value={queryDate}
              onChange={e => setQueryDate(e.target.value)}
              style={inputStyle}
            />
            <p style={{ color: '#555577', fontSize: '0.75rem', marginTop: '6px' }}>
              默认今天 · 容许度 1°
            </p>

            <button
              onClick={() => generate(false)}
              disabled={!selectedChart || loading}
              style={{
                width: '100%', marginTop: '18px', padding: '10px',
                background: selectedChart && !loading ? '#c9a84c' : '#1e1e3a',
                color: selectedChart && !loading ? '#0a0a18' : '#3a3a5a',
                border: 'none', borderRadius: '8px', fontWeight: 700,
                cursor: selectedChart && !loading ? 'pointer' : 'not-allowed',
                fontSize: '0.9rem', transition: 'background 0.2s',
              }}
            >
              {loading && !forceRefresh ? '分析中…' : '生成行运分析'}
            </button>

            {result && (
              <button
                onClick={() => generate(true)}
                disabled={loading}
                style={{
                  width: '100%', marginTop: '8px', padding: '8px',
                  background: 'transparent',
                  color: loading ? '#3a3a5a' : '#8888aa',
                  border: '1px solid #2a2a5a', borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '0.8rem',
                }}
              >
                {loading && forceRefresh ? '重新生成中…' : '↺ 重新生成 AI 解读'}
              </button>
            )}

            {error && (
              <p style={{ color: '#ff6666', fontSize: '0.8rem', marginTop: '10px' }}>{error}</p>
            )}
          </div>
        </div>

        {/* ── 右栏：结果 ── */}
        <div className="transits-results">

          {/* 空态 */}
          {!result && !loading && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '320px', background: '#12122a',
              border: '1px dashed #2a2a5a', borderRadius: '12px', color: '#3a3a6a',
            }}>
              选择本命盘并点击「生成行运分析」
            </div>
          )}

          {/* 加载态 */}
          {loading && (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '320px', gap: '16px',
            }}>
              <span style={{ fontSize: '2rem', animation: 'spin 1.5s linear infinite', display: 'inline-block' }}>◌</span>
              <div style={{ color: '#8888aa', fontSize: '0.9rem', textAlign: 'center', lineHeight: '1.7' }}>
                正在计算行运窗口并生成 AI 解读…<br />
                <span style={{ color: '#555577', fontSize: '0.8rem' }}>首次请求约需 20-40 秒，相同日期再次查询将立即返回</span>
              </div>
            </div>
          )}

          {/* 结果 */}
          {result && !loading && (
            <>
              {/* 摘要行 */}
              <div style={{ color: '#555577', fontSize: '0.8rem', marginBottom: '16px' }}>
                {queryDate} · 发现 {result.active_transits.length} 个活跃相位（容许度 ≤ 1°）
              </div>

              {result.active_transits.length === 0 && (
                <div style={{
                  background: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px',
                  padding: '40px', textAlign: 'center', color: '#555577',
                }}>
                  当前日期没有在 1° 容许度内的行运相位
                </div>
              )}

              {/* 逐相位卡片：新行运在前，缓存行运在后 */}
              {[...result.active_transits]
                .sort((a, b) => (a.is_new === b.is_new ? 0 : a.is_new ? -1 : 1))
                .map(t => (
                  <TransitCard key={t.key} transit={t} />
                ))}

              {/* 整体报告 */}
              {result.overall && (
                <div style={{
                  background: '#12122a', border: '1px solid #3a3a6a',
                  borderRadius: '12px', padding: '24px', marginTop: '8px',
                }}>
                  <div style={{ color: '#c9a84c', fontSize: '0.95rem', fontWeight: 700,
                    letterSpacing: '0.06em', marginBottom: '16px' }}>
                    ✦ 整体行运综述
                  </div>
                  <div style={{
                    color: '#d0d0e0', fontSize: '0.9rem', lineHeight: '2',
                    whiteSpace: 'pre-wrap',
                  }}>
                    {result.overall}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── 单相位卡片 ────────────────────────────────────────────────────

function TransitCard({ transit: t }) {
  const tSym    = PLANET_SYMBOLS[planetKey(t.transit_planet_zh)] || PLANET_SYMBOLS[planetKey(t.transit_planet)] || ''
  const nSym    = PLANET_SYMBOLS[planetKey(t.natal_planet_zh)]   || PLANET_SYMBOLS[planetKey(t.natal_planet)]   || ''
  const aspZh   = ASPECT_ZH[t.aspect] ?? (() => {
    console.warn(`[Transits] 未映射的相位名: "${t.aspect}" — 请在 ASPECT_ZH 中添加中文翻译`)
    return t.aspect
  })()
  const aspColor  = ASPECT_COLOR[t.aspect] || '#d0d0e0'
  const toneColor = TONE_COLOR[t.tone] || '#8888aa'

  const days    = Math.round((new Date(t.end_date) - new Date(t.start_date)) / 86400000)
  const elapsed = Math.round((new Date() - new Date(t.start_date)) / 86400000)
  const retro   = t.retrograde_cycle ? `含逆行·${t.pass_count} 次精确` : null

  return (
    <div style={{
      background: '#12122a',
      border: `1px solid ${t.is_new ? '#3a2a6a' : '#2a2a5a'}`,
      borderRadius: '12px', marginBottom: '12px', overflow: 'hidden',
    }}>
      {/* 卡片头 */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #1a1a3a' }}>
        {/* 行星 + 相位行 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {t.is_new && (
            <span style={{
              background: '#3a2a6a', color: '#bb88ff',
              fontSize: '0.7rem', fontWeight: 700, padding: '1px 6px',
              borderRadius: '4px', letterSpacing: '0.05em',
            }}>新</span>
          )}
          <span style={{ color: '#c9a84c', fontSize: '1.1rem' }}>{tSym}</span>
          <span style={{ color: '#e0e0f0', fontWeight: 600 }}>{t.transit_planet_zh}</span>
          <span style={{ color: aspColor, fontWeight: 700, padding: '1px 8px',
            background: aspColor + '18', borderRadius: '4px', fontSize: '0.85rem' }}>
            {aspZh}
          </span>
          <span style={{ color: '#8888aa', fontSize: '1rem' }}>{nSym}</span>
          <span style={{ color: '#d0d0e0' }}>{t.natal_planet_zh}</span>

          {t.tone && (
            <span style={{
              color: toneColor, fontSize: '0.78rem', fontWeight: 600,
              padding: '1px 8px', background: toneColor + '18', borderRadius: '4px',
            }}>
              {t.tone}
            </span>
          )}

          <span style={{ marginLeft: 'auto', display: 'flex', gap: '10px', alignItems: 'center' }}>
            <span style={{
              color: t.current_orb <= 0.3 ? '#c9a84c' : '#8888aa',
              fontSize: '0.82rem', fontWeight: 600,
            }}>
              {t.current_orb.toFixed(2)}°
            </span>
            <span style={{
              color: t.applying ? '#66cc88' : '#8888aa',
              fontSize: '0.78rem',
            }}>
              {t.applying ? '⬆ 入相' : '⬇ 出相'}
            </span>
          </span>
        </div>

        {/* 主题标签 */}
        {t.themes && t.themes.length > 0 && (
          <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {t.themes.map(theme => (
              <span key={theme} style={{
                background: '#1e1e3a', color: '#8888cc',
                fontSize: '0.73rem', padding: '2px 8px', borderRadius: '10px',
                border: '1px solid #2a2a5a',
              }}>{theme}</span>
            ))}
          </div>
        )}

        {/* 时间行 */}
        <div style={{ marginTop: '8px', display: 'flex', gap: '12px', flexWrap: 'wrap',
          color: '#555577', fontSize: '0.78rem' }}>
          <span>{t.start_date} — {t.end_date}</span>
          <span>·</span>
          <span>共 {days} 天（已过 {Math.max(0, elapsed)} 天）</span>
          {retro && <><span>·</span><span style={{ color: '#bb88ff' }}>{retro}</span></>}
        </div>
      </div>

      {/* AI 分析 */}
      {t.analysis && (
        <div style={{
          padding: '16px 20px',
          color: '#c8c8e0', fontSize: '0.87rem', lineHeight: '1.95',
          whiteSpace: 'pre-wrap',
        }}>
          {t.analysis}
        </div>
      )}
    </div>
  )
}

// ── 辅助组件 ─────────────────────────────────────────────────────

function Label({ children, style }) {
  return (
    <div style={{ color: '#c9a84c', fontSize: '0.82rem', fontWeight: 600,
      marginBottom: '8px', ...style }}>
      {children}
    </div>
  )
}
