import { useState, useEffect, useRef } from 'react'
import { useRegion } from '../contexts/RegionContext'

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY || ''

async function searchAmap(query) {
  const res = await fetch(
    `https://restapi.amap.com/v3/geocode/geo?address=${encodeURIComponent(query)}&key=${AMAP_KEY}&output=json`
  )
  const data = await res.json()
  if (!data.geocodes || data.geocodes.length === 0) return []
  return data.geocodes.map((g, i) => ({
    place_id: `amap_${i}`,
    display_name: g.formatted_address,
    lat: g.location.split(',')[1],
    lon: g.location.split(',')[0],
  }))
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

/**
 * Reusable location search input backed by Nominatim.
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
        let data
        if (region === 'CN') {
          data = await searchAmap(value)
        } else {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(value)}&format=json&limit=6&addressdetails=1`,
            { headers: { 'Accept-Language': 'zh-CN,zh,en' } }
          )
          data = await res.json()
        }
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
          未找到地点，请尝试其他关键词
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
            <li key={item.place_id}
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
