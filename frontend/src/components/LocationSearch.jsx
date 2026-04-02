import { useState, useEffect, useRef } from 'react'
import { useRegion } from '../contexts/RegionContext'

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

/**
 * Reusable location search input backed by backend geocode proxy.
 * CN region: 高德 REST API（后端代理，GCJ-02→WGS-84 转换在后端完成）
 * GLOBAL region: Nominatim via backend proxy.
 *
 * Props:
 *   initialValue  – location name to pre-fill on mount
 *   latitude      – current confirmed latitude (to show ✓ hint)
 *   longitude     – current confirmed longitude
 *   onSelect      – called with { latitude, longitude, locationName } when a result is chosen
 *                   called with { latitude: '', longitude: '', locationName: value } when input is cleared/changed
 */
export default function LocationSearch({ initialValue = '', latitude, longitude, onSelect, label = '出生地' }) {
  const { region } = useRegion()
  const [query, setQuery] = useState(initialValue)
  const [suggestions, setSuggestions] = useState([])
  const [searching, setSearching] = useState(false)
  const [searchFailed, setSearchFailed] = useState(false)
  const debounceRef = useRef(null)

  // Sync display when initialValue changes (e.g. parent loads a different chart)
  useEffect(() => {
    setQuery(initialValue || '')
    setSuggestions([])
    setSearchFailed(false)
  }, [initialValue])

  function handleInput(value) {
    setQuery(value)
    setSuggestions([])
    setSearchFailed(false)
    onSelect({ latitude: '', longitude: '', locationName: value })

    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (value.length < 2) return

    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await fetch(
          `/api/geocode?q=${encodeURIComponent(value)}&region=${encodeURIComponent(region)}`
        )
        const json = await res.json()
        const data = json.results || []
        setSuggestions(data)
        if (data.length === 0) setSearchFailed(true)
      } catch {
        setSearchFailed(true)
      } finally {
        setSearching(false)
      }
    }, 500)
  }

  function handleSelect(item) {
    setQuery(item.display_name)
    setSuggestions([])
    setSearchFailed(false)
    onSelect({
      latitude: parseFloat(item.lat).toFixed(4),
      longitude: parseFloat(item.lon).toFixed(4),
      locationName: item.display_name,
    })
  }

  const confirmed = latitude !== '' && longitude !== ''

  return (
    <div style={{ position: 'relative' }}>
      <label style={labelStyle}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          style={{
            ...inputStyle,
            borderColor: confirmed ? '#3a5a3a' : '#2a2a5a',
            paddingRight: searching ? '32px' : '10px',
          }}
          placeholder="搜索城市或地区…"
          value={query}
          onChange={e => handleInput(e.target.value)}
          autoComplete="off"
        />
        {searching && (
          <span style={{
            position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
            color: '#8888aa', fontSize: '0.75rem',
          }}>…</span>
        )}
      </div>

      {confirmed && (
        <div style={{ color: '#4a8a4a', fontSize: '0.7rem', marginTop: '4px' }}>
          ✓ {latitude}°, {longitude}°
        </div>
      )}

      {searchFailed && !confirmed && (
        <div style={{ color: '#8a4a4a', fontSize: '0.7rem', marginTop: '4px' }}>
          {region === 'CN'
            ? '未找到地点（国内模式，仅搜索中国地区）'
            : '未找到地点，请尝试其他关键词'}
        </div>
      )}

      {suggestions.length > 0 && (
        <ul style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          backgroundColor: '#1a1a35', border: '1px solid #2a2a5a',
          borderRadius: '6px', marginTop: '2px',
          listStyle: 'none', padding: 0,
          maxHeight: '240px', overflowY: 'auto',
        }}>
          {suggestions.map(item => (
            <li key={item.place_id || item.display_name}
              onClick={() => handleSelect(item)}
              style={{
                padding: '8px 12px', cursor: 'pointer',
                fontSize: '0.8rem', color: '#c8c8e8',
                borderBottom: '1px solid #1e1e3a',
              }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = '#22224a'}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              {item.display_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
