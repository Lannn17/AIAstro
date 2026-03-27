# 本命盘标签点击解释功能 — 设计文档

**日期：** 2026-03-27
**状态：** 已批准，待实现
**来源：** TODO.md `#重要 5`

---

## 背景

本命盘综合概述下方展示若干标签（如"群星3宫"、"多火象行星"、"大三角格局"），用户反馈不理解这些标签的含义。需要设计一个低摩擦的方式让用户了解每个标签背后的占星概念。

---

## 目标

- 用户点击任意本命盘标签，立即看到该概念的简洁解释
- 提供通道让用户进一步向 AI 提问，了解该配置对自己星盘的具体影响

---

## 范围

- **本次实现**：`NatalChart.jsx` 中 `planetAnalyses.overall.tags` 的标签
- **不在范围内**：行运页面主题标签（事业、感情等）

---

## 方案设计

### 展示方式：Tooltip 气泡

点击标签后，在标签正下方弹出气泡（Tooltip），包含：
1. 标签名称（标题）
2. 静态预设解释文字（100字以内）
3. "✨ 问 AI 深入解读此配置" 按钮

气泡关闭条件：
- 点击气泡外任意区域
- 按 ESC 键
- 点击其他标签（同时只展开一个）

### 内容来源：静态 + AI 按钮（混合方案）

- **静态解释**：前端维护标签类型 → 解释的映射，点击即时显示，零延迟
- **AI 按钮**：复用已有占星对话功能，点击后跳转并预填问题，不新建后端端点

### AI 按钮交互

点击"问 AI 深入解读"后：
1. Tooltip 关闭
2. 页面滚动到占星对话区域（`#chat-section`）
3. 预填问题：`"请解释我星盘中的「{tag}」配置，对我的性格和人生有何影响？"`
4. 聚焦输入框，用户直接发送

---

## 文件变更计划

### 新建：`frontend/src/utils/tagExplanations.js`

导出函数 `getTagExplanation(tagText: string): { title: string, explanation: string } | null`

支持的标签模式：

| 正则模式 | 示例输入 | 解释重点 |
|---|---|---|
| `群星(.+)座（(\d+)颗核心行星）` | 群星白羊座（3颗核心行星） | 该星座特质 + 群星含义 |
| `第(\d+)宫强势（(\d+)颗核心行星）` | 第3宫强势（3颗核心行星） | 该宫位象征领域 |
| `多([火土风水])象行星（(\d+)颗）` | 多火象行星（4颗） | 该元素气质 |
| `多(本始\|固定\|变动)星（(\d+)颗）` | 多本始星（4颗） | 该模式特征 |
| `逆行行星：(.+)` | 逆行行星：水星、土星 | 逆行通用含义 + 涉及行星 |
| `大三角格局` | 大三角格局（太阳·月亮·火星） | 大三角相位含义 |
| `T三角格局` | T三角格局 | T三角相位含义 |
| 未匹配 | 任意 AI 生成标签 | 降级：仅显示 AI 按钮，不显示解释文字 |

### 新建：`frontend/src/components/TagTooltip.jsx`

**Props:**
```ts
{
  tag: string,          // 标签文本
  onAskAI: (tag: string) => void  // 点击"问AI"的回调
}
```

**内部状态：**
- `isOpen: boolean` — 气泡是否展开

**渲染结构：**
```
<span class="tag-wrapper">
  <span class="tag" onClick={toggle}>  ← 原标签样式 + hover 效果 + cursor:pointer
  {isOpen && (
    <div class="tooltip-bubble">
      <span class="tooltip-title">{tag}</span>
      <button class="close-btn">×</button>
      <p class="tooltip-body">{explanation}</p>   ← 无解释时隐藏
      <button class="ask-ai-btn" onClick={onAskAI}>✨ 问 AI 深入解读此配置</button>
    </div>
  )}
</span>
```

**定位逻辑：** 气泡默认向下展开；若接近视窗右边缘则向左对齐；若接近底部则向上展开。

**点击外部关闭：** 使用 `useEffect` + `document.addEventListener('mousedown', ...)` 实现。

### 修改：`frontend/src/pages/NatalChart.jsx`

1. 引入 `TagTooltip` 组件
2. 将 `planetAnalyses.overall.tags.map(tag => <span>)` 替换为 `<TagTooltip>` 循环
3. 实现 `handleAskAI(tag)` 回调：
   - 使用 `useRef` 引用占星对话输入框
   - 调用 `setChatInput(...)` 预填问题
   - `chatRef.current.scrollIntoView({ behavior: 'smooth' })`

---

## UX 细节

- 标签悬停：`border-color` 变亮 + `box-shadow` 微发光，提示可点击
- 活跃标签（tooltip 打开时）：背景色加深（`#2a2050`），边框变为金色
- Tooltip 宽度：最大 `320px`，文字 `12px`，行高 `1.6`
- 动画：`opacity + transform` 淡入（100ms），保持轻量

---

## 不在范围内

- 多语言解释文案（当前仅中文，与标签生成语言一致）
- 行运主题标签
- 后端新端点
- 解释内容的 AI 实时生成（通过现有对话入口实现）
