/** Converts camelCase filenames to readable book titles, e.g. "modernAstrology" → "Modern Astrology" */
function cleanSourceName(raw) {
  const base = raw.replace('[EN]', '').split('(')[0].split('/').pop().replace(/\.\w+$/, '').trim()
  return base
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .trim()
}

export function SourcesSection({ sources }) {
  if (!sources?.length) return null
  const cited = sources.filter(s => s.cited)
  return (
    <div style={{
      marginTop: '16px',
      padding: '12px 14px',
      backgroundColor: '#0a0a1e',
      border: '1px solid #2a2a4a',
      borderRadius: '8px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <span style={{ color: '#6666aa', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          RAG 检索来源
        </span>
        <span style={{ color: '#3a3a6a', fontSize: '0.7rem' }}>
          ✓ 已引用 · ○ 未引用
        </span>
        <span style={{ marginLeft: 'auto', color: cited.length ? '#66cc88' : '#444466', fontSize: '0.72rem' }}>
          {cited.length}/{sources.length} 条引用
        </span>
      </div>
      {sources.map((s, i) => {
        const name = cleanSourceName(s.source)
        return (
          <div key={i} style={{ marginBottom: '8px' }}>
            {/* Header row: cited status + book name + score */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              gap: '8px', fontSize: '0.75rem',
            }}>
              <span style={{ color: s.cited ? '#8888cc' : '#444466' }}>
                <span style={{ marginRight: '5px', color: s.cited ? '#66cc88' : '#333355' }}>
                  {s.cited ? '✓' : '○'}
                </span>
                {name}
              </span>
              <span style={{ color: s.score >= 0.5 ? '#c9a84c' : '#444466', flexShrink: 0 }}>
                {s.score.toFixed(3)}
              </span>
            </div>
            {/* Excerpt: prefer Chinese summary, fall back to truncated English */}
            {(s.summary_zh || s.text) && (
              <div style={{
                marginTop: '3px', marginLeft: '16px',
                color: '#555577', fontSize: '0.72rem', lineHeight: 1.5,
                borderLeft: `2px solid ${s.cited ? '#3a3a7a' : '#222240'}`,
                paddingLeft: '8px',
              }}>
                {s.summary_zh || (s.text.length > 120 ? s.text.slice(0, 120) + '…' : s.text)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/**
 * Reusable AI interpretation panel.
 *
 * Props:
 *   onGenerate  – called when button is clicked
 *   loading     – show spinner / disable button
 *   result      – object from useInterpret: { answer, sources? }
 *   error       – error string from useInterpret
 *   label       – button label (default: "生成 AI 解读")
 *   disabled    – disable button regardless of loading
 *   children    – optional: replace the default answer text display
 */
export default function AIPanel({
  onGenerate,
  loading,
  result,
  error,
  label = '生成 AI 解读',
  disabled = false,
  children,
}) {
  return (
    <div style={{ marginTop: '24px' }}>
      <button
        onClick={onGenerate}
        disabled={loading || disabled}
        style={{
          padding: '8px 20px',
          borderRadius: '8px',
          cursor: loading || disabled ? 'not-allowed' : 'pointer',
          backgroundColor: '#2a2a5a',
          border: '1px solid #4a4a8a',
          color: loading || disabled ? '#5a5a8a' : '#c9a84c',
          fontSize: '0.85rem',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {loading ? '生成中…' : label}
      </button>

      {error && (
        <div style={{ color: '#cc4444', fontSize: '0.82rem', marginTop: '8px' }}>
          {error}
        </div>
      )}

      {result && (
        <>
          {/* Answer text */}
          <div style={{ marginTop: '16px', color: '#ccc', lineHeight: 1.7, fontSize: '0.88rem' }}>
            {children || (
              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
                {result.answer}
              </pre>
            )}
          </div>

          {/* Model label */}
          {result.model_used && (
            <div style={{ marginTop: '6px', textAlign: 'right' }}>
              <span style={{ fontSize: '0.65rem', color: result.model_used === 'cached' ? '#6a8a6a' : '#7a6aaa', background: '#0f0f1e', border: '1px solid #2a2a4a', borderRadius: '10px', padding: '2px 7px' }}>
                {result.model_used === 'cached' ? '缓存' : result.model_used.replace('gemini-', '')}
              </span>
            </div>
          )}

          {/* Separate citations section */}
          <SourcesSection sources={result.sources} />
        </>
      )}
    </div>
  )
}
