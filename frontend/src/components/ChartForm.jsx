import { useState, useEffect } from 'react'
import LocationSearch from './LocationSearch'

const HOUSE_SYSTEMS_INFO = [
  {
    name: 'Placidus',
    zh: '普拉西德斯',
    desc: '西方占星最主流的宫位系统，基于时间划分天球。适合大多数人的日常星盘分析。',
    strength: '对出生时间敏感，能精细反映人生时间节点。',
    for: '初学者和进阶者的首选，几乎所有主流软件默认使用。',
    caveat: '高纬度地区（北纬60°以上）宫位会严重扭曲，不建议使用。',
  },
  {
    name: 'Koch',
    zh: '科赫',
    desc: '与Placidus相近，但以出生地为中心重新定义时间段划分，宫位略有差异。',
    strength: '对个人命运走向的描述被认为更精准，尤其在推运和二次推进中表现突出。',
    for: '有一定基础、希望与Placidus对比研究的学习者。',
    caveat: '同样在高纬度失效。',
  },
  {
    name: 'Whole Sign',
    zh: '整个星座宫位',
    desc: '古代希腊-赫勒尼斯时期的系统，上升点所在星座整体为第一宫，每个宫位恰好对应一个星座30°。',
    strength: '结构清晰、无高纬度问题。与古典占星文本直接对应，解读传统技法时更准确。',
    for: '古典占星爱好者、研究希腊-阿拉伯占星传统的人，以及不确定出生时间（±30分钟误差内）的用户。',
    caveat: '行星可能"落入"与现代软件不同的宫位，初学者容易困惑。',
  },
  {
    name: 'Equal',
    zh: '等宫制',
    desc: '以上升点为起点，每宫均等30°向后划分，简单直观。',
    strength: '高纬度可用，无扭曲，逻辑一致。',
    for: '注重上升轴线的分析者，或作为验证其他系统的参照。',
    caveat: 'MC不一定落在第十宫，职业/社会地位的判断需另行计算。',
  },
  {
    name: 'Regiomontanus',
    zh: '雷基蒙塔努斯',
    desc: '中世纪流行的空间划分系统，以赤道等分为基础。',
    strength: '卜卦占星（Horary）的经典首选，对特定事件预测有独特优势。',
    for: '专注于卜卦占星和传统预测技法的进阶用户。',
    caveat: '用于本命盘分析时优势不明显，较小众。',
  },
  {
    name: 'Campanus',
    zh: '坎帕努斯',
    desc: '以地平圈为基础进行空间划分，与地平线方向紧密关联。',
    strength: '对"此刻此地"的空间感知有独特描述，部分传统认为更真实反映物质层面。',
    for: '研究空间占星或有特定哲学取向的进阶用户。',
    caveat: '当代使用较少，参考资料有限。',
  },
]

const TIMEZONES = [
  'Asia/Shanghai', 'Asia/Tokyo', 'Asia/Seoul', 'Asia/Hong_Kong',
  'Asia/Singapore', 'Asia/Kolkata', 'Asia/Dubai',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'America/New_York', 'America/Chicago', 'America/Los_Angeles',
  'America/Sao_Paulo', 'Australia/Sydney', 'Pacific/Auckland',
]

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

