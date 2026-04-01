import { createContext, useContext, useState, useCallback } from 'react'

const PromptRatingContext = createContext(null)

export function PromptRatingProvider({ children }) {
  // logId of the most recent AI result that hasn't been rated yet
  const [pendingLogId, setPendingLogId] = useState(null)
  // Skip count for soft-enforcement logic
  const [skipCount, setSkipCount] = useState(0)

  const registerResult = useCallback((logId) => {
    // Called by AI result components after receiving a response
    setPendingLogId(logId)
  }, [])

  const clearPending = useCallback(() => {
    setPendingLogId(null)
  }, [])

  const recordSkip = useCallback(() => {
    setSkipCount(n => n + 1)
  }, [])

  const resetSkipCount = useCallback(() => {
    setSkipCount(0)
  }, [])

  return (
    <PromptRatingContext.Provider value={{
      pendingLogId,
      skipCount,
      registerResult,
      clearPending,
      recordSkip,
      resetSkipCount,
    }}>
      {children}
    </PromptRatingContext.Provider>
  )
}

export function usePromptRating() {
  const ctx = useContext(PromptRatingContext)
  if (!ctx) throw new Error('usePromptRating must be used inside PromptRatingProvider')
  return ctx
}