const PLANET_SYMBOLS = {
  sun: '☉', moon: '☽', mercury: '☿', venus: '♀', mars: '♂',
  jupiter: '♃', saturn: '♄', uranus: '♅', neptune: '♆', pluto: '♇',
  mean_node: '☊', true_node: '☊', chiron: '⚷', mean_lilith: '⚸',
}

const SIGN_SYMBOLS = {
  'Áries': '♈', 'Touro': '♉', 'Gêmeos': '♊', 'Câncer': '♋',
  'Leão': '♌', 'Virgem': '♍', 'Escorpião': '♏',
  'Sagitário': '♐', 'Capricórnio': '♑', 'Aquário': '♒', 'Peixes': '♓',
  'Aries': '♈', 'Taurus': '♉', 'Gemini': '♊', 'Cancer': '♋',
  'Leo': '♌', 'Virgo': '♍', 'Libra': '♎', 'Scorpio': '♏',
  'Sagittarius': '♐', 'Capricorn': '♑', 'Aquarius': '♒', 'Pisces': '♓',
  '白羊座': '♈', '金牛座': '♉', '双子座': '♊', '巨蟹座': '♋',
  '狮子座': '♌', '处女座': '♍', '天秤座': '♎', '天蝎座': '♏',
  '射手座': '♐', '摩羯座': '♑', '水瓶座': '♒', '双鱼座': '♓',
  '牡羊座': '♈', '牡牛座': '♉', '蟹座': '♋',
  '獅子座': '♌', '乙女座': '♍', '蠍座': '♏', '山羊座': '♑', '魚座': '♓',
}

const UI_LABELS = {
  zh: { title: '✦ 行星', planet: '行星', sign: '星座', degree: '度数', house: '宫位', retro: '逆行', houseCell: n => `第${n}宫` },
  ja: { title: '✦ 惑星', planet: '惑星', sign: '星座', degree: '度数', house: 'ハウス', retro: '逆行', houseCell: n => `第${n}H` },
  en: { title: '✦ PLANETS', planet: 'Planet', sign: 'Sign', degree: 'Degree', house: 'House', retro: 'Rx', houseCell: n => `House ${n}` },
  pt: { title: '✦ PLANETAS', planet: 'Planeta', sign: 'Signo', degree: 'Grau', house: 'Casa', retro: 'Ret.', houseCell: n => `Casa ${n}` },
  es: { title: '✦ PLANETAS', planet: 'Planeta', sign: 'Signo', degree: 'Grado', house: 'Casa', retro: 'Ret.', houseCell: n => `Casa ${n}` },
  fr: { title: '✦ PLANÈTES', planet: 'Planète', sign: 'Signe', degree: 'Degré', house: 'Maison', retro: 'Rét.', houseCell: n => `Maison ${n}` },
  de: { title: '✦ PLANETEN', planet: 'Planet', sign: 'Zeichen', degree: 'Grad', house: 'Haus', retro: 'Ret.', houseCell: n => `Haus ${n}` },
}

function formatDegree(longitude) {
  const deg = Math.floor(longitude % 30)
  const min = Math.floor((longitude % 1) * 60)
  return `${deg}°${String(min).padStart(2, '0')}'`
}

export default function PlanetTable({ planets, language = 'zh' }) {
  if (!planets) return null

  const L = UI_LABELS[language] || UI_LABELS['en']
  const rows = Object.entries(planets)

  return (
    <div className="rounded-xl overflow-hidden"
      style={{ backgroundColor: '#12122a', border: '1px solid #2a2a5a' }}
    >
      <h3 className="text-center text-sm font-semibold tracking-widest py-3 border-b"
        style={{ color: '#c9a84c', borderColor: '#2a2a5a' }}
      >
        {L.title}
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid #2a2a5a', color: '#8888aa' }}>
              <th className="text-left px-4 py-2">{L.planet}</th>
              <th className="text-left px-4 py-2">{L.sign}</th>
              <th className="text-left px-4 py-2">{L.degree}</th>
              <th className="text-left px-4 py-2">{L.house}</th>
              <th className="text-left px-4 py-2">{L.retro}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, planet]) => (
              <tr key={key}
                className="transition-colors"
                style={{ borderBottom: '1px solid #1a1a3a' }}
                onMouseEnter={e => e.currentTarget.style.backgroundColor = '#1a1a35'}
                onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <td className="px-4 py-2 font-medium">
                  <span className="mr-2 text-base" style={{ color: '#c9a84c' }}>
                    {PLANET_SYMBOLS[key] || '·'}
                  </span>
                  {planet.name}
                </td>
                <td className="px-4 py-2">
                  <span className="mr-1">{SIGN_SYMBOLS[planet.sign] || ''}</span>
                  {planet.sign}
                </td>
                <td className="px-4 py-2" style={{ color: '#8888aa', fontFamily: 'monospace' }}>
                  {formatDegree(planet.longitude)}
                </td>
                <td className="px-4 py-2">
                  <span className="px-2 py-0.5 rounded text-xs"
                    style={{ backgroundColor: '#1e1e40', color: '#a07de0' }}
                  >
                    {L.houseCell(planet.house)}
                  </span>
                </td>
                <td className="px-4 py-2">
                  {planet.retrograde && (
                    <span style={{ color: '#ff8888', fontSize: '0.75rem' }}>℞</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
