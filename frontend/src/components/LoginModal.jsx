import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

const inputStyle = {
  width: '100%', padding: '10px 12px',
  backgroundColor: '#1a1a3a', border: '1px solid #3a3a6a',
  borderRadius: '8px', color: '#e8e0f0', fontSize: '0.95rem',
  outline: 'none', boxSizing: 'border-box',
}

const btnPrimary = (disabled) => ({
  width: '100%', padding: '10px',
  backgroundColor: '#c9a84c', border: 'none',
  borderRadius: '8px', color: '#0a0a1a',
  fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer',
  opacity: disabled ? 0.5 : 1,
  marginTop: '4px',
})

export default function LoginModal() {
  const { showLoginModal, login, register, continueAsGuest } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'

  // Login state
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // Register state
  const [regUsername, setRegUsername] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm] = useState('')

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!showLoginModal) return null

  function switchMode(m) {
    setMode(m)
    setError('')
  }

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e) {
    e.preventDefault()
    setError('')
    if (regPassword !== regConfirm) {
      setError('两次输入的密码不一致')
      return
    }
    if (regPassword.length < 6) {
      setError('密码至少6位')
      return
    }
    if (regPassword.length > 16) {
      setError('密码最多16位')
      return
    }
    setLoading(true)
    try {
      await register(regUsername, regPassword)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      backgroundColor: 'rgba(10,10,26,0.92)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '16px',
    }}>
      <div style={{
        backgroundColor: '#0d0d22',
        border: '1px solid #2a2a5a',
        borderRadius: '12px',
        padding: '32px 28px',
        width: '100%',
        maxWidth: '360px',
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{ color: '#c9a84c', fontSize: '2rem', marginBottom: '8px' }}>✦</div>
          <div style={{ color: '#e8e0f0', fontSize: '1.2rem', fontWeight: 700, letterSpacing: '0.1em' }}>
            ASTRO
          </div>
        </div>

        {/* Tab switcher */}
        <div style={{ display: 'flex', marginBottom: '20px', borderRadius: '8px', overflow: 'hidden', border: '1px solid #2a2a5a' }}>
          {['login', 'register'].map(m => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              style={{
                flex: 1, padding: '8px',
                backgroundColor: mode === m ? '#1a1a4a' : 'transparent',
                border: 'none', color: mode === m ? '#e8e0f0' : '#5a5a8a',
                fontSize: '0.9rem', cursor: 'pointer', fontWeight: mode === m ? 600 : 400,
              }}
            >
              {m === 'login' ? '登录' : '注册'}
            </button>
          ))}
        </div>

        {/* Login form */}
        {mode === 'login' && (
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '14px' }}>
              <input
                type="text" placeholder="用户名" value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username" style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: '8px' }}>
              <input
                type="password" placeholder="密码" value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password" style={inputStyle}
              />
            </div>
            {error && (
              <div style={{ color: '#ff6b6b', fontSize: '0.82rem', marginBottom: '10px', textAlign: 'center' }}>
                {error}
              </div>
            )}
            <button type="submit" disabled={loading || !username || !password} style={btnPrimary(loading || !username || !password)}>
              {loading ? '登录中…' : '登录'}
            </button>
          </form>
        )}

        {/* Register form */}
        {mode === 'register' && (
          <form onSubmit={handleRegister}>
            <div style={{ marginBottom: '14px' }}>
              <input
                type="text" placeholder="用户名（最多50位）" value={regUsername}
                onChange={e => setRegUsername(e.target.value)}
                autoComplete="username" style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: '14px' }}>
              <input
                type="password" placeholder="密码（6-16位）" value={regPassword}
                onChange={e => setRegPassword(e.target.value)}
                autoComplete="new-password" style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: '8px' }}>
              <input
                type="password" placeholder="确认密码" value={regConfirm}
                onChange={e => setRegConfirm(e.target.value)}
                autoComplete="new-password" style={inputStyle}
              />
            </div>
            {error && (
              <div style={{ color: '#ff6b6b', fontSize: '0.82rem', marginBottom: '10px', textAlign: 'center' }}>
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading || !regUsername || !regPassword || !regConfirm}
              style={btnPrimary(loading || !regUsername || !regPassword || !regConfirm)}
            >
              {loading ? '注册中…' : '注册'}
            </button>
          </form>
        )}

        {/* Divider + Guest */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '18px 0' }}>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#2a2a5a' }} />
          <span style={{ color: '#5a5a8a', fontSize: '0.8rem' }}>或</span>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#2a2a5a' }} />
        </div>
        <button
          onClick={continueAsGuest}
          style={{
            width: '100%', padding: '10px',
            backgroundColor: 'transparent', border: '1px solid #3a3a6a',
            borderRadius: '8px', color: '#8888aa', fontSize: '0.9rem', cursor: 'pointer',
          }}
        >
          以访客身份使用
        </button>
        <div style={{ color: '#5a5a7a', fontSize: '0.75rem', textAlign: 'center', marginTop: '10px', lineHeight: 1.5 }}>
          访客可使用所有计算功能，但无法查看已保存的星盘
        </div>
        <div style={{ color: '#3a3a5a', fontSize: '0.7rem', textAlign: 'center', marginTop: '16px' }}>
          v{__APP_VERSION__}
        </div>
      </div>
    </div>
  )
}
