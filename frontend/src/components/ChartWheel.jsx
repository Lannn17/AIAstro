const CHART_TITLE = {
  zh: '✦ 星盘图',
  ja: '✦ 天球図',
  en: '✦ NATAL CHART',
  pt: '✦ MAPA ASTROLÓGICO',
  es: '✦ MAPA NATAL',
  fr: '✦ THÈME NATAL',
  de: '✦ GEBURTSHOROSKOP',
}

export default function ChartWheel({ svgContent, language = 'zh' }) {
  return (
    <div className="rounded-xl overflow-hidden p-4"
      style={{ backgroundColor: '#12122a', border: '1px solid #2a2a5a' }}
    >
      <h3 className="text-center text-sm font-semibold tracking-widest mb-4" style={{ color: '#c9a84c' }}>
        {CHART_TITLE[language] || CHART_TITLE['en']}
      </h3>
      <div
        className="mx-auto"
        style={{ maxWidth: '600px' }}
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />
    </div>
  )
}
