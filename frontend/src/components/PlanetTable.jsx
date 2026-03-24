const PLANET_SYMBOLS = {
  sun: '☉', moon: '☽', mercury: '☿', venus: '♀', mars: '♂',
  jupiter: '♃', saturn: '♄', uranus: '♅', neptune: '♆', pluto: '♇',
  mean_node: '☊', true_node: '☊', mean_south_node: '☋', true_south_node: '☋', chiron: '⚷', mean_lilith: '⚸',
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

// Fallback translations for planets stored untranslated in old saved charts
const PLANET_NAMES = {
  zh: {
    Sun: '太阳', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星',
    Jupiter: '木星', Saturn: '土星', Uranus: '天王星', Neptune: '海王星', Pluto: '冥王星',
    Mean_Node: '北交点', True_Node: '北交点', Mean_South_Node: '南交点', True_South_Node: '南交点',
    Chiron: '凯龙星', Lilith: '黑月莉莉丝', Mean_Lilith: '黑月莉莉丝',
    Ascendant: '上升点', Midheaven: '天顶',
  },
  ja: {
    Sun: '太陽', Moon: '月', Mercury: '水星', Venus: '金星', Mars: '火星',
    Jupiter: '木星', Saturn: '土星', Uranus: '天王星', Neptune: '海王星', Pluto: '冥王星',
    Mean_Node: '平均ノースノード', True_Node: 'ノースノード',
    Mean_South_Node: '平均サウスノード', True_South_Node: 'サウスノード',
    Chiron: 'カイロン', Lilith: 'リリス', Mean_Lilith: 'リリス',
    Ascendant: 'アセンダント', Midheaven: 'MC',
  },
}

// Fallback translations for signs stored untranslated in old saved charts (keyed by English sign_original)
const SIGN_NAMES = {
  zh: {
    Aries: '白羊座', Taurus: '金牛座', Gemini: '双子座', Cancer: '巨蟹座',
    Leo: '狮子座', Virgo: '处女座', Libra: '天秤座', Scorpio: '天蝎座',
    Sagittarius: '射手座', Capricorn: '摩羯座', Aquarius: '水瓶座', Pisces: '双鱼座',
  },
  ja: {
    Aries: '牡羊座', Taurus: '牡牛座', Gemini: '双子座', Cancer: '蟹座',
    Leo: '獅子座', Virgo: '乙女座', Libra: '天秤座', Scorpio: '蠍座',
    Sagittarius: '射手座', Capricorn: '山羊座', Aquarius: '水瓶座', Pisces: '魚座',
  },
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
  const SKIP_PLANETS = new Set(['true_node', 'true_lilith', 'true_south_node'])
  const rows = Object.entries(planets).filter(([k]) => !SKIP_PLANETS.has(k))

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
                  {PLANET_NAMES[language]?.[planet.name_original] || planet.name}
                </td>
                <td className="px-4 py-2">
                  {(() => {
                    const signDisplay = SIGN_NAMES[language]?.[planet.sign_original] || planet.sign
                    return <>
                      <span className="mr-1">{SIGN_SYMBOLS[signDisplay] || ''}</span>
                      {signDisplay}
                    </>
                  })()}
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
