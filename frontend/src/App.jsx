import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import './index.css'
import NatalChart from './pages/NatalChart'
import Transits from './pages/Transits'
import Synastry from './pages/Synastry'
import Progressions from './pages/Progressions'
import SolarReturn from './pages/SolarReturn'
import Directions from './pages/Directions'
import Interpretations from './pages/Interpretations'

const NAV_ITEMS = [
  { path: '/',              label: '星盘' },
  { path: '/transits',     label: '行运' },
  { path: '/synastry',     label: '合盘' },
  { path: '/progressions', label: '推运' },
  { path: '/solar-return', label: '太阳回归' },
  { path: '/directions',   label: '方向法' },
  { path: '/interpretations', label: '解释' },
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

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen" style={{ backgroundColor: '#0a0a1a' }}>

        {/* Sticky header */}
        <header style={{
          position: 'sticky', top: 0, zIndex: 50,
          backgroundColor: '#0d0d22',
          borderBottom: '1px solid #2a2a5a',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '8px 48px' }}>
            {/* Logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <span style={{ color: '#c9a84c', fontSize: '1.3rem' }}>✦</span>
              <span style={{ color: '#c9a84c', fontSize: '1rem', fontWeight: 700, letterSpacing: '0.15em' }}>
                ASTRO
              </span>
            </div>

            {/* Nav tabs */}
            <nav style={{ display: 'flex', flex: 1, gap: '4px', padding: '0 32px' }}>
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
          </div>
        </header>

        {/* Page content */}
        <main style={{ padding: '32px 48px' }}>
          <Routes>
            <Route path="/"              element={<NatalChart />} />
            <Route path="/transits"      element={<Transits />} />
            <Route path="/synastry"      element={<Synastry />} />
            <Route path="/progressions"  element={<Progressions />} />
            <Route path="/solar-return"  element={<SolarReturn />} />
            <Route path="/directions"    element={<Directions />} />
            <Route path="/interpretations" element={<Interpretations />} />
          </Routes>
        </main>

      </div>
    </BrowserRouter>
  )
}
