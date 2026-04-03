// frontend/src/pages/AstroDice.jsx
import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../utils/apiFetch'
import { SourcesSection } from '../components/AIPanel'
import DiceAnimation from '../components/DiceAnimation'

// 响应式断点 hook
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 640)
  useEffect(() => {
    const h = () => setIsMobile(window.innerWidth < 640)
    window.addEventListener('resize', h)
    return () => window.removeEventListener('resize', h)
  }, [])
  return isMobile
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const CATEGORIES = [
  { key: '事业', icon: '💼' },
  { key: '感情', icon: '❤️' },
  { key: '财务', icon: '💰' },
  { key: '家庭', icon: '🏠' },
  { key: '学习', icon: '📚' },
  { key: '其他', icon: '🔮' },
]

const PLANET_ICONS = {
  sun: '☀️', moon: '🌙', mercury: '☿', venus: '♀', mars: '♂',
  jupiter: '♃', saturn: '♄', uranus: '♅', neptune: '♆', pluto: '♇',
  north_node: '☊', chiron: '⚷',
}

// ── 功能说明卡片 ────────────────────────────────────────────────────
function GuideCard({ collapsed, onToggle }) {
  return (
    <div style={{
      background: '#0d0d22',
      border: '1px solid #2a2a5a',
      borderRadius: '12px',
      marginBottom: '28px',
      overflow: 'hidden',
    }}>
      <button
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 20px', background: 'transparent',
          border: 'none', cursor: 'pointer',
          color: '#c9a84c', fontSize: '0.95rem', fontWeight: 600,
        }}
      >
        <span>✦ 什么是占星骰子？</span>
        <span style={{ fontSize: '0.8rem', color: '#8888aa' }}>{collapsed ? '展开 ▾' : '收起 ▴'}</span>
      </button>

      {!collapsed && (
        <div style={{ padding: '0 20px 20px', color: '#c8c8e8', fontSize: '0.9rem', lineHeight: 1.8 }}>
          <p style={{ marginTop: 0 }}>
            占星骰子源自传统卜卦占星，通过掷出三颗骰子获得宇宙的随机指引。
            每颗骰子各司其职，三者组合构成一个完整的占星信息。
          </p>

          {/* 三骰说明 */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
            {[
              { emoji: '🎲', label: '行星骰', sub: '什么能量？', color: '#c9a84c', desc: '代表本次议题的核心驱动力与主题' },
              { emoji: '🎲', label: '星座骰', sub: '什么方式？', color: '#88aaff', desc: '代表能量的运作风格与处理方式' },
              { emoji: '🎲', label: '宫位骰', sub: '什么领域？', color: '#88cc88', desc: '代表这股能量落在你生活的哪个区域' },
            ].map(d => (
              <div key={d.label} style={{
                flex: '1 1 160px',
                background: '#12122a', borderRadius: '8px',
                padding: '12px 14px', border: '1px solid #2a2a4a',
              }}>
                <div style={{ fontSize: '1.4rem', marginBottom: '4px' }}>{d.emoji}</div>
                <div style={{ color: d.color, fontWeight: 600, fontSize: '0.88rem' }}>{d.label}</div>
                <div style={{ color: '#8888aa', fontSize: '0.8rem', marginBottom: '6px' }}>{d.sub}</div>
                <div style={{ color: '#a0a0c0', fontSize: '0.82rem' }}>{d.desc}</div>
              </div>
            ))}
          </div>

          {/* 示例 */}
          <div style={{
            background: '#12122a', borderRadius: '8px',
            padding: '12px 16px', marginBottom: '14px',
            borderLeft: '3px solid #c9a84c',
          }}>
            <div style={{ color: '#c9a84c', fontSize: '0.82rem', marginBottom: '6px', fontWeight: 600 }}>
              示例：金星 ＋ 天蝎座 ＋ 第7宫
            </div>
            <div style={{ color: '#a0a0c0', fontSize: '0.85rem' }}>
              在【一对一关系】领域，以【深入执着、洞察本质】的方式，处理与【价值观与关系】相关的议题。
            </div>
          </div>

          {/* 注意事项 */}
          <div style={{ color: '#8888aa', fontSize: '0.82rem', display: 'flex', gap: '8px' }}>
            <span>⚠️</span>
            <span>
              占星能量不应滥用——请在心中想好一个<strong style={{ color: '#c9c9e0' }}>具体且诚恳的问题</strong>再掷骰子。
              每天只能就一件事进行占卜。
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 骰子展示格 ──────────────────────────────────────────────────────
function DiceCard({ dice, label, color, inherited }) {
  if (!dice) return null
  const icon = dice.key ? (PLANET_ICONS[dice.key] || '🎲') : '🎲'
  const title = dice.name
  const sub = dice.core || dice.style || dice.domain
  return (
    <div style={{
      flex: '1 1 140px',
      background: '#0d0d22',
      border: `1px solid ${color}44`,
      borderRadius: '10px',
      padding: '14px',
      textAlign: 'center',
      position: 'relative',
    }}>
      {inherited && (
        <div style={{
          position: 'absolute', top: '6px', right: '8px',
          fontSize: '0.7rem', color: '#5a5a8a',
          background: '#1a1a3a', padding: '1px 6px', borderRadius: '8px',
        }}>沿用</div>
      )}
      <div style={{ fontSize: '2rem', marginBottom: '6px' }}>{icon}</div>
      <div style={{ color, fontWeight: 700, fontSize: '0.9rem', marginBottom: '2px' }}>{title}</div>
      <div style={{ color: '#8888aa', fontSize: '0.75rem', marginBottom: '4px' }}>{label}</div>
      <div style={{ color: '#a0a0c0', fontSize: '0.8rem' }}>{sub}</div>
    </div>
  )
}

// ── 主组件 ──────────────────────────────────────────────────────────
export default function AstroDice() {
  const { authHeaders, isAuthenticated } = useAuth()
  const isMobile = useIsMobile()
  const diceRef = useRef(null)

  const [guideCollapsed, setGuideCollapsed] = useState(false)
  const [question, setQuestion] = useState('')
  const [category, setCategory] = useState('其他')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // 星盘选择
  const [charts, setCharts] = useState([])
  const [selectedChartId, setSelectedChartId] = useState(null)

  // 主结果
  const [result, setResult] = useState(null)

  // 追问/补充状态
  const [rerollMode, setRerollMode] = useState(null)   // null | 'followup' | 'supplement'
  const [followupQ, setFollowupQ] = useState('')
  const [rerolling, setRerolling] = useState(false)
  const [rerollResult, setRerollResult] = useState(null)
  const [supplementResult, setSupplementResult] = useState(null)

  // 骰子动画弹窗
  const [showDiceModal, setShowDiceModal] = useState(false)
  const diceSettledResolve = useRef(null)
  const resultRef = useRef(null)

  // localStorage 历史（24h）
  const [localHistory, setLocalHistory] = useState([])

  // 拉取已保存星盘列表 + 加载本地历史
  useEffect(() => {
    if (!isAuthenticated) return
    apiFetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(data => setCharts(Array.isArray(data) ? data : []))
      .catch(() => {})

    // 读取并清理过期本地记录
    try {
      const raw = localStorage.getItem('dice_history')
      const all = raw ? JSON.parse(raw) : []
      const cutoff = Date.now() - 24 * 60 * 60 * 1000
      const fresh = all.filter(r => r.ts > cutoff)
      setLocalHistory(fresh)
      localStorage.setItem('dice_history', JSON.stringify(fresh))
    } catch {}
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  function _pushLocalHistory(dice, question, category, core_sentence) {
    try {
      const raw = localStorage.getItem('dice_history')
      const all = raw ? JSON.parse(raw) : []
      const cutoff = Date.now() - 24 * 60 * 60 * 1000
      const fresh = all.filter(r => r.ts > cutoff)
      const entry = { ts: Date.now(), question, category, core_sentence,
                      planet: dice.planet.name, sign: dice.sign.name, house: dice.house.number }
      const updated = [entry, ...fresh]
      localStorage.setItem('dice_history', JSON.stringify(updated))
      setLocalHistory(updated)
    } catch {}
  }

  if (!isAuthenticated) {
    return (
      <div style={{ color: '#8888aa', padding: '40px', textAlign: 'center' }}>
        请先登录
      </div>
    )
  }

  // ── 主掷骰 ──
  async function handleRoll() {
    if (!question.trim()) { setError('请先输入你想询问的问题'); return }
    setError('')
    setLoading(true)
    setResult(null)
    setRerollResult(null)
    setSupplementResult(null)
    setRerollMode(null)

    // 1. 先发 API 请求——429 直接拦截，不打开动画弹窗
    let apiData
    try {
      const res = await apiFetch(`${API_BASE}/api/dice/roll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          question: question.trim(),
          category,
          chart_id: selectedChartId || undefined,
        }),
      })
      if (res.status === 429) {
        const d = await res.json()
        setError(d.detail)
        setLoading(false)
        return
      }
      if (!res.ok) throw new Error(res.status)
      apiData = await res.json()
    } catch (e) {
      setError(`解读失败，请稍后重试（${e.message}）`)
      setLoading(false)
      return
    }

    // 2. API 成功后再显示骰子动画弹窗
    setShowDiceModal(true)
    await new Promise((resolve) => {
      diceSettledResolve.current = resolve
      setTimeout(() => { diceRef.current?.throwDice() }, 200)
      setTimeout(() => resolve(null), 8000)
    })

    // 3. 渲染结果
    setResult(apiData)
    setGuideCollapsed(true)
    _pushLocalHistory(apiData.dice_display, question.trim(), category, apiData.core_sentence)

    // 4. 停留一下让用户看到骰子停下的状态，再关弹窗并滚到结果顶部
    setTimeout(() => {
      setShowDiceModal(false)
      setLoading(false)
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 50)
    }, 1000)
  }

  // ── 再掷 ──
  async function handleReroll() {
    if (rerollMode === 'followup' && !followupQ.trim()) {
      setError('请输入追问方向'); return
    }
    setError('')
    setRerolling(true)
    setRerollResult(null)
    setSupplementResult(null)
    try {
      const dice = result.dice_display
      const res = await apiFetch(`${API_BASE}/api/dice/reroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          original_planet: dice.planet.key,
          original_sign:   dice.sign.key,
          original_house:  dice.house.number,
          original_question: question,
          category,
          mode: rerollMode,
          followup_question: rerollMode === 'followup' ? followupQ.trim() : undefined,
        }),
      })
      if (!res.ok) throw new Error(res.status)
      const data = await res.json()
      if (rerollMode === 'supplement') setSupplementResult(data)
      else setRerollResult(data)
      setRerollMode(null)
      setFollowupQ('')
    } catch (e) {
      setError(`再掷失败，请稍后重试（${e.message}）`)
    } finally {
      setRerolling(false)
    }
  }

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: isMobile ? '16px 12px' : '28px 16px', color: '#c8c8e8' }}>

      <h1 style={{ color: '#c9a84c', fontSize: isMobile ? '1.1rem' : '1.3rem', marginBottom: isMobile ? '14px' : '24px' }}>
        🎲 占星骰子
      </h1>

      {/* ── 3D 骰子动画弹窗 ── */}
      {showDiceModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          background: 'rgba(4,4,18,0.88)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: isMobile ? '92vw' : '560px',
            borderRadius: '16px', overflow: 'hidden',
            border: '1px solid #2a2a4a',
            boxShadow: '0 12px 60px rgba(0,0,0,0.8)',
          }}>
            <DiceAnimation
              ref={diceRef}
              height={isMobile ? 260 : 380}
              onSettled={(faceIndices) => {
                if (diceSettledResolve.current) {
                  diceSettledResolve.current(faceIndices)
                  diceSettledResolve.current = null
                }
              }}
            />
            <div style={{
              textAlign: 'center', padding: '10px 0 14px',
              background: '#080816', color: '#c9a84c',
              fontSize: '0.78rem', letterSpacing: '2px',
            }}>
              ✦ 命运之轮转动中… ✦
            </div>
          </div>
        </div>
      )}

      <GuideCard collapsed={guideCollapsed} onToggle={() => setGuideCollapsed(v => !v)} />

      {/* ── 今日历史（24h，来自 localStorage）── */}
      {!result && localHistory.length > 0 && (
        <div style={{
          background: '#0d0d22', border: '1px solid #2a2a5a',
          borderRadius: '10px', padding: '14px 18px', marginBottom: '20px',
        }}>
          <div style={{ color: '#8888aa', fontSize: '0.8rem', marginBottom: '10px', letterSpacing: '0.08em' }}>
            今日记录
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {localHistory.map((r, i) => (
              <div key={i} style={{
                display: 'flex', gap: '10px', alignItems: 'flex-start',
                padding: '8px 10px', background: '#12122a',
                borderRadius: '8px', fontSize: '0.82rem',
              }}>
                <span style={{ color: '#c9a84c', flexShrink: 0 }}>
                  {r.planet} · {r.sign} · {r.house}宫
                </span>
                <span style={{ color: '#6666aa', flexShrink: 0 }}>
                  {new Date(r.ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span style={{ color: '#8888aa', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.question}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Step 1：输入问题 ── */}
      {!result && (
        <div style={{
          background: '#0d0d22', border: '1px solid #2a2a5a',
          borderRadius: '12px', padding: isMobile ? '16px' : '24px',
        }}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', color: '#8888aa', fontSize: isMobile ? '0.8rem' : '0.85rem', marginBottom: '8px' }}>
              在心中想好一个具体问题，然后写下来：
            </label>
            <textarea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="例如：我该不该接受这份工作邀请？"
              rows={isMobile ? 2 : 3}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: '#12122a', border: '1px solid #3a3a6a',
                borderRadius: '8px', color: '#c9c9e0',
                padding: isMobile ? '8px 12px' : '10px 14px',
                fontSize: isMobile ? '0.9rem' : '0.95rem',
                resize: 'vertical', outline: 'none',
              }}
            />
          </div>

          <div style={{ marginBottom: isMobile ? '14px' : '20px' }}>
            <div style={{ color: '#8888aa', fontSize: '0.82rem', marginBottom: '8px' }}>
              选择问题类别：
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: isMobile ? '6px' : '8px' }}>
              {CATEGORIES.map(c => (
                <button
                  key={c.key}
                  onClick={() => setCategory(c.key)}
                  style={{
                    padding: isMobile ? '7px 12px' : '6px 14px',
                    borderRadius: '20px', cursor: 'pointer',
                    fontSize: isMobile ? '0.8rem' : '0.85rem',
                    fontWeight: category === c.key ? 600 : 400,
                    background: category === c.key ? '#1a1a3a' : 'transparent',
                    border: `1px solid ${category === c.key ? '#c9a84c' : '#3a3a6a'}`,
                    color: category === c.key ? '#c9a84c' : '#8888aa',
                    transition: 'all 0.15s', minHeight: '36px',
                  }}
                >
                  {c.icon} {c.key}
                </button>
              ))}
            </div>
          </div>

          {/* 可选：结合本命盘 */}
          {charts.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <div style={{ color: '#8888aa', fontSize: '0.82rem', marginBottom: '8px' }}>
                结合本命盘解读（可选）：
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                <button
                  onClick={() => setSelectedChartId(null)}
                  style={{
                    padding: '6px 14px', borderRadius: '20px', cursor: 'pointer',
                    fontSize: '0.82rem',
                    background: selectedChartId === null ? '#1a1a3a' : 'transparent',
                    border: `1px solid ${selectedChartId === null ? '#c9a84c' : '#3a3a6a'}`,
                    color: selectedChartId === null ? '#c9a84c' : '#8888aa',
                  }}
                >
                  不使用
                </button>
                {charts.map(c => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedChartId(c.id)}
                    style={{
                      padding: '6px 14px', borderRadius: '20px', cursor: 'pointer',
                      fontSize: '0.82rem',
                      background: selectedChartId === c.id ? '#1a1a3a' : 'transparent',
                      border: `1px solid ${selectedChartId === c.id ? '#88aaff' : '#3a3a6a'}`,
                      color: selectedChartId === c.id ? '#88aaff' : '#8888aa',
                    }}
                  >
                    {c.label || c.name}
                  </button>
                ))}
              </div>
              {selectedChartId && (
                <div style={{ color: '#5a5a8a', fontSize: '0.78rem', marginTop: '6px' }}>
                  ✦ 解读将结合该星盘的上升、日月及与骰子相关的宫位信息
                </div>
              )}
            </div>
          )}

          {error && <div style={{ color: '#ff8866', fontSize: '0.88rem', marginBottom: '12px' }}>{error}</div>}

          <button
            onClick={handleRoll}
            disabled={loading}
            style={{
              width: '100%', padding: isMobile ? '14px' : '12px',
              background: loading ? '#2a2a4a' : '#c9a84c',
              color: loading ? '#8888aa' : '#0a0a1a',
              border: 'none', borderRadius: '8px',
              fontWeight: 700, fontSize: isMobile ? '1rem' : '1rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.05em', minHeight: '48px',
            }}
          >
            {loading ? '正在解读…' : '🎲 掷骰子'}
          </button>
        </div>
      )}

      {/* ── Step 2：结果展示 ── */}
      {result && (
        <div ref={resultRef}>
          {/* 问题回显 */}
          <div style={{
            background: '#12122a', borderRadius: '8px', padding: '10px 16px',
            marginBottom: '20px', color: '#8888aa', fontSize: '0.88rem',
            borderLeft: '3px solid #c9a84c',
          }}>
            <span style={{ color: '#c9a84c' }}>问题：</span>{question}
            <span style={{ marginLeft: '12px', color: '#5a5a8a' }}>（{category}）</span>
          </div>

          {/* 三骰展示 */}
          <div style={{ display: 'flex', gap: isMobile ? '8px' : '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
            <DiceCard dice={result.dice_display.planet} label="能量" color="#c9a84c" />
            <DiceCard dice={result.dice_display.sign}   label="方式" color="#88aaff" />
            <DiceCard dice={result.dice_display.house}  label="领域" color="#88cc88" />
          </div>

          {/* 核心句 */}
          <div style={{
            background: '#0d0d22', border: '1px solid #2a2a5a',
            borderRadius: '8px', padding: '12px 16px', marginBottom: '16px',
            color: '#c9c9e0', fontSize: '0.9rem', lineHeight: 1.7,
            borderLeft: '3px solid #c9a84c',
          }}>
            {result.core_sentence}
          </div>

          {/* AI 解读 */}
          <div style={{
            background: '#0d0d22', border: '1px solid #2a2a5a',
            borderRadius: '10px', padding: '18px 20px', marginBottom: '16px',
          }}>
            <div style={{ color: '#8888aa', fontSize: '0.8rem', marginBottom: '10px', letterSpacing: '0.08em' }}>
              AI 解读
            </div>
            <div style={{ lineHeight: 1.85, fontSize: '0.95rem', whiteSpace: 'pre-wrap' }}>
              {result.interpretation}
            </div>
          </div>

          <SourcesSection sources={result.sources} />

          {/* 补充能量结果 */}
          {supplementResult && (
            <div style={{
              background: '#0d1a0d', border: '1px solid #2a4a2a',
              borderRadius: '10px', padding: '16px 20px', marginBottom: '16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <span style={{ fontSize: '1.4rem' }}>{PLANET_ICONS[supplementResult.supplement_planet.key] || '🎲'}</span>
                <div>
                  <span style={{ color: '#88cc88', fontWeight: 600 }}>
                    辅助能量：{supplementResult.supplement_planet.name}
                  </span>
                  <span style={{ color: '#5a5a8a', fontSize: '0.82rem', marginLeft: '8px' }}>
                    {supplementResult.supplement_planet.core}
                  </span>
                </div>
              </div>
              <div style={{ lineHeight: 1.8, fontSize: '0.92rem', whiteSpace: 'pre-wrap', color: '#b0b0d0' }}>
                {supplementResult.interpretation}
              </div>
              <SourcesSection sources={supplementResult.sources} />
            </div>
          )}

          {/* 追问结果 */}
          {rerollResult && (
            <div style={{
              background: '#0d0d22', border: '1px solid #3a3a7a',
              borderRadius: '10px', padding: '16px 20px', marginBottom: '16px',
            }}>
              <div style={{ color: '#88aaff', fontSize: '0.82rem', marginBottom: '12px', fontWeight: 600 }}>
                追问解读
              </div>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
                <DiceCard dice={rerollResult.dice_display.planet} label="新能量" color="#c9a84c" />
                <DiceCard dice={rerollResult.dice_display.sign}   label="方式（沿用）" color="#88aaff" inherited />
                <DiceCard dice={rerollResult.dice_display.house}  label="新领域" color="#88cc88" />
              </div>
              <div style={{
                borderLeft: '3px solid #88aaff',
                paddingLeft: '12px', marginBottom: '12px',
                color: '#c9c9e0', fontSize: '0.88rem',
              }}>
                {rerollResult.core_sentence}
              </div>
              <div style={{ lineHeight: 1.85, fontSize: '0.92rem', whiteSpace: 'pre-wrap' }}>
                {rerollResult.interpretation}
              </div>
              <SourcesSection sources={rerollResult.sources} />
            </div>
          )}

          {/* 再掷操作区 */}
          {!rerollMode && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
              <button
                onClick={() => setRerollMode('followup')}
                disabled={rerolling}
                style={{
                  padding: isMobile ? '10px 14px' : '9px 18px',
                  flex: isMobile ? '1 1 auto' : 'none',
                  borderRadius: '8px', cursor: 'pointer',
                  background: '#12122a', border: '1px solid #88aaff',
                  color: '#88aaff', fontSize: isMobile ? '0.82rem' : '0.88rem', fontWeight: 600,
                  minHeight: '42px',
                }}
              >
                🔍 追问
              </button>
              <button
                onClick={() => setRerollMode('supplement')}
                disabled={rerolling}
                style={{
                  padding: isMobile ? '10px 14px' : '9px 18px',
                  flex: isMobile ? '1 1 auto' : 'none',
                  borderRadius: '8px', cursor: 'pointer',
                  background: '#12122a', border: '1px solid #88cc88',
                  color: '#88cc88', fontSize: isMobile ? '0.82rem' : '0.88rem', fontWeight: 600,
                  minHeight: '42px',
                }}
              >
                ✨ 补充能量
              </button>
              <button
                onClick={() => { setResult(null); setRerollResult(null); setSupplementResult(null); setGuideCollapsed(false) }}
                style={{
                  padding: isMobile ? '10px 14px' : '9px 18px',
                  flex: isMobile ? '1 1 100%' : 'none',
                  borderRadius: '8px', cursor: 'pointer',
                  background: 'transparent', border: '1px solid #3a3a6a',
                  color: '#8888aa', fontSize: isMobile ? '0.82rem' : '0.88rem',
                  minHeight: '42px',
                  marginLeft: isMobile ? 0 : 'auto',
                }}
              >
                🔄 新问题
              </button>
            </div>
          )}

          {/* 追问输入框 */}
          {rerollMode === 'followup' && (
            <div style={{
              background: '#0d0d22', border: '1px solid #3a3a7a',
              borderRadius: '10px', padding: '16px 20px', marginBottom: '12px',
            }}>
              <div style={{ color: '#88aaff', fontSize: '0.85rem', marginBottom: '10px' }}>
                追问方向（保留原问题背景，掷出新的行星+宫位）：
              </div>
              <textarea
                value={followupQ}
                onChange={e => setFollowupQ(e.target.value)}
                placeholder="例如：具体来说，合作方的真实意图如何判断？"
                rows={2}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: '#12122a', border: '1px solid #3a3a7a',
                  borderRadius: '8px', color: '#c9c9e0',
                  padding: '8px 12px', fontSize: '0.9rem',
                  resize: 'vertical', outline: 'none',
                  marginBottom: '12px',
                }}
              />
              {error && <div style={{ color: '#ff8866', fontSize: '0.85rem', marginBottom: '8px' }}>{error}</div>}
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={handleReroll}
                  disabled={rerolling}
                  style={{
                    padding: '8px 20px', background: rerolling ? '#2a2a4a' : '#88aaff',
                    color: rerolling ? '#8888aa' : '#0a0a1a',
                    border: 'none', borderRadius: '8px',
                    fontWeight: 600, cursor: rerolling ? 'not-allowed' : 'pointer',
                  }}
                >
                  {rerolling ? '解读中…' : '🎲 掷出追问'}
                </button>
                <button
                  onClick={() => { setRerollMode(null); setFollowupQ(''); setError('') }}
                  style={{
                    padding: '8px 16px', background: 'transparent',
                    border: '1px solid #3a3a6a', color: '#8888aa',
                    borderRadius: '8px', cursor: 'pointer',
                  }}
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {/* 补充能量确认 */}
          {rerollMode === 'supplement' && (
            <div style={{
              background: '#0d1a0d', border: '1px solid #2a4a2a',
              borderRadius: '10px', padding: '14px 20px', marginBottom: '12px',
              display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap',
            }}>
              <span style={{ color: '#88cc88', fontSize: '0.88rem' }}>
                将掷出一颗行星骰作为辅助能量，为当前解读补充视角
              </span>
              <button
                onClick={handleReroll}
                disabled={rerolling}
                style={{
                  padding: '7px 18px', background: rerolling ? '#2a2a4a' : '#88cc88',
                  color: rerolling ? '#8888aa' : '#0a0a1a',
                  border: 'none', borderRadius: '8px',
                  fontWeight: 600, cursor: rerolling ? 'not-allowed' : 'pointer',
                }}
              >
                {rerolling ? '解读中…' : '✨ 确认掷出'}
              </button>
              <button
                onClick={() => setRerollMode(null)}
                style={{
                  padding: '7px 14px', background: 'transparent',
                  border: '1px solid #3a3a6a', color: '#8888aa',
                  borderRadius: '8px', cursor: 'pointer',
                }}
              >
                取消
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
