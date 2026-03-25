import { useChartSession } from '../contexts/ChartSessionContext'
import { useAuth } from '../contexts/AuthContext'

export default function GuestSessionList() {
  const { sessionCharts, currentSessionId, setCurrentSessionId } = useChartSession()
  const { setShowLoginModal } = useAuth()

  return (
    <div style={{
      backgroundColor: '#12122a',
      border: '1px solid #2a2a5a',
      borderRadius: '10px',
      overflow: 'hidden',
    }}>
      {/* 标题 */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid #2a2a5a',
        color: '#8888aa',
        fontSize: '0.75rem',
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
      }}>
        本次会话
      </div>

      {/* 星盘列表 */}
      <div style={{ padding: '8px' }}>
        {sessionCharts.length === 0 ? (
          <div style={{ color: '#3a3a6a', fontSize: '0.78rem', padding: '8px 6px' }}>
            暂无星盘，计算后自动显示
          </div>
        ) : (
          sessionCharts.map(c => (
            <div
              key={c.id}
              onClick={() => setCurrentSessionId(c.id)}
              style={{
                padding: '8px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
                backgroundColor: currentSessionId === c.id ? '#1e1e40' : 'transparent',
                color: currentSessionId === c.id ? '#c9a84c' : '#8888aa',
                fontSize: '0.82rem',
                marginBottom: '2px',
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => {
                if (currentSessionId !== c.id)
                  e.currentTarget.style.backgroundColor = '#16163a'
              }}
              onMouseLeave={e => {
                if (currentSessionId !== c.id)
                  e.currentTarget.style.backgroundColor = 'transparent'
              }}
            >
              {c.name || '未命名'}
            </div>
          ))
        )}
      </div>

      {/* 登录提示 */}
      <div style={{
        padding: '10px 14px',
        borderTop: '1px solid #2a2a5a',
        fontSize: '0.72rem',
        color: '#3a3a6a',
      }}>
        <span
          onClick={() => setShowLoginModal(true)}
          style={{ color: '#c9a84c', cursor: 'pointer', textDecoration: 'underline' }}
        >
          登录
        </span>
        {' '}后可永久保存星盘
        <div style={{ marginTop: '4px', color: '#2a2a4a' }}>刷新页面后数据将清除</div>
      </div>
    </div>
  )
}
