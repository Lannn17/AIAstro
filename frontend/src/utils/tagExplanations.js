// 12宫象征
const HOUSE_MEANINGS = {
  1: '自我、外貌与人生态度',
  2: '金钱、财产与个人价值',
  3: '沟通、学习、短途旅行与兄弟姐妹',
  4: '家庭、根源与内心安全感',
  5: '创意、恋爱、娱乐与子女',
  6: '日常工作、健康与服务',
  7: '伴侣关系、合作与公开的对立',
  8: '转化、共有资源、性与死亡议题',
  9: '哲学、高等教育、长途旅行与信仰',
  10: '事业、社会地位与公众形象',
  11: '友谊、团体、社会理想与未来愿景',
  12: '隐藏领域、心灵深处、孤独与灵性',
}

// 星座象征
const SIGN_MEANINGS = {
  白羊: '冲劲、主动、直接、开拓',
  金牛: '稳定、享受、耐心、务实',
  双子: '灵活、好奇、善变、沟通',
  巨蟹: '情感、直觉、保护、家庭',
  狮子: '自信、创意、表现欲、领导力',
  处女: '分析、服务、完美主义、细节',
  天秤: '平衡、美感、合作、和谐',
  天蝎: '深度、转化、洞察、强烈',
  射手: '自由、乐观、探索、哲学',
  摩羯: '务实、纪律、雄心、责任',
  水瓶: '独立、革新、人道、前卫',
  双鱼: '直觉、同理心、梦想、灵性',
}

// 元素气质
const ELEMENT_MEANINGS = {
  火: '充满热情与行动力，倾向主动出击，有强烈的表现欲与领导本能',
  土: '重视实际与稳定，脚踏实地，擅长将想法落实为具体成果',
  风: '思维活跃，善于沟通与分析，对新想法和社交互动充满兴趣',
  水: '情感丰富，直觉敏锐，擅长感知他人情绪，心灵世界深厚',
}

// 模式特征
const MODE_MEANINGS = {
  本始: '主动发起者，善于开创新局面，但有时难以持续到底',
  固定: '意志坚定，专注持久，一旦投入便全力以赴，不易改变方向',
  变动: '灵活适应，善于整合与过渡，能在变化中找到出路',
}

// 行星核心领域
const PLANET_DOMAINS = {
  太阳: '自我认同与核心意志',
  月亮: '情感与本能反应',
  水星: '思维与沟通方式',
  金星: '审美、价值观与人际关系',
  火星: '行动力与欲望驱动',
  木星: '信念、扩张与成长运势',
  土星: '责任、限制与长期积累',
  天王星: '变革与突破冲动',
  海王星: '梦想、直觉与灵性追求',
  冥王星: '深层转化与潜在力量',
  凯龙: '核心伤痛与疗愈智慧',
  北交点: '今生成长方向',
  南交点: '前世积累的习性',
}

// 核心行星 key（与后端 _CORE_PLANETS 一致）
const CORE_PLANET_KEYS = new Set(['sun', 'moon', 'mercury', 'venus', 'mars',
  'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'])


/**
 * 将 "太阳·水星·金星" 格式转为带领域注释的短句。
 * 例如 → "太阳（自我认同）、水星（思维沟通）与金星（审美关系）"
 */
function _describePlanets(planetStr) {
  const list = planetStr.split(/[·、,，]/).map(s => s.trim()).filter(Boolean)
  const described = list.map(p => {
    const domain = PLANET_DOMAINS[p]
    return domain ? `${p}（${domain}）` : p
  })
  if (described.length === 0) return planetStr
  if (described.length === 1) return described[0]
  if (described.length === 2) return described.join('与')
  return described.slice(0, -1).join('、') + '与' + described[described.length - 1]
}

/**
 * 从 chartData 中找出在指定星座（不含"座"后缀）的核心行星名。
 * @returns {string[]|null} 行星名列表，不足3颗返回 null
 */
function _getPlanetsInSign(chartData, signZh) {
  if (!chartData?.planets) return null
  const result = []
  for (const [key, p] of Object.entries(chartData.planets)) {
    if (!CORE_PLANET_KEYS.has(key)) continue
    // p.sign 为中文含座（如"天蝎座"），去尾与 signZh 比较
    const pSign = (p.sign || '').replace(/座$/, '')
    if (pSign === signZh) result.push(p.name || key)
  }
  return result.length >= 3 ? result : null
}

