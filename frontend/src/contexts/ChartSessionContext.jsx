import { createContext, useContext, useState, useCallback } from 'react'

const ChartSessionContext = createContext(null)

export function ChartSessionProvider({ children }) {
  // 会话星盘列表：[{ id, name, chartData, formData, svgData, locationName }]
  const [sessionCharts, setSessionCharts] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)

  const addSessionChart = useCallback((chart) => {
    const id = chart.id || `session-${Date.now()}`
    const entry = { ...chart, id }
    setSessionCharts(prev => {
      // 如果同名已存在则替换，否则追加
      const exists = prev.findIndex(c => c.name === entry.name)
      if (exists >= 0) {
        const next = [...prev]
        next[exists] = entry
        return next
      }
      return [...prev, entry]
    })
    setCurrentSessionId(id)
    return id
  }, [])

  const clearSessionCharts = useCallback(() => {
    setSessionCharts([])
    setCurrentSessionId(null)
  }, [])

  const currentSessionChart = sessionCharts.find(c => c.id === currentSessionId)
    ?? sessionCharts[0]
    ?? null

  return (
    <ChartSessionContext.Provider value={{
      sessionCharts,
      currentSessionId,
      currentSessionChart,   // 向后兼容：替代原 sessionChart
      addSessionChart,
      setCurrentSessionId,
      clearSessionCharts,
    }}>
      {children}
    </ChartSessionContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChartSession() {
  return useContext(ChartSessionContext)
}
