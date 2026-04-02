import { createContext, useContext, useState } from 'react'
import { apiFetch } from '../utils/apiFetch'

const AuthContext = createContext(null)

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token'))
  const [username, setUsername] = useState(() => localStorage.getItem('auth_username') || '')
  const [isGuest] = useState(false)
  const [isAdmin, setIsAdmin] = useState(() => localStorage.getItem('is_admin') === 'true')
  const [showLoginModal, setShowLoginModal] = useState(
    () => !localStorage.getItem('auth_token')
  )
  const [sessionKey, setSessionKey] = useState(0)

  function _applyToken(access_token, admin, name) {
    localStorage.setItem('auth_token', access_token)
    localStorage.setItem('is_admin', admin ? 'true' : 'false')
    localStorage.setItem('auth_username', name || '')
    localStorage.removeItem('guest_mode')
    setToken(access_token)
    setIsAdmin(!!admin)
    setUsername(name || '')
    setShowLoginModal(false)
    setSessionKey(k => k + 1)
  }

  async function login(username, password) {
    const res = await apiFetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '登录失败')
    }
    const { access_token } = await res.json()
    // Fetch /me to get is_admin
    const meRes = await apiFetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    })
    const me = meRes.ok ? await meRes.json() : {}
    _applyToken(access_token, me.is_admin ?? false, me.username ?? username)
  }

  async function register(regUsername, password) {
    const res = await apiFetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: regUsername, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '注册失败')
    }
    const { access_token } = await res.json()
    // Registered users are never admin
    _applyToken(access_token, false, regUsername)
  }

  function logout() {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('guest_mode')
    localStorage.removeItem('is_admin')
    localStorage.removeItem('auth_username')
    setToken(null)
    setUsername('')
    setIsAdmin(false)
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
      username,
      isGuest,
      isAdmin,
      isAuthenticated: !!token,
      login,
      register,
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

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
