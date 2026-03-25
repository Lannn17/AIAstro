import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token'))
  const [isGuest, setIsGuest] = useState(() => localStorage.getItem('guest_mode') === 'true')
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [sessionKey, setSessionKey] = useState(0)

  useEffect(() => {
    if (!token && !isGuest) {
      setShowLoginModal(true)
    }
  }, [])

  async function login(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '登录失败')
    }
    const { access_token } = await res.json()
    localStorage.setItem('auth_token', access_token)
    localStorage.removeItem('guest_mode')
    setToken(access_token)
    setIsGuest(false)
    setShowLoginModal(false)
    setSessionKey(k => k + 1)
  }

  function continueAsGuest() {
    localStorage.setItem('guest_mode', 'true')
    localStorage.removeItem('auth_token')
    setIsGuest(true)
    setToken(null)
    setShowLoginModal(false)
    setSessionKey(k => k + 1)
  }

  function logout() {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('guest_mode')
    setToken(null)
    setIsGuest(false)
    setShowLoginModal(true)
    setSessionKey(k => k + 1)
  }

  function authHeaders() {
    if (token) return { Authorization: `Bearer ${token}` }
    return {}
  }

  return (
    <AuthContext.Provider value={{
      token,
      isGuest,
      isAuthenticated: !!token,
      login,
      continueAsGuest,
      logout,
      authHeaders,
      showLoginModal,
      setShowLoginModal,
      sessionKey,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
