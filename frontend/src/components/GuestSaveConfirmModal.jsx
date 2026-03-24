export default function GuestSaveConfirmModal({ onConfirm, onCancel }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9000,
      backgroundColor: 'rgba(10,10,26,0.85)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '16px',
    }}>
      <div style={{
        backgroundColor: '#0d0d22',
        border: '1px solid #4a3a1a',
        borderRadius: '12px',
        padding: '28px 24px',
        width: '100%',
        maxWidth: '380px',
      }}>
        <div style={{ color: '#c9a84c', fontSize: '1.4rem', textAlign: 'center', marginBottom: '14px' }}>
          ⚠
        </div>
        <div style={{ color: '#e8e0f0', fontSize: '0.95rem', fontWeight: 600, textAlign: 'center', marginBottom: '12px' }}>
          提交前请确认
        </div>
        <div style={{ color: '#8888aa', fontSize: '0.85rem', lineHeight: 1.75, marginBottom: '22px' }}>
          您正以<span style={{ color: '#c9a84c' }}>访客身份</span>使用本应用。
          提交后，您的星盘数据将进入<strong style={{ color: '#e8e0f0' }}>待审核队列</strong>，
          由所有者确认后才会正式保存。
          <br /><br />
          审核通过前，数据不会出现在任何星盘列表中。
          如需保存并自行管理，请先登录。
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1, padding: '9px',
              backgroundColor: 'transparent',
              border: '1px solid #3a3a6a',
              borderRadius: '8px', color: '#8888aa',
              fontSize: '0.9rem', cursor: 'pointer',
            }}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            style={{
              flex: 1, padding: '9px',
              backgroundColor: '#4a3a1a',
              border: '1px solid #c9a84c',
              borderRadius: '8px', color: '#c9a84c',
              fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer',
            }}
          >
            提交审核
          </button>
        </div>
      </div>
    </div>
  )
}
