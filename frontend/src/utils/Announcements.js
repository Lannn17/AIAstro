import changelogRaw from '../../../CHANGELOG.md?raw';

function parseLatestUpdates(raw) {
  const lines = raw.split('\n');
  const updates = [];
  let inLatest = false;
  let inAdded = false;

  for (const line of lines) {
    if (!inLatest && /^## $$\d+\.\d+\.\d+$$/.test(line)) {
      inLatest = true;
      continue;
    }
    if (inLatest && /^## $$\d+\.\d+\.\d+$$/.test(line)) {
      break;
    }
    if (inLatest && /^### Added/.test(line)) {
      inAdded = true;
      continue;
    }
    if (inAdded && /^### /.test(line)) {
      inAdded = false;
      continue;
    }
    if (inAdded && line.startsWith('- **')) {
      const match = line.match(/- \*\*(.+?)\*\*\s*[—–-]\s*(.+)/);
      if (match) {
        updates.push({
          label: match[1],
          description: match[2],
        });
      }
    }
  }
  return updates;
}

function parseLatestDate(raw) {
  const match = raw.match(/## $$\d+\.\d+\.\d+$$ - (\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : "";
}

export const CURRENT_VERSION = __APP_VERSION__;
export const CURRENT_DATE = parseLatestDate(changelogRaw);
export const LATEST_UPDATES = parseLatestUpdates(changelogRaw);

export const ALL_FEATURES = [
  { label: "本命盘分析", description: "行星、相位、宫位完整解读 + 特质总结标签并支持点击查看详情" },
  { label: "出生时间校正", description: "三阶段校正：事件扫描 → 上升问卷 → 主题验证" },
  { label: "行运解读", description: "实时行运 AI 四维分析" },
  { label: "太阳回归盘", description: "年度运势 RAG + Gemini 解读" },
  { label: "合盘分析", description: "双人 SVG 盘图 + AI 多维度解读" },
];

export const UPCOMING = [
  { label: "月亮推运 Progressions", description: "锚定月亮反映的内心情绪" },
  { label: "每日卡片", description: "当天星运信息即时反馈" },
  { label: "占星骰子", description: "针对具体事件进行占星推运" },
];