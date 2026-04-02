import { useEffect, useRef, useState } from 'react'
import { getTagExplanation } from '../utils/tagExplanations'

/**
 * 可点击的本命盘标签，点击后弹出解释气泡。
 *
 * Props:
 *   tag        - 标签文本
 *   isOpen     - 是否展开（由父组件控制，保证同时只有一个展开）
 *   onToggle   - 点击标签时调用
 *   onClose    - 关闭气泡时调用
 *   onAskAI    - 点击"问 AI"按钮时调用
 */
export default function TagTooltip({ tag, isOpen, onToggle, onClose, onAskAI, chartData = null }) {
  const wrapperRef = useRef(null)
  const [popupPos, setPopupPos] = useState({ left: 0, top: 0, width: 300 })
  const info = getTagExplanation(tag, chartData)
  // 标签显示时去掉括号内容（行星名仅用于描述生成），保持标签简洁
  const displayTag = tag.replace(/（[^）]+）$/, '')

  // 打开时计算 fixed 定位坐标，确保气泡在视口内
  useEffect(() => {
    if (!isOpen || !wrapperRef.current) return
    const rect = wrapperRef.current.getBoundingClientRect()
    const MARGIN = 12
    const popupW = Math.min(300, window.innerWidth - MARGIN * 2)
    let left = rect.left
    if (left + popupW > window.innerWidth - MARGIN) {
      left = window.innerWidth - popupW - MARGIN
    }
    if (left < MARGIN) left = MARGIN
    setPopupPos({ left, top: rect.bottom + 8, width: popupW })
  }, [isOpen])

  // 点击外部关闭
  useEffect(() => {
    if (!isOpen) return
    function handleMouseDown(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [isOpen, onClose])

  // ESC 关闭
  useEffect(() => {
    if (!isOpen) return
    function handleKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  return (
    <span ref={wrapperRef} style={{ display: 'inline-block' }}>
      {/* 标签本体 */}
      <span
        onClick={onToggle}
        style={{
          display: 'inline-block',
          padding: '3px 10px',
          borderRadius: '20px',
          fontSize: '0.75rem',
          fontWeight: 600,
          background: isOpen ? '#2a2050' : '#1e1a38',
          border: `1px solid ${isOpen ? '#c9a84c' : '#7a6aaa'}`,
          color: '#c9a84c',
          cursor: 'pointer',
          transition: 'border-color 0.15s, background 0.15s, box-shadow 0.15s',
          boxShadow: isOpen ? '0 0 8px rgba(201,168,76,0.25)' : 'none',
          userSelect: 'none',
        }}
        onMouseEnter={e => {
          if (!isOpen) {
            e.currentTarget.style.borderColor = '#9a8acc'
            e.currentTarget.style.boxShadow = '0 0 6px rgba(154,138,204,0.3)'
          }
        }}
        onMouseLeave={e => {
          if (!isOpen) {
            e.currentTarget.style.borderColor = '#7a6aaa'
            e.currentTarget.style.boxShadow = 'none'
          }
        }}
      >
        {displayTag}
      </span>

      {/* 气泡：position:fixed 相对视口定位，避免移动端溢出 */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            top: popupPos.top,
            left: popupPos.left,
            width: popupPos.width,
            zIndex: 9999,
            background: '#1d1640',
            border: '1px solid #7a6aaa',
            borderRadius: '10px',
            padding: '14px 16px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}
        >
          {/* 小箭头 */}
          <div style={{
            position: 'absolute',
            top: '-7px',
            left: '16px',
            width: '12px',
            height: '12px',
            background: '#1d1640',
            border: '1px solid #7a6aaa',
            borderRight: 'none',
            borderBottom: 'none',
            transform: 'rotate(45deg)',
          }} />

          {/* 标题行 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: '#c9a84c', fontWeight: 700, fontSize: '0.8rem' }}>✦ {displayTag}</span>
            <span
              onClick={onClose}
              style={{ color: '#5a4a7a', fontSize: '1.1rem', lineHeight: 1, cursor: 'pointer', padding: '0 2px' }}
            >×</span>
          </div>

          {/* 解释文字 */}
          {info ? (
            <p style={{ color: '#c8b8e8', fontSize: '0.8rem', lineHeight: 1.65, margin: '0 0 12px 0' }}>
              {info.explanation}
            </p>
          ) : (
            <p style={{ color: '#5a5a8a', fontSize: '0.78rem', margin: '0 0 10px 0' }}>
              点击下方按钮，让 AI 为你解读这个配置的含义。
            </p>
          )}

          {/* Ask AI 按钮 */}
          <button
            onClick={() => { onClose(); onAskAI() }}
            style={{
              width: '100%',
              background: 'linear-gradient(135deg,#3a2a6a,#4a2a5a)',
              border: '1px solid #7a5aaa',
              color: '#d0b0ff',
              fontSize: '0.78rem',
              padding: '6px 12px',
              borderRadius: '16px',
              cursor: 'pointer',
            }}
          >
            ✨ 问 AI 深入解读此配置
          </button>
        </div>
      )}
    </span>
  )
}
