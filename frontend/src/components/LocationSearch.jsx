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

// GCJ-02 → WGS-84（与后端 gcj02_to_wgs84 同款公式）
function gcj02ToWgs84(lng, lat) {
  const a = 6378245.0
  const ee = 0.00669342162296594323
  const transformLat = (x, y) => {
    let r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
    r += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0
    r += (20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin(y / 3.0 * Math.PI)) * 2.0 / 3.0
    r += (160.0 * Math.sin(y / 12.0 * Math.PI) + 320.0 * Math.sin(y * Math.PI / 30.0)) * 2.0 / 3.0
    return r
  }
  const transformLng = (x, y) => {
    let r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
    r += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0
    r += (20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin(x / 3.0 * Math.PI)) * 2.0 / 3.0
    r += (150.0 * Math.sin(x / 12.0 * Math.PI) + 300.0 * Math.sin(x / 30.0 * Math.PI)) * 2.0 / 3.0
    return r
  }
  const dLat = transformLat(lng - 105.0, lat - 35.0)
  const dLng = transformLng(lng - 105.0, lat - 35.0)
  const radLat = lat / 180.0 * Math.PI
  let magic = Math.sin(radLat)
  magic = 1 - ee * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  const corrLat = dLat * 180.0 / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI)
  const corrLng = dLng * 180.0 / (a / sqrtMagic * Math.cos(radLat) * Math.PI)
  return [lng - corrLng, lat - corrLat]
}

/**
 * Reusable location search input.
 * CN region: 高德 JS SDK (AMap.AutoComplete) via /_AMapService proxy.
 * GLOBAL region: Nominatim via /api/geocode backend proxy.
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

      if (region === 'CN') {
        // 高德 JS SDK（安全密钥通过 /_AMapService 代理注入）
        const AMap = window.AMap
        if (!AMap || !AMap.AutoComplete) {
          setSearchFailed(true)
          setSearching(false)
          return
        }
        const ac = new AMap.AutoComplete({ city: '全国' })
        ac.search(value, (status, result) => {
          setSearching(false)
          if (status === 'complete' && result.tips?.length > 0) {
            const mapped = result.tips
              .filter(t => t.location && t.location.lng != null && t.location.lat != null)
              .map((t, i) => {
                const [wgsLng, wgsLat] = gcj02ToWgs84(t.location.lng, t.location.lat)
                return {
                  place_id: `amap_${i}_${t.id || t.name}`,
                  display_name: t.district ? `${t.name}，${t.district}` : t.name,
                  lat: wgsLat.toFixed(6),
                  lon: wgsLng.toFixed(6),
                }
              })
            setSuggestions(mapped)
            if (mapped.length === 0) setSearchFailed(true)
          } else {
            setSearchFailed(true)
          }
        })
      } else {
        // GLOBAL: Nominatim via backend proxy
        try {
          const res = await fetch(
            `/api/geocode?q=${encodeURIComponent(value)}&region=GLOBAL`
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
