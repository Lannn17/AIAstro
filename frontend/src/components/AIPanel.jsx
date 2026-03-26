/**
 * Reusable AI interpretation panel.
 * Renders a trigger button, an error message, and the result text.
 *
 * Props:
 *   onGenerate  – called when button is clicked
 *   loading     – show spinner / disable button
 *   result      – object with an `answer` string field (from useInterpret)
 *   error       – error string (from useInterpret)
 *   label       – button label (default: "生成 AI 解读")
 *   disabled    – disable button regardless of loading (e.g. inputs not ready)
 *   children    – optional: replace the default <pre> result display
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
        children
          ? <div style={{ marginTop: '16px' }}>{children}</div>
          : (
            <div style={{ marginTop: '16px', color: '#ccc', lineHeight: 1.7, fontSize: '0.88rem' }}>
              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
                {result.answer}
              </pre>
            </div>
          )
      )}
    </div>
  )
}
