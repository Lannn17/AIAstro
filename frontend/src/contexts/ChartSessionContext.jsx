import { createContext, useContext, useState } from 'react'

const ChartSessionContext = createContext(null)

export function ChartSessionProvider({ children }) {
  const [sessionChart, setSessionChart] = useState(null)
  // sessionChart shape: { chartData, formData, locationName }
  return (
    <ChartSessionContext.Provider value={{ sessionChart, setSessionChart }}>
      {children}
    </ChartSessionContext.Provider>
  )
}

export function useChartSession() {
  return useContext(ChartSessionContext)
}