/**
 * 从 chartData 中找出在指定宫位的核心行星名。
 * @returns {string[]|null}
 */
function _getPlanetsInHouse(chartData, houseNum) {
  if (!chartData?.planets) return null
  const result = []
  for (const [key, p] of Object.entries(chartData.planets)) {
    if (!CORE_PLANET_KEYS.has(key)) continue
    if (Number(p.house) === houseNum) result.push(p.name || key)
  }
  return result.length >= 3 ? result : null
}

/**
 * 根据标签文本返回解释。
 * @param {string} tagText
 * @param {object|null} chartData  - 可选，传入当前星盘数据以获取具体行星名
 * @returns {{ title: string, explanation: string } | null}
 */
export function getTagExplanation(tagText, chartData = null) {
  // 群星 + 星座（新格式：含具体行星名，如"群星天蝎座（太阳·水星·金星）"）
  let m = tagText.match(/^群星(.+)座（([^颗\d][^）]*?)）$/)
  if (m) {
    const sign = m[1], planetStr = m[2]
    const meaning = SIGN_MEANINGS[sign] || '独特特质'
    const described = _describePlanets(planetStr)
    return {
      title: tagText,
      explanation: `${described}同聚${sign}座，${sign}座的特质（${meaning}）渗透这些生命领域的表达方式，使你在相关事务上带有鲜明的${sign}座气息与内驱力。`,
    }
  }

  // 群星 + 星座（旧格式：含数量，如"群星天蝎座（3颗核心行星）"，向后兼容）
  m = tagText.match(/^群星(.+)座（(\d+)颗核心行星）$/)
  if (m) {
    const sign = m[1], count = m[2]
    const meaning = SIGN_MEANINGS[sign] || '多元特质'
    const fromChart = _getPlanetsInSign(chartData, sign)
    if (fromChart) {
      const described = _describePlanets(fromChart.join('·'))
      return {
        title: tagText,
        explanation: `${described}同聚${sign}座，${sign}座的特质（${meaning}）渗透这些生命领域的表达方式，使你在相关事务上带有鲜明的${sign}座气息与内驱力。`,
      }
    }
    return {
      title: tagText,
      explanation: `${count} 颗核心行星集中在${sign}座，能量高度聚焦。${sign}座特质（${meaning}）在你的命盘中格外突出，使你在这一星座所代表的方向上有持续的驱动力。`,
    }
  }

  // 群星 + 宫位（AI 简写格式，如"群星3宫"）
  m = tagText.match(/^群星(\d+)宫$/)
  if (m) {
    const house = parseInt(m[1])
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    const fromChart = _getPlanetsInHouse(chartData, house)
    if (fromChart) {
      const described = _describePlanets(fromChart.join('·'))
      return {
        title: tagText,
        explanation: `${described}共聚第 ${house} 宫（${meaning}），这些行星的特质在${meaning}层面相互交织，使该领域成为你命盘的能量焦点。`,
      }
    }
    return {
      title: tagText,
      explanation: `多颗核心行星聚集于第 ${house} 宫（${meaning}），使这一生命领域成为你命盘的能量核心，你会在${meaning}方面投入格外多的精力与关注。`,
    }
  }

  // 群星 + 星座简写（AI 格式，如"群星天蝎座"无括号）
  m = tagText.match(/^群星(.+)座$/)
  if (m) {
    const sign = m[1]
    const meaning = SIGN_MEANINGS[sign] || '多元特质'
    const fromChart = _getPlanetsInSign(chartData, sign)
    if (fromChart) {
      const described = _describePlanets(fromChart.join('·'))
      return {
        title: tagText,
        explanation: `${described}同聚${sign}座，${sign}座的特质（${meaning}）渗透这些生命领域的表达方式，使你在相关事务上带有鲜明的${sign}座气息与内驱力。`,
      }
    }
    return {
      title: tagText,
      explanation: `多颗核心行星集中在${sign}座，${sign}座特质（${meaning}）在你的命盘中格外突出，使你在这一星座所代表的方向上有持续的驱动力。`,
    }
  }

  // 宫位强势（新格式：含具体行星名，如"第3宫强势（太阳·水星·金星）"）
  m = tagText.match(/^第(\d+)宫强势（([^颗\d][^）]*?)）$/)
  if (m) {
    const house = parseInt(m[1]), planetStr = m[2]
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    const described = _describePlanets(planetStr)
    return {
      title: tagText,
      explanation: `${described}共聚第 ${house} 宫（${meaning}），这些行星的特质在${meaning}层面相互交织，使该领域成为你人生中持续投入与成长的核心舞台。`,
    }
  }

  // 宫位强势（旧格式：含数量，如"第3宫强势（3颗核心行星）"，向后兼容）
  m = tagText.match(/^第(\d+)宫强势（(\d+)颗核心行星）$/)
  if (m) {
    const house = parseInt(m[1]), count = m[2]
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    const fromChart = _getPlanetsInHouse(chartData, house)
    if (fromChart) {
      const described = _describePlanets(fromChart.join('·'))
      return {
        title: tagText,
        explanation: `${described}共聚第 ${house} 宫（${meaning}），这些行星的特质在${meaning}层面相互交织，使该领域成为你人生中持续投入与成长的核心舞台。`,
      }
    }
    return {
      title: tagText,
      explanation: `${count} 颗核心行星聚集于第 ${house} 宫（${meaning}），使这一生命领域成为你性格与经历的核心舞台，你会在${meaning}方面持续积累深厚的人生经验。`,
    }
  }

  // 宫位强势（AI 简写，如"第3宫强势"）
  m = tagText.match(/^第(\d+)宫强势$/)
  if (m) {
    const house = parseInt(m[1])
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    const fromChart = _getPlanetsInHouse(chartData, house)
    if (fromChart) {
      const described = _describePlanets(fromChart.join('·'))
      return {
        title: tagText,
        explanation: `${described}共聚第 ${house} 宫（${meaning}），这些行星的特质在${meaning}层面相互交织，使该领域成为你人生中持续投入与成长的核心舞台。`,
      }
    }
    return {
      title: tagText,
      explanation: `多颗核心行星聚集于第 ${house} 宫（${meaning}），这一生命领域在你的命盘中占据重要地位，你会在${meaning}方面投入格外多的精力与关注。`,
    }
  }

  // 多元素行星（新格式含行星名：如"多火象行星（4颗：太阳·火星·木星·冥王星）"）
  m = tagText.match(/^多([火土风水])象行星（(\d+)颗：(.+)）$/)
  if (m) {
    const elem = m[1], count = m[2], planetStr = m[3]
    const meaning = ELEMENT_MEANINGS[elem] || ''
    const described = _describePlanets(planetStr)
    return {
      title: tagText,
      explanation: `命盘中有 ${count} 颗行星（${described}）位于${elem}象星座，${meaning}。这种元素主导使你的行事风格带有鲜明的${elem}象气质。`,
    }
  }
  // 多元素行星（旧格式/AI简写，向后兼容）
  m = tagText.match(/^多([火土风水])象行星[（(]?(\d+)?颗?[）)]?$/)
  if (m) {
    const elem = m[1], count = m[2] || '多'
    const meaning = ELEMENT_MEANINGS[elem] || ''
    return {
      title: tagText,
      explanation: `命盘中有 ${count} 颗行星位于${elem}象星座，${meaning}。这种元素主导使你的行事风格带有鲜明的${elem}象气质。`,
    }
  }

  // 多模式行星（新格式含行星名：如"多固定星（5颗：火星·土星·天王星·海王星·冥王星）"）
  m = tagText.match(/^多(本始|固定|变动)星（(\d+)颗：(.+)）$/)
  if (m) {
    const mode = m[1], count = m[2], planetStr = m[3]
    const meaning = MODE_MEANINGS[mode] || ''
    const described = _describePlanets(planetStr)
    return {
      title: tagText,
      explanation: `命盘中有 ${count} 颗行星（${described}）落在${mode}星座，${meaning}。这一模式主导着你面对生活变化时的基本姿态。`,
    }
  }
  // 多模式行星（旧格式/AI简写，向后兼容）
  m = tagText.match(/^多(本始|固定|变动)星[（(]?(\d+)?颗?[）)]?$/)
  if (m) {
    const mode = m[1], count = m[2] || '多'
    const meaning = MODE_MEANINGS[mode] || ''
    return {
      title: tagText,
      explanation: `命盘中有 ${count} 颗行星落在${mode}星座，${meaning}。这一模式主导着你面对生活变化时的基本姿态。`,
    }
  }

  // 逆行行星（新格式：如"逆行行星（火星·土星）"，前端已去括号展示）
  m = tagText.match(/^逆行行星（(.+)）$/)
  if (m) {
    const described = _describePlanets(m[1])
    return {
      title: tagText,
      explanation: `${described}在你出生时处于逆行状态。逆行行星的能量趋于内化，相关议题需要更多自我探索与反思，成熟后往往发展出独到的深度。`,
    }
  }
  // 逆行行星（旧格式，向后兼容）
  m = tagText.match(/^逆行行星：(.+)$/)
  if (m) {
    return {
      title: tagText,
      explanation: `${m[1]}在你出生时处于逆行状态。逆行行星的能量趋于内化，相关议题需要更多自我探索与反思，成熟后往往发展出独到的深度。`,
    }
  }

  // 命主星逆行（新格式含命主星名：如"命主星逆行（天王星）"）
  m = tagText.match(/^命主星逆行（(.+)）$/)
  if (m) {
    const ruler = m[1]
    const domain = PLANET_DOMAINS[ruler]
    const domainNote = domain ? `（${domain}）` : ''
    return {
      title: tagText,
      explanation: `你的命主星${ruler}${domainNote}在你出生时处于逆行状态，其能量趋于内化与深化。你在${ruler}所代表的领域往往有更多自我审视的倾向，成熟后能发展出超越常规的洞察力与独到深度。`,
    }
  }
  // 命主星逆行（无命主星名的 fallback）
  if (tagText === '命主星逆行') {
    return {
      title: tagText,
      explanation: '命主星在你出生时处于逆行状态，其能量趋于内化与深化。你在命主星所代表的领域往往有更多自我审视的倾向，成熟后能发展出超越常规的洞察力与独到深度。',
    }
  }

  // 单颗行星逆行（AI 简写格式，如"火星逆行"）
  m = tagText.match(/^(.+)逆行$/)
  if (m) {
    const planet = m[1]
    const domain = PLANET_DOMAINS[planet]
    const domainNote = domain ? `（${domain}）` : ''
    return {
      title: tagText,
      explanation: `${planet}${domainNote}在你出生时处于逆行状态，其能量趋于内化与深化。你在${planet}所代表的领域往往有更多自我审视的倾向，成熟后能发展出超越常规的洞察力与独到深度。`,
    }
  }

  // 大三角格局（含行星名：如"大三角格局（火星·土星·天王星）"）
  m = tagText.match(/^大三角格局（(.+)）$/)
  if (m) {
    const described = _describePlanets(m[1])
    return {
      title: tagText,
      explanation: `${described}形成等边三角形（互差约 120°），能量流动顺畅，是命盘中天赋才能的标志。虽然轻松，但也可能因过于舒适而缺乏主动挑战的动力。`,
    }
  }
  if (tagText.startsWith('大三角格局')) {
    return {
      title: tagText,
      explanation: '三颗行星形成等边三角形（互差约 120°），能量流动顺畅，是命盘中天赋才能的标志。虽然轻松，但也可能因过于舒适而缺乏主动挑战的动力。',
    }
  }

  // T三角格局（含行星名：如"T三角格局（顶点：火星，对冲：太阳·月亮）"）
  m = tagText.match(/^T三角格局（顶点：(.+?)，对冲：(.+)）$/)
  if (m) {
    const apex = m[1], oppStr = m[2]
    const domain = PLANET_DOMAINS[apex]
    const domainNote = domain ? `（${domain}）` : ''
    return {
      title: tagText,
      explanation: `${oppStr}形成对冲，各自与顶点${apex}${domainNote}形成四分相，构成紧张的 T 形。${apex}所在宫位是你人生的挑战中心，也是成长的关键出口。`,
    }
  }
  if (tagText.startsWith('T三角格局')) {
    return {
      title: tagText,
      explanation: '两颗对冲行星各自与第三颗行星形成四分相，构成紧张的 T 形。这是强大的行动动力，顶点行星所在的宫位领域是你人生的挑战中心，也是成长的关键出口。',
    }
  }

  // 未匹配
  return null
}