export default function ChartForm({ onSubmit, loading, initialData, onFormChange }) {
  const [form, setForm] = useState(() => initialData ? {
    name: initialData.name || '',
    year: String(initialData.year ?? ''),
    month: String(initialData.month ?? ''),
    day: String(initialData.day ?? ''),
    hour: String(initialData.hour ?? ''),
    minute: String(initialData.minute ?? ''),
    birth_time_confirmed: initialData.birth_time_confirmed ?? false,
    latitude: String(initialData.latitude ?? ''),
    longitude: String(initialData.longitude ?? ''),
    tz_str: initialData.tz_str || 'Asia/Shanghai',
    house_system: initialData.house_system || 'Placidus',
    language: initialData.language || 'zh',
  } : {
    name: '',
    year: '',
    month: '',
    day: '',
    hour: '',
    minute: '',
    birth_time_confirmed: false,
    latitude: '',
    longitude: '',
    tz_str: 'Asia/Shanghai',
    house_system: 'Placidus',
    language: 'zh',
  })
  const [locationName, setLocationName] = useState(initialData?.locationName || '')
  const [showHouseInfo, setShowHouseInfo] = useState(false)

  useEffect(() => {
    if (!showHouseInfo) return
    function onKey(e) { if (e.key === 'Escape') setShowHouseInfo(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [showHouseInfo])

  function set(field, value) {
    setForm(f => {
      const next = { ...f, [field]: value }
      onFormChange?.(next, locationName)
      return next
    })
  }

  function handleLocationSelect({ latitude, longitude, locationName: name }) {
    setForm(f => {
      const next = { ...f, latitude, longitude }
      onFormChange?.(next, name)
      return next
    })
    setLocationName(name)
  }

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit({
      ...form,
      year: parseInt(form.year),
      month: parseInt(form.month),
      day: parseInt(form.day),
      hour: parseInt(form.hour),
      minute: parseInt(form.minute),
      latitude: parseFloat(form.latitude),
      longitude: parseFloat(form.longitude),
      birth_time_confirmed: form.birth_time_confirmed,
    }, locationName)
  }

  const locationConfirmed = form.latitude !== '' && form.longitude !== ''
  // kept for submit button disabled check

  return (
    <form onSubmit={handleSubmit}
      className="rounded-xl p-5"
      style={{ backgroundColor: '#12122a', border: '1px solid #2a2a5a' }}
    >
      <div className="space-y-3">

        {/* Name */}
        <div>
          <label style={labelStyle}>姓名</label>
          <input style={inputStyle} placeholder="例：爱因斯坦"
            value={form.name} onChange={e => set('name', e.target.value)} />
        </div>

        {/* Date row */}
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label style={labelStyle}>年</label>
            <input style={inputStyle} type="number" placeholder="1990" required
              value={form.year} onChange={e => set('year', e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>月</label>
            <input style={inputStyle} type="number" min="1" max="12" placeholder="1–12" required
              value={form.month} onChange={e => set('month', e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>日</label>
            <input style={inputStyle} type="number" min="1" max="31" placeholder="1–31" required
              value={form.day} onChange={e => set('day', e.target.value)} />
          </div>
        </div>

        {/* Time row */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label style={labelStyle}>时</label>
            <input style={inputStyle} type="number" min="0" max="23" placeholder="0–23" required
              value={form.hour} onChange={e => set('hour', e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>分</label>
            <input style={inputStyle} type="number" min="0" max="59" placeholder="0–59" required
              value={form.minute} onChange={e => set('minute', e.target.value)} />
          </div>
        </div>

        {/* Birth time confirmation checkbox */}
        <div style={{
          borderRadius: '6px',
          padding: '10px 12px',
          backgroundColor: '#0d0d22',
          border: '1px solid #2a2a5a',
        }}>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.birth_time_confirmed}
              onChange={e => set('birth_time_confirmed', e.target.checked)}
              style={{ marginTop: '2px', accentColor: '#c9a84c', flexShrink: 0, cursor: 'pointer' }}
            />
            <span style={{ color: '#c8c8e8', fontSize: '0.8rem', lineHeight: 1.5 }}>
              我确认此出生时间精确到分钟
            </span>
          </label>
          {form.birth_time_confirmed ? (
            <p style={{ margin: '6px 0 0 24px', color: '#6a8a6a', fontSize: '0.72rem', lineHeight: 1.5 }}>
              感谢确认。此数据可能被匿名收集，用于训练出生时间校正模型，以提升未来的校正精准度。
            </p>
          ) : (
            <p style={{ margin: '6px 0 0 24px', color: '#8888aa', fontSize: '0.72rem', lineHeight: 1.5 }}>
              若不确定出生时间，可先计算星盘，生成后下方会出现「<span style={{ color: '#c9a84c' }}>出生时间校正</span>」按钮，通过生命事件反推更准确的出生时刻。
            </p>
          )}
        </div>

        {/* Location search */}
        <LocationSearch
          initialValue={initialData?.locationName || ''}
          latitude={form.latitude}
          longitude={form.longitude}
          onSelect={handleLocationSelect}
        />

        {/* Timezone */}
        <div>
          <label style={labelStyle}>时区</label>
          <select style={inputStyle} value={form.tz_str} onChange={e => set('tz_str', e.target.value)}>
            {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
          </select>
        </div>

        {/* House system + Language row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <label style={{ ...labelStyle, marginBottom: 0 }}>宫位系统</label>
              <button
                type="button"
                onClick={() => setShowHouseInfo(true)}
                style={{
                  width: '14px', height: '14px', borderRadius: '50%',
                  border: '1px solid #4a4a7a', backgroundColor: 'transparent',
                  color: '#6666aa', fontSize: '0.6rem', lineHeight: 1,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, padding: 0,
                }}
              >?</button>
            </div>
            <select style={inputStyle} value={form.house_system} onChange={e => set('house_system', e.target.value)}>
              {['Placidus','Koch','Whole Sign','Equal','Regiomontanus','Campanus'].map(s =>
                <option key={s} value={s}>{s}</option>
              )}
            </select>
          </div>
          <div>
            <label style={labelStyle}>语言</label>
            <select style={inputStyle} value={form.language} onChange={e => set('language', e.target.value)}>
              <option value="zh">中文</option>
              <option value="en">English</option>
              <option value="ja">日本語</option>
            </select>
          </div>
        </div>

      </div>

      {/* Submit */}
      <button type="submit" disabled={loading || !locationConfirmed}
        className="mt-5 w-full py-2 rounded-lg font-semibold tracking-wider transition-opacity"
        style={{
          backgroundColor: '#c9a84c',
          color: '#0a0a1a',
          opacity: (loading || !locationConfirmed) ? 0.5 : 1,
          cursor: (loading || !locationConfirmed) ? 'not-allowed' : 'pointer',
          fontSize: '0.9rem',
        }}
      >
        {loading ? '✦ 计算中…' : '✦ 计算星盘'}
      </button>

      {/* House system info modal */}
      {showHouseInfo && (
        <div
          onClick={() => setShowHouseInfo(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            backgroundColor: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            className="house-modal-inner"
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ color: '#c9a84c', fontSize: '1rem', fontWeight: 600, letterSpacing: '0.08em', margin: 0 }}>
                宫位系统说明
              </h2>
              <button
                onClick={() => setShowHouseInfo(false)}
                style={{ background: 'none', border: 'none', color: '#8888aa', fontSize: '1.2rem', cursor: 'pointer', lineHeight: 1 }}
              >✕</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {HOUSE_SYSTEMS_INFO.map(h => (
                <div key={h.name} style={{
                  borderRadius: '8px',
                  padding: '14px',
                  backgroundColor: form.house_system === h.name ? '#1a1a3a' : '#0d0d22',
                  border: `1px solid ${form.house_system === h.name ? '#c9a84c55' : '#1e1e3a'}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '6px' }}>
                    <span style={{ color: '#c9a84c', fontWeight: 600, fontSize: '0.9rem' }}>{h.name}</span>
                    <span style={{ color: '#6666aa', fontSize: '0.75rem' }}>{h.zh}</span>
                    {form.house_system === h.name && (
                      <span style={{ color: '#c9a84c', fontSize: '0.65rem', marginLeft: 'auto' }}>当前选择</span>
                    )}
                  </div>
                  <p style={{ color: '#c8c8e8', fontSize: '0.8rem', margin: '0 0 6px', lineHeight: 1.6 }}>{h.desc}</p>
                  <p style={{ color: '#8888aa', fontSize: '0.75rem', margin: '0 0 3px', lineHeight: 1.5 }}>
                    <span style={{ color: '#6a8a6a' }}>优势：</span>{h.strength}
                  </p>
                  <p style={{ color: '#8888aa', fontSize: '0.75rem', margin: '0 0 3px', lineHeight: 1.5 }}>
                    <span style={{ color: '#c9a84c99' }}>推荐：</span>{h.for}
                  </p>
                  {h.caveat && (
                    <p style={{ color: '#8888aa', fontSize: '0.75rem', margin: 0, lineHeight: 1.5 }}>
                      <span style={{ color: '#8a4a4a' }}>注意：</span>{h.caveat}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </form>
  )
}
