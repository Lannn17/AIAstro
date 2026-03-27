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

/**
 * 根据标签文本返回解释。
 * @param {string} tagText
 * @returns {{ title: string, explanation: string } | null}
 */
export function getTagExplanation(tagText) {
  // 群星 + 星座（规则生成格式）
  let m = tagText.match(/^群星(.+)座（(\d+)颗核心行星）$/)
  if (m) {
    const sign = m[1], count = m[2]
    const meaning = SIGN_MEANINGS[sign] || '多元特质'
    return {
      title: tagText,
      explanation: `${count} 颗核心行星集中在${sign}座，能量高度聚焦。${sign}座特质（${meaning}）在你的命盘中格外突出，相关人生议题将反复出现。`,
    }
  }

  // 群星 + 宫位（AI 简写格式，如"群星3宫"）
  m = tagText.match(/^群星(\d+)宫$/)
  if (m) {
    const house = parseInt(m[1])
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    return {
      title: tagText,
      explanation: `多颗核心行星聚集于第 ${house} 宫（${meaning}），使这一生命领域成为你命盘的能量核心，相关议题会在人生中反复凸显。`,
    }
  }

  // 群星 + 星座简写（AI 格式，如"群星天蝎座"无括号）
  m = tagText.match(/^群星(.+)座$/)
  if (m) {
    const sign = m[1]
    const meaning = SIGN_MEANINGS[sign] || '多元特质'
    return {
      title: tagText,
      explanation: `多颗核心行星集中在${sign}座，${sign}座特质（${meaning}）在你的命盘中格外突出，相关人生议题将反复出现。`,
    }
  }

  // 宫位强势（规则生成格式）
  m = tagText.match(/^第(\d+)宫强势（(\d+)颗核心行星）$/)
  if (m) {
    const house = parseInt(m[1]), count = m[2]
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    return {
      title: tagText,
      explanation: `${count} 颗核心行星聚集于第 ${house} 宫（${meaning}），使这一生命领域成为你性格与经历的核心舞台，相关议题贯穿人生。`,
    }
  }

  // 宫位强势（AI 简写，如"第3宫强势"）
  m = tagText.match(/^第(\d+)宫强势$/)
  if (m) {
    const house = parseInt(m[1])
    const meaning = HOUSE_MEANINGS[house] || '该宫位相关领域'
    return {
      title: tagText,
      explanation: `多颗核心行星聚集于第 ${house} 宫（${meaning}），这一生命领域在你的命盘中占据重要地位，相关议题贯穿人生。`,
    }
  }

  // 多元素行星（规则生成格式及 AI 简写）
  m = tagText.match(/^多([火土风水])象行星[（(]?(\d+)?颗?[）)]?$/)
  if (m) {
    const elem = m[1], count = m[2] || '多'
    const meaning = ELEMENT_MEANINGS[elem] || ''
    return {
      title: tagText,
      explanation: `命盘中有 ${count} 颗行星位于${elem}象星座，${meaning}。这种元素主导使你的行事风格带有鲜明的${elem}象气质。`,
    }
  }

  // 多模式行星（规则生成格式及 AI 简写）
  m = tagText.match(/^多(本始|固定|变动)星[（(]?(\d+)?颗?[）)]?$/)
  if (m) {
    const mode = m[1], count = m[2] || '多'
    const meaning = MODE_MEANINGS[mode] || ''
    return {
      title: tagText,
      explanation: `命盘中有 ${count} 颗行星落在${mode}星座，${meaning}。这一模式主导着你面对生活变化时的基本姿态。`,
    }
  }

  // 逆行行星
  m = tagText.match(/^逆行行星：(.+)$/)
  if (m) {
    const planets = m[1]
    return {
      title: tagText,
      explanation: `${planets} 在你出生时处于逆行状态。逆行行星的能量趋于内化，相关议题需要更多自我探索与反思，成熟后往往发展出独到的深度。`,
    }
  }

  // 大三角格局
  if (tagText.startsWith('大三角格局')) {
    return {
      title: tagText,
      explanation: '三颗行星形成等边三角形（互差约 120°），能量流动顺畅，是命盘中天赋才能的标志。虽然轻松，但也可能因过于舒适而缺乏主动挑战的动力。',
    }
  }

  // T三角格局
  if (tagText.startsWith('T三角格局')) {
    return {
      title: tagText,
      explanation: '两颗对冲行星各自与第三颗行星形成四分相，构成紧张的 T 形。这是强大的行动动力，顶点行星所在的宫位领域是你人生的挑战中心，也是成长的关键出口。',
    }
  }

  // 未匹配
  return null
}
