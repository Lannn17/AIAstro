import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { useEffect } from 'react'
import './index.css'
import NatalChart from './pages/NatalChart'
import Transits from './pages/Transits'
import Synastry from './pages/Synastry'
import Progressions from './pages/Progressions'
import SolarReturn from './pages/SolarReturn'
import Directions from './pages/Directions'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ChartSessionProvider, useChartSession } from './contexts/ChartSessionContext'
import Analytics from './pages/Analytics'
import LoginModal from './components/LoginModal'

const NAV_ITEMS = [
  { path: '/',              label: '星盘' },
  { path: '/transits',     label: '行运' },
  { path: '/synastry',     label: '合盘' },
  { path: '/progressions', label: '推运' },
  { path: '/solar-return', label: '太阳回归' },
  { path: '/directions',   label: '方向法' },
]

const navLinkStyle = ({ isActive }) => ({
  flex: '1 1 0',
  textAlign: 'center',
  padding: '8px 0',
  borderRadius: '6px',
  fontSize: '1rem',
  letterSpacing: '0.08em',
  fontWeight: 500,
  textDecoration: 'none',
  color: isActive ? '#0a0a1a' : '#8888aa',
  backgroundColor: isActive ? '#c9a84c' : 'transparent',
  transition: 'all 0.15s',
  whiteSpace: 'nowrap',
})

function UserBadge() {
  const { isAuthenticated, isGuest, logout, setShowLoginModal } = useAuth()

  if (isAuthenticated) {
    return (
      <button
        onClick={logout}
        title="退出登录"
        style={{
          flexShrink: 0,
          padding: '5px 12px',
          backgroundColor: 'transparent',
          border: '1px solid #3a3a6a',
          borderRadius: '6px',
          color: '#8888aa',
          fontSize: '0.78rem',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        退出
      </button>
    )
  }

  if (isGuest) {
    return (
      <button
        onClick={() => setShowLoginModal(true)}
        title="点击登录"
        style={{
          flexShrink: 0,
          padding: '5px 12px',
          backgroundColor: 'transparent',
          border: '1px solid #4a3a1a',
          borderRadius: '6px',
          color: '#c9a84c',
          fontSize: '0.78rem',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        访客 · 登录
      </button>
    )
  }

  return null
}

function AppInner() {
  const { sessionKey } = useAuth()
  const { clearSessionCharts } = useChartSession()

  useEffect(() => {
    clearSessionCharts()
  }, [sessionKey]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BrowserRouter>
      <LoginModal />
      <div className="min-h-screen" style={{ backgroundColor: '#0a0a1a' }}>

        {/* Sticky header */}
        <header style={{
          position: 'sticky', top: 0, zIndex: 50,
          backgroundColor: '#0d0d22',
          borderBottom: '1px solid #2a2a5a',
        }}>
          <div className="app-header-inner">
            {/* Logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <span style={{ color: '#c9a84c', fontSize: '1.3rem' }}>✦</span>
              <span style={{ color: '#c9a84c', fontSize: '1rem', fontWeight: 700, letterSpacing: '0.15em' }}>
                ASTRO
              </span>
            </div>

            {/* Nav tabs */}
            <nav className="app-nav">
              {NAV_ITEMS.map(({ path, label }) => (
                <NavLink
                  key={path}
                  to={path}
                  end={path === '/'}
                  style={navLinkStyle}
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            {/* User badge */}
            <UserBadge />
          </div>
        </header>

        {/* Page content */}
        <main key={sessionKey} className="app-main">
          <Routes>
            <Route path="/"              element={<NatalChart />} />
            <Route path="/transits"      element={<Transits />} />
            <Route path="/synastry"      element={<Synastry />} />
            <Route path="/progressions"  element={<Progressions />} />
            <Route path="/solar-return"  element={<SolarReturn />} />
            <Route path="/directions"    element={<Directions />} />
            <Route path="/admin"         element={<Analytics />} />
          </Routes>
        </main>

      </div>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ChartSessionProvider>
        <AppInner />
      </ChartSessionProvider>
    </AuthProvider>
  )
}
