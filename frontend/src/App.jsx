import { BrowserRouter, Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import './index.css'
import NatalChart from './pages/NatalChart'
import Transits from './pages/Transits'
import Synastry from './pages/Synastry'
import Progressions from './pages/Progressions'
import SolarReturn from './pages/SolarReturn'
import Directions from './pages/Directions'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ChartSessionProvider, useChartSession } from './contexts/ChartSessionContext'
import { RegionProvider, useRegion } from './contexts/RegionContext'
import WelcomeModal from "./components/WelcomeModal"
import LoginModal from './components/LoginModal'
import { PromptRatingProvider } from './contexts/PromptRatingContext'
import PromptRatingModal from './components/PromptRatingModal'
import { usePromptRating } from './contexts/PromptRatingContext'
import FeedbackButton from './components/FeedbackButton'
import AdminPrompts from './pages/AdminPrompts'
import AdminPromptDetail from './pages/AdminPromptDetail'

const NAV_ITEMS = [
  { path: '/',              label: '星盘' },
  { path: '/transits',     label: '行运' },
  { path: '/solar-return', label: '太阳回归' },
  { path: '/progressions', label: '月亮推运' },
  { path: '/synastry',     label: '合盘' },
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
  const { isAuthenticated, username, logout } = useAuth()

  if (isAuthenticated) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
        {username && (
          <span style={{ color: '#c9a84c', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
            {username}
          </span>
        )}
        <button
          onClick={logout}
          title="退出登录"
          style={{
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
      </div>
    )
  }

  return null
}

function RegionToggle() {
  const { region, isAuto, setRegion, resetToAuto } = useRegion()

  function handleClick(val) {
    if (region === val) {
      resetToAuto()
    } else {
      setRegion(val)
    }
  }

  const btnBase = {
    padding: '4px 8px',
    border: '1px solid #2a2a5a',
    borderRadius: '5px',
    fontSize: '0.72rem',
    cursor: 'pointer',
    background: 'transparent',
    color: '#8888aa',
    whiteSpace: 'nowrap',
    lineHeight: 1.2,
  }

  const btnActive = {
    ...btnBase,
    borderColor: '#c9a84c',
    color: '#c9a84c',
  }

  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexShrink: 0 }}>
      <button
        style={region === 'GLOBAL' ? btnActive : btnBase}
        onClick={() => handleClick('GLOBAL')}
        title={region === 'GLOBAL' && isAuto ? '自动检测（点击重置）' : undefined}
      >
        🌐 海外
      </button>
      <button
        style={region === 'CN' ? btnActive : btnBase}
        onClick={() => handleClick('CN')}
        title={region === 'CN' && isAuto ? '自动检测（点击重置）' : undefined}
      >
        🇨🇳 国内
      </button>
      {isAuto && (
        <span style={{ fontSize: '0.65rem', color: '#555577', marginLeft: '2px' }}>
          自动
        </span>
      )}
    </div>
  )
}

function InterceptedNavLink({ path, label }) {
  const { pendingLogId } = usePromptRating()
  const navigate = useNavigate()
  const [showRating, setShowRating] = useState(false)

  function handleClick(e) {
    if (pendingLogId) {
      e.preventDefault()
      setShowRating(true)
    }
  }

  return (
    <>
      <NavLink
        to={path}
        end={path === '/'}
        style={navLinkStyle}
        onClick={handleClick}
      >
        {label}
      </NavLink>
      {showRating && (
        <PromptRatingModal
          onClose={() => {
            setShowRating(false)
            navigate(path)
          }}
          onProceed={() => {
            setShowRating(false)
            navigate(path)
          }}
        />
      )}
    </>
  )
}

function AppInner() {
  const { sessionKey, isAuthenticated, isAdmin } = useAuth()
  const { clearSessionCharts } = useChartSession()

  const navItems = [
    ...NAV_ITEMS,
    ...(isAuthenticated && isAdmin ? [{ path: '/admin/prompts', label: '管理' }] : []),
  ]

  useEffect(() => {
    clearSessionCharts()
  }, [sessionKey]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BrowserRouter>
      <PromptRatingProvider>
      <LoginModal />
      <WelcomeModal />
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
              {navItems.map(({ path, label }) => (
                <InterceptedNavLink key={path} path={path} label={label} />
              ))}
            </nav>

            {/* User badge */}
            <UserBadge />
            {/* Region toggle */}
            <RegionToggle />
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
            <Route path="/admin"         element={<Navigate to="/admin/prompts" replace />} />
            <Route path="/admin/prompts"  element={isAdmin ? <AdminPrompts /> : <Navigate to="/" replace />} />
            <Route path="/admin/prompts/:id" element={isAdmin ? <AdminPromptDetail /> : <Navigate to="/" replace />} />
          </Routes>
        </main>

      <FeedbackButton />
      </div>
      </PromptRatingProvider>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <RegionProvider>
        <ChartSessionProvider>
          <AppInner />
        </ChartSessionProvider>
      </RegionProvider>
    </AuthProvider>
  )
}