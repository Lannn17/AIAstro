import { createContext, useContext, useState, useEffect } from 'react'
import { setRegionGetter } from '../utils/apiFetch'

const RegionContext = createContext({ region: 'GLOBAL', isAuto: false })

export function useRegion() {
  return useContext(RegionContext)
}

export function RegionProvider({ children }) {
  const [region, setRegionState] = useState('GLOBAL')
  const [isAuto, setIsAuto] = useState(false)

  // Wire apiFetch to always use the latest region value
  useEffect(() => {
    setRegionGetter(() => region)
  }, [region])

  // On mount: check localStorage first, then IP detect
  useEffect(() => {
    const stored = localStorage.getItem('region')
    if (stored === 'CN' || stored === 'GLOBAL') {
      setRegionState(stored)
      setIsAuto(false)
    } else {
      // Auto-detect via backend IP check
      fetch('/api/region')
        .then(r => r.json())
        .then(data => {
          const detected = data.region === 'CN' ? 'CN' : 'GLOBAL'
          setRegionState(detected)
          setIsAuto(true)
        })
        .catch(() => {
          setRegionState('GLOBAL')
          setIsAuto(false)
        })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function setRegion(val) {
    localStorage.setItem('region', val)
    setRegionState(val)
    setIsAuto(false)
  }

  function resetToAuto() {
    localStorage.removeItem('region')
    setIsAuto(true)
    fetch('/api/region')
      .then(r => r.json())
      .then(data => {
        setRegionState(data.region === 'CN' ? 'CN' : 'GLOBAL')
      })
      .catch(() => setRegionState('GLOBAL'))
  }

  return (
    <RegionContext.Provider value={{ region, isAuto, setRegion, resetToAuto }}>
      {children}
    </RegionContext.Provider>
  )
}
