import { useState, useEffect } from 'react'
import { useInterpret } from '../hooks/useInterpret'
import { SourcesSection } from '../components/AIPanel'
import ReactMarkdown from 'react-markdown'
import ChartForm from '../components/ChartForm'
import PlanetTable from '../components/PlanetTable'
import ChartWheel from '../components/ChartWheel'
import GuestSaveConfirmModal from '../components/GuestSaveConfirmModal'
import GuestSessionList from '../components/GuestSessionList'
import { useAuth } from '../contexts/AuthContext'
import { useChartSession } from '../contexts/ChartSessionContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const RECTIFY_DOMAINS = [
  {
    id: 'career', label: '职业 / 事业',
    question: '你的职业生涯中是否有重大事件？',
    types: [
      { value: 'career_up', label: '晋升 / 加薪' },
      { value: 'career_down', label: '降职 / 失业' },
      { value: 'career_change', label: '职业转型' },
      { value: 'business_start', label: '创业 / 开业' },
      { value: 'business_end', label: '关闭生意' },
      { value: 'retirement', label: '退休' },
    ],
  },
  {
    id: 'romance', label: '感情 / 婚恋',
    question: '你的感情关系中是否有重大事件？',
    types: [
      { value: 'marriage', label: '结婚' },
      { value: 'divorce', label: '离婚' },
      { value: 'new_relationship', label: '确立恋情' },
      { value: 'breakup', label: '分手 / 分居' },
    ],
  },
  {
    id: 'family', label: '家庭 / 亲子',
    question: '你的家庭生活中是否有重大变化？',
    types: [
      { value: 'childbirth', label: '子女出生 / 收养' },
      { value: 'bereavement_parent', label: '父母去世' },
      { value: 'bereavement_spouse', label: '配偶去世' },
      { value: 'bereavement_child', label: '子女去世' },
      { value: 'bereavement_other', label: '其他亲友去世' },
      { value: 'family_bond_change', label: '家庭关系重大转变（决裂 / 和解）' },
    ],
  },
  {
    id: 'health', label: '健康 / 身体',
    question: '你是否经历过重大健康事件？',
    types: [
      { value: 'serious_illness', label: '重病确诊' },
      { value: 'accident', label: '意外事故' },
      { value: 'surgery', label: '重大手术' },
      { value: 'mental_health_crisis', label: '精神健康危机' },
    ],
  },
  {
    id: 'finance', label: '财务 / 资产',
    question: '你是否经历过重大财务变动？',
    types: [
      { value: 'financial_gain', label: '重大收益' },
      { value: 'financial_loss', label: '重大损失' },
      { value: 'major_investment', label: '重大投资 / 购房' },
      { value: 'inheritance', label: '继承遗产' },
      { value: 'bankruptcy', label: '破产' },
    ],
  },
  {
    id: 'relocation', label: '出行 / 移居 / 求学',
    question: '你是否有过重大迁移、求学或法律经历？',
    types: [
      { value: 'relocation_domestic', label: '国内搬迁' },
      { value: 'relocation_international', label: '跨国移居' },
      { value: 'study_abroad', label: '留学 / 出国求学' },
      { value: 'major_exam', label: '重要考试 / 升学' },
      { value: 'graduation', label: '毕业 / 重要学历' },
      { value: 'legal_win', label: '胜诉' },
      { value: 'legal_loss', label: '败诉 / 法律纠纷' },
      { value: 'spiritual_awakening', label: '精神觉醒 / 信仰转变' },
    ],
  },
]

export default function NatalChart() {
  const { isGuest, isAuthenticated, authHeaders, logout } = useAuth()
  const { currentSessionChart, addSessionChart } = useChartSession()
  const [result, setResult] = useState(null)
  const [svgContent, setSvgContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lastFormData, setLastFormData] = useState(null)
  const [lastLocationName, setLastLocationName] = useState(null)

  const [savedCharts, setSavedCharts] = useState([])
  const [pendingCharts, setPendingCharts] = useState([])
  const [saving, setSaving] = useState(false)
  const [savedId, setSavedId] = useState(null)  // id of currently loaded saved chart
  const [editingChartId, setEditingChartId] = useState(null)  // id being edited (patch target)
  const [chartFormKey, setChartFormKey] = useState(0)  // increment to remount ChartForm with new data
  const [chartFormInitialData, setChartFormInitialData] = useState(null)

  const [messages, setMessages] = useState([])
  const [chatSummary, setChatSummary] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  // Planet interpretations
  const [planetAnalyses, setPlanetAnalyses] = useState({})
  const planetInterp = useInterpret('/api/interpret_planets')

  const [rectifyOpen, setRectifyOpen] = useState(false)
  const [rectifyEvents, setRectifyEvents] = useState([])
  const [rectifyWizardStep, setRectifyWizardStep] = useState(0)  // 0-5=domain, 6=turning point
  const [currentDomainEvent, setCurrentDomainEvent] = useState(null)
  const [approxHour, setApproxHour] = useState('')
  const [timeRangeHours, setTimeRangeHours] = useState('')
  const [rectifyLoading, setRectifyLoading] = useState(false)
  const [rectifyResult, setRectifyResult] = useState(null)
  const [rectifyError, setRectifyError] = useState(null)

  // Phase 2: ASC quiz
  const [ascQuizData, setAscQuizData] = useState(null)
  const [ascQuizLoading, setAscQuizLoading] = useState(false)
  const [ascQuizAnswers, setAscQuizAnswers] = useState({})
  const [recommendedIdx, setRecommendedIdx] = useState(null)

  // Phase 3: theme quiz + confidence
  const [themeQuizData, setThemeQuizData] = useState(null)
  const [themeAnswers, setThemeAnswers] = useState({})
  const [confidenceResult, setConfidenceResult] = useState(null)
  const [confidenceLoading, setConfidenceLoading] = useState(false)

  const [showGuestConfirm, setShowGuestConfirm] = useState(false)
  const [pendingFormData, setPendingFormData] = useState(null)
  const [pendingLocationName, setPendingLocationName] = useState(null)

  // Restore guest session chart when returning to this tab
  useEffect(() => {
    if (isGuest && result === null && currentSessionChart) {
      setResult(currentSessionChart.chartData)
      setSvgContent(currentSessionChart.svgData || null)
      setLastFormData(currentSessionChart.formData)
      setLastLocationName(currentSessionChart.locationName)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isAuthenticated) {
      fetchSavedCharts()
      fetchPendingCharts()
    }
  }, [isAuthenticated])

  async function fetchSavedCharts() {
    try {
      const res = await fetch(`${API_BASE}/api/charts`, { headers: authHeaders() })
      if (res.ok) {
        setSavedCharts(await res.json())
      } else if (res.status === 401) {
        logout()
      } else {
        const errText = await res.text().catch(() => '')
        setError(`加载星盘列表失败 (${res.status})${errText ? ': ' + errText : ''}`)
      }
    } catch (e) {
      setError(`无法连接服务器: ${e.message}`)
    }
  }

  async function fetchPendingCharts() {
    try {
      const res = await fetch(`${API_BASE}/api/charts/pending`, { headers: authHeaders() })
      if (res.ok) setPendingCharts(await res.json())
      // 401 handled by fetchSavedCharts; other errors silently ignored for pending list
    } catch { /* ignore */ }
  }

  async function handleApprove(id, e) {
    e.stopPropagation()
    await fetch(`${API_BASE}/api/charts/pending/${id}/approve`, {
      method: 'POST', headers: authHeaders(),
    })
    await Promise.all([fetchSavedCharts(), fetchPendingCharts()])
  }

  async function handleRejectPending(id, e) {
    e.stopPropagation()
    if (!window.confirm('删除此待审核记录？')) return
    await fetch(`${API_BASE}/api/charts/${id}`, { method: 'DELETE', headers: authHeaders() })
    await fetchPendingCharts()
  }

  async function handleSubmit(formData, locationName) {
    // Guests must confirm data submission before seeing any results
    if (isGuest) {
      setPendingFormData(formData)
      setPendingLocationName(locationName)
      setShowGuestConfirm(true)
      return
    }
    await doCalculate(formData, locationName)
  }

  // Calculate chart (owner path — no auto-save)
  async function doCalculate(formData, locationName) {
    setLoading(true)
    setError(null)
    setResult(null)
    setSvgContent(null)
    setSavedId(null)
    setPlanetAnalyses({})
    planetInterp.reset()
    setLastFormData(formData)
    setLastLocationName(locationName)
    setMessages([])
    setChatSummary('')

    try {
      const res = await fetch(`${API_BASE}/api/natal_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setResult(data)

      const svgRes = await fetch(`${API_BASE}/api/svg_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal_chart: formData,
          chart_type: 'natal',
          show_aspects: true,
          language: formData.language || 'zh',
          theme: 'dark',
        }),
      })
      const svgData = svgRes.ok ? await svgRes.text() : null
      if (svgData) setSvgContent(svgData)
      addSessionChart({ name: formData.name || '未命名', chartData: data, formData, locationName, svgData })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Guest confirmed: calculate + auto-save to pending queue
  async function doGuestSubmit() {
    const formData = pendingFormData
    const locationName = pendingLocationName
    setShowGuestConfirm(false)
    setPendingFormData(null)
    setPendingLocationName(null)

    setLoading(true)
    setError(null)
    setResult(null)
    setSvgContent(null)
    setSavedId(null)
    setPlanetAnalyses({})
    planetInterp.reset()
    setLastFormData(formData)
    setLastLocationName(locationName)
    setMessages([])
    setChatSummary('')

    let chartData = null
    let svgData = null
    try {
      const res = await fetch(`${API_BASE}/api/natal_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      chartData = await res.json()
      setResult(chartData)

      const svgRes = await fetch(`${API_BASE}/api/svg_chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal_chart: formData,
          chart_type: 'natal',
          show_aspects: true,
          language: formData.language || 'zh',
          theme: 'dark',
        }),
      })
      if (svgRes.ok) { svgData = await svgRes.text(); setSvgContent(svgData) }
      addSessionChart({ name: formData.name || '未命名', chartData, formData, locationName, svgData })
    } catch (e) {
      setError(e.message)
      setLoading(false)
      return
    } finally {
      setLoading(false)
    }

    // Auto-save to pending queue (no auth token → backend marks is_guest=1)
    try {
      const label = formData.name
        ? `${formData.name} · ${formData.year}/${formData.month}/${formData.day}`
        : `星盘 ${formData.year}/${formData.month}/${formData.day}`
      await fetch(`${API_BASE}/api/charts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label,
          name: formData.name || null,
          birth_year: formData.year,
          birth_month: formData.month,
          birth_day: formData.day,
          birth_hour: formData.hour,
          birth_minute: formData.minute,
          location_name: locationName || null,
          latitude: formData.latitude,
          longitude: formData.longitude,
          tz_str: formData.tz_str,
          house_system: formData.house_system,
          language: formData.language,
          chart_data: chartData,
          svg_data: svgData || null,
        }),
      })
    } catch { /* silent — results still shown even if queue save fails */ }
  }

  async function handleSave() {
    if (!result || !lastFormData) return
    setSaving(true)
    try {
      const label = lastFormData.name
        ? `${lastFormData.name} · ${lastFormData.year}/${lastFormData.month}/${lastFormData.day}`
        : `星盘 ${lastFormData.year}/${lastFormData.month}/${lastFormData.day}`

      const res = await fetch(`${API_BASE}/api/charts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          label,
          name: lastFormData.name || null,
          birth_year: lastFormData.year,
          birth_month: lastFormData.month,
          birth_day: lastFormData.day,
          birth_hour: lastFormData.hour,
          birth_minute: lastFormData.minute,
          location_name: lastLocationName || null,
          latitude: lastFormData.latitude,
          longitude: lastFormData.longitude,
          tz_str: lastFormData.tz_str,
          house_system: lastFormData.house_system,
          language: lastFormData.language,
          chart_data: result,
          svg_data: svgContent || null,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(`${res.status} ${body.detail || ''}`)
      }
      const saved = await res.json()
      setSavedId(saved.id)
      setEditingChartId(null)
      setChartFormInitialData(null)
      await fetchSavedCharts()
    } catch (e) {
      setError(`保存失败: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  async function handleLoad(summary) {
    setSavedId(summary.id)
    setEditingChartId(null)
    setChartFormInitialData(null)
    setError(null)
    setMessages([])
    setChatSummary('')
    try {
      const res = await fetch(`${API_BASE}/api/charts/${summary.id}`, { headers: authHeaders() })
      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${errText}`)
      }
      const chart = await res.json()
      setLastFormData({
        name: chart.name || '',
        year: chart.birth_year,
        month: chart.birth_month,
        day: chart.birth_day,
        hour: chart.birth_hour,
        minute: chart.birth_minute,
        latitude: chart.latitude,
        longitude: chart.longitude,
        tz_str: chart.tz_str,
        house_system: chart.house_system,
        language: chart.language,
      })
      setLastLocationName(chart.location_name)
      if (chart.chart_data) {
        setResult(chart.chart_data)
        setPlanetAnalyses({})
        // 静默查缓存：命中→自动显示；未命中→静默（按钮出现等用户点击）
        fetchPlanetCache(chart.chart_data, summary.id)
      }
      if (chart.svg_data) setSvgContent(chart.svg_data)
    } catch (e) {
      setError(`加载失败: ${e.message}`)
      setSavedId(null)
    }
  }

  // 滚动摘要：当消息超过8条时，把旧消息压缩成摘要并裁掉，保持 token 消耗恒定
  async function maybeCompress(allMessages) {
    if (allMessages.length < 8) return
    const toSummarize = allMessages.slice(0, -4)  // 除最近4条外全部压缩
    const keep        = allMessages.slice(-4)
    try {
      const res = await fetch(`${API_BASE}/api/interpret/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: toSummarize,
          chart_name: result?.input_data?.name || '',
        }),
      })
      if (!res.ok) return  // 摘要失败时静默保留原历史，不影响主流程
      const { summary } = await res.json()
      setChatSummary(prev => prev ? `${prev}\n${summary}` : summary)
      setMessages(keep)
    } catch { /* 静默失败 */ }
  }

  async function handleChat(e) {
    e.preventDefault()
    if (!chatInput.trim() || !result) return
    const question = chatInput.trim()
    const historySnapshot = messages.slice(-4)  // 最近2轮原始历史
    setChatInput('')
    setMessages(prev => [...prev, { role: 'user', text: question }])
    setChatLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/interpret/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: question,
          chart_data: result,
          k: 5,
          history: historySnapshot,
          summary: chatSummary,
        }),
      })
      if (!res.ok) throw new Error(`错误 ${res.status}`)
      const data = await res.json()
      setMessages(prev => {
        const next = [...prev, { role: 'assistant', text: data.answer, sources: data.sources }]
        maybeCompress(next)  // 后台异步压缩，不阻塞 UI
        return next
      })
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: `⚠ ${e.message}` }])
    } finally {
      setChatLoading(false)
    }
  }

  async function fetchPlanetCache(chartData, chartId) {
    if (!chartData || !chartId) return
    try {
      const res = await fetch(`${API_BASE}/api/interpret_planets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          natal_chart: chartData,
          language: chartData.input_data?.language || 'zh',
          chart_id: chartId,
          cache_only: true,
        }),
      })
      if (res.ok) {
        const resp = await res.json()
        if (resp.analyses) setPlanetAnalyses(resp.analyses)
      }
    } catch { /* silent */ }
  }

  async function handleInterpretPlanets(chartData, chartId) {
    const data = (chartData && chartData.planets) ? chartData : result
    const id = chartId !== undefined ? chartId : savedId
    if (!data) return
    const json = await planetInterp.run({
      natal_chart: data,
      language: data.input_data?.language || 'zh',
      chart_id: id || null,
    })
    if (json?.analyses) setPlanetAnalyses(json.analyses)
  }

  async function handleRectify() {
    if (!lastFormData) return
    const events = rectifyEvents
      .filter(e => e.year)
      .map(e => ({
        year: Number(e.year),
        month: e.month ? Number(e.month) : null,
        day: (e.month && e.day) ? Number(e.day) : null,
        event_type: e.event_type,
        weight: Number(e.weight),
        is_turning_point: e.is_turning_point || false,
      }))
    if (events.length === 0) { setRectifyError('请至少填写一个事件（年份必填）'); return }
    setRectifyLoading(true)
    setRectifyError(null)
    setRectifyResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/rectify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          birth_year: lastFormData.year, birth_month: lastFormData.month, birth_day: lastFormData.day,
          latitude: lastFormData.latitude, longitude: lastFormData.longitude,
          tz_str: lastFormData.tz_str, house_system: lastFormData.house_system,
          events,
          approx_hour: approxHour !== '' ? Number(approxHour) : null,
          approx_minute: null,
          time_range_hours: timeRangeHours !== '' ? Number(timeRangeHours) : null,
          natal_chart_data: result || {},
        }),
      })
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `错误 ${res.status}`) }
      const data = await res.json()
      setRectifyResult(data)
      // Reset phase 2/3 states for new run
      setAscQuizData(null); setAscQuizAnswers({}); setRecommendedIdx(null)
      setThemeQuizData(null); setThemeAnswers({}); setConfidenceResult(null)
    } catch (e) { setRectifyError(e.message) }
    finally { setRectifyLoading(false) }
  }

  async function handleLoadAscQuiz(top3) {
    setAscQuizLoading(true)
    try {
      const signs = top3.map(t => t.asc_sign).filter(Boolean)
      const res = await fetch(`${API_BASE}/api/rectify/asc_quiz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asc_signs: signs }),
      })
      if (res.ok) setAscQuizData((await res.json()).questions)
    } catch { /* silent */ }
    finally { setAscQuizLoading(false) }
  }

  function handleAscAnswer(qId, option) {
    setAscQuizAnswers(prev => ({ ...prev, [qId]: option }))
  }

  function handleSubmitAscQuiz() {
    if (!rectifyResult?.top3) return
    const top3 = rectifyResult.top3
    const signScores = {}
    top3.forEach(t => { signScores[t.asc_sign] = 0 })
    Object.values(ascQuizAnswers).forEach(opt => {
      (opt.signs || []).forEach(s => { if (s in signScores) signScores[s]++ })
    })
    const best = top3.reduce((a, b) =>
      (signScores[b.asc_sign] || 0) > (signScores[a.asc_sign] || 0) ? b : a
    )
    setRecommendedIdx(top3.indexOf(best))
    // Load theme quiz
    fetch(`${API_BASE}/api/rectify/theme_quiz`)
      .then(r => r.json()).then(d => setThemeQuizData(d.questions)).catch(() => {})
  }

  async function handleSubmitThemeQuiz() {
    if (!rectifyResult?.top3 || recommendedIdx === null) return
    const candidate = rectifyResult.top3[recommendedIdx]
    const answers = themeQuizData?.map(q => ({
      question: q.text,
      answer: themeAnswers[q.id]?.text || '未作答',
    })) || []
    setConfidenceLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/rectify/confidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate,
          birth_year: lastFormData.year, birth_month: lastFormData.month, birth_day: lastFormData.day,
          latitude: lastFormData.latitude, longitude: lastFormData.longitude,
          tz_str: lastFormData.tz_str,
          theme_answers: answers,
        }),
      })
      if (res.ok) setConfidenceResult(await res.json())
    } catch { /* silent */ }
    finally { setConfidenceLoading(false) }
  }

  function removeEvent(i) { setRectifyEvents(prev => prev.filter((_, idx) => idx !== i)) }
  function updateEvent(i, field, value) { setRectifyEvents(prev => prev.map((e, idx) => idx === i ? { ...e, [field]: value } : e)) }

  async function handleDelete(id, e) {
    e.stopPropagation()
    if (!window.confirm('确认删除该星盘？此操作无法撤销。')) return
    await fetch(`${API_BASE}/api/charts/${id}`, { method: 'DELETE', headers: authHeaders() })
    if (savedId === id || editingChartId === id) {
      setSavedId(null)
      setEditingChartId(null)
      setChartFormInitialData(null)
      setResult(null)
      setSvgContent(null)
      setLastFormData(null)
    }
    await fetchSavedCharts()
  }

  function handleEdit() {
    if (!savedId || !lastFormData) return
    setEditingChartId(savedId)
    setChartFormInitialData({ ...lastFormData, locationName: lastLocationName })
    setChartFormKey(k => k + 1)
  }

  async function handleUpdate() {
    if (!result || !lastFormData || !editingChartId) return
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/charts/${editingChartId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          name: lastFormData.name || null,
          birth_year: lastFormData.year,
          birth_month: lastFormData.month,
          birth_day: lastFormData.day,
          birth_hour: lastFormData.hour,
          birth_minute: lastFormData.minute,
          location_name: lastLocationName || null,
          latitude: lastFormData.latitude,
          longitude: lastFormData.longitude,
          tz_str: lastFormData.tz_str,
          house_system: lastFormData.house_system,
          language: lastFormData.language,
          chart_data: result,
          svg_data: svgContent || null,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(`${res.status} ${body.detail || ''}`)
      }
      setSavedId(editingChartId)
      setEditingChartId(null)
      setChartFormInitialData(null)
      await fetchSavedCharts()
    } catch (e) {
      setError(`更新失败: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const labelStyle = { color: '#9a8acc', fontSize: '0.78rem', fontWeight: 600, marginBottom: '6px' }
  const inputSm = { background: '#0e0e24', border: '1px solid #2a2a5a', color: '#d0d0e0', borderRadius: '5px', padding: '6px 8px', fontSize: '0.82rem', boxSizing: 'border-box' }

  return (
    <div className="page-layout">

      {showGuestConfirm && (
        <GuestSaveConfirmModal
          onConfirm={doGuestSubmit}
          onCancel={() => setShowGuestConfirm(false)}
        />
      )}

      {/* Sidebar */}
      <div className="page-sidebar">
      {isAuthenticated ? (
        <>
        {/* Pending charts (guest submissions awaiting approval) */}
        {pendingCharts.length > 0 && (
          <div style={{
            backgroundColor: '#1a1208',
            border: '1px solid #4a3a1a',
            borderRadius: '10px',
            overflow: 'hidden',
            marginBottom: '12px',
          }}>
            <div style={{
              padding: '10px 14px',
              borderBottom: '1px solid #4a3a1a',
              color: '#c9a84c',
              fontSize: '0.7rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}>
              待审核
              <span style={{
                backgroundColor: '#c9a84c', color: '#0a0a1a',
                borderRadius: '10px', fontSize: '0.65rem',
                padding: '1px 6px', fontWeight: 700,
              }}>
                {pendingCharts.length}
              </span>
            </div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {pendingCharts.map(c => (
                <li key={c.id} style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid #2a1a08',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: '6px',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      color: '#c8b888', fontSize: '0.78rem', fontWeight: 500,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {c.name || '无名'}
                    </div>
                    <div style={{ color: '#7a6a4a', fontSize: '0.68rem', marginTop: '2px' }}>
                      {c.birth_year}/{c.birth_month}/{c.birth_day}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                    <button
                      onClick={(e) => handleApprove(c.id, e)}
                      title="批准"
                      style={{
                        background: 'none', border: '1px solid #4a6a3a',
                        color: '#6aaa5a', cursor: 'pointer',
                        fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px',
                      }}
                    >✓</button>
                    <button
                      onClick={(e) => handleRejectPending(c.id, e)}
                      title="删除"
                      style={{
                        background: 'none', border: 'none', color: '#4a3a3a',
                        cursor: 'pointer', fontSize: '0.75rem', padding: '2px',
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = '#cc6666'}
                      onMouseLeave={e => e.currentTarget.style.color = '#4a3a3a'}
                    >✕</button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Saved charts */}
        <div style={{
          backgroundColor: '#12122a',
          border: '1px solid #2a2a5a',
          borderRadius: '10px',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '10px 14px',
            borderBottom: '1px solid #2a2a5a',
            color: '#c9a84c',
            fontSize: '0.7rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}>
            已保存星盘
          </div>
          {savedCharts.length === 0 ? (
            <div style={{ padding: '16px 14px', color: '#3a3a6a', fontSize: '0.75rem' }}>暂无记录</div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {savedCharts.map(c => (
                <li
                  key={c.id}
                  onClick={() => handleLoad(c)}
                  style={{
                    padding: '10px 14px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #1a1a35',
                    backgroundColor: savedId === c.id ? '#1e1e40' : 'transparent',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: '6px',
                  }}
                  onMouseEnter={e => { if (savedId !== c.id) e.currentTarget.style.backgroundColor = '#16163a' }}
                  onMouseLeave={e => { if (savedId !== c.id) e.currentTarget.style.backgroundColor = 'transparent' }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      color: savedId === c.id ? '#c9a84c' : '#c8c8e8',
                      fontSize: '0.78rem',
                      fontWeight: 500,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {c.name || '无名'}
                    </div>
                    <div style={{ color: '#6666aa', fontSize: '0.68rem', marginTop: '2px' }}>
                      {c.birth_year}/{c.birth_month}/{c.birth_day}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(c.id, e)}
                    style={{
                      background: 'none', border: 'none', color: '#4a3a5a',
                      cursor: 'pointer', fontSize: '0.75rem', padding: '0',
                      flexShrink: 0, lineHeight: 1,
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = '#cc6666'}
                    onMouseLeave={e => e.currentTarget.style.color = '#4a3a5a'}
                  >✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>
        </>
      ) : (
        <GuestSessionList />
      )}
      </div>

      {/* Main area */}
      <div className="page-main">

        {/* Left column: form */}
        <div className="page-form-col">
          <ChartForm
            key={chartFormKey}
            onSubmit={handleSubmit}
            loading={loading}
            initialData={chartFormInitialData}
          />

          {error && (
            <div className="mt-4 p-3 rounded-lg text-sm"
              style={{ backgroundColor: '#2a1020', color: '#ff8888', border: '1px solid #5a2030' }}>
              ✗ {error}
            </div>
          )}

          {result && (!savedId || editingChartId) && !loading && svgContent && !isGuest && (
            editingChartId ? (
              <div className="mt-3" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <button
                  onClick={handleUpdate}
                  disabled={saving}
                  className="w-full py-2 rounded-lg tracking-wider transition-opacity"
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid #c9a84c',
                    color: '#c9a84c',
                    fontSize: '0.85rem',
                    opacity: saving ? 0.5 : 1,
                    cursor: saving ? 'not-allowed' : 'pointer',
                  }}
                >
                  {saving ? '更新中…' : '✦ 更新已保存星盘'}
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="w-full py-2 rounded-lg tracking-wider transition-opacity"
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid #5a5a8a',
                    color: '#9090cc',
                    fontSize: '0.82rem',
                    opacity: saving ? 0.5 : 1,
                    cursor: saving ? 'not-allowed' : 'pointer',
                  }}
                >
                  另存为新星盘
                </button>
                <button
                  onClick={() => { setEditingChartId(null); setChartFormInitialData(null) }}
                  style={{
                    background: 'none', border: 'none', color: '#666688',
                    fontSize: '0.75rem', cursor: 'pointer', padding: '2px 0',
                  }}
                >
                  × 取消编辑
                </button>
              </div>
            ) : (
              <button
                onClick={handleSave}
                disabled={saving}
                className="mt-3 w-full py-2 rounded-lg tracking-wider transition-opacity"
                style={{
                  backgroundColor: 'transparent',
                  border: '1px solid #c9a84c',
                  color: '#c9a84c',
                  fontSize: '0.85rem',
                  opacity: saving ? 0.5 : 1,
                  cursor: saving ? 'not-allowed' : 'pointer',
                }}
              >
                {saving ? '保存中…' : '✦ 保存此星盘'}
              </button>
            )
          )}

          {savedId && (
            <div className="mt-3" style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
              <div style={{ color: '#4a8a4a', fontSize: '0.78rem' }}>✓ 已保存</div>
              <button
                onClick={handleEdit}
                style={{
                  background: 'none',
                  border: '1px solid #2a2a5a',
                  color: '#7878aa',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  padding: '4px 12px',
                  cursor: 'pointer',
                  width: '100%',
                }}
              >
                ✏ 编辑此星盘
              </button>
            </div>
          )}

          {/* Chat toggle button */}
          {result && svgContent && (
            <button
              className="mt-4 w-full py-2 rounded-lg tracking-wider"
              onClick={() => { setChatOpen(o => !o); setRectifyOpen(false) }}
              style={{
                backgroundColor: chatOpen ? '#c9a84c' : 'transparent',
                border: '1px solid #c9a84c',
                color: chatOpen ? '#0a0a1a' : '#c9a84c',
                fontSize: '0.88rem',
                cursor: 'pointer',
                fontWeight: chatOpen ? 600 : 400,
              }}
            >
              ✦ 占星对话
            </button>
          )}

          {/* Rectify toggle button */}
          {result && (
            <button
              className="mt-2 w-full py-2 rounded-lg tracking-wider"
              onClick={() => { setRectifyOpen(o => !o); setChatOpen(false) }}
              style={{
                backgroundColor: rectifyOpen ? '#7a6aaa' : 'transparent',
                border: '1px solid #7a6aaa',
                color: rectifyOpen ? '#ffffff' : '#9a8acc',
                fontSize: '0.88rem',
                cursor: 'pointer',
                fontWeight: rectifyOpen ? 600 : 400,
              }}
            >
              ◈ 校对出生时间
            </button>
          )}
        </div>

        {/* Right column: results or chat */}
        <div className="page-result-col">

          {/* Chart results */}
          {!chatOpen && (
            <>
              {!result && !loading && (
                <div className="flex items-center justify-center rounded-xl"
                  style={{ height: '400px', backgroundColor: '#12122a', border: '1px dashed #2a2a5a', color: '#3a3a6a', fontSize: '2rem' }}>
                  ✦
                </div>
              )}
              {loading && (
                <div className="flex items-center justify-center rounded-xl"
                  style={{ height: '400px', backgroundColor: '#12122a', border: '1px solid #2a2a5a', color: '#8888aa', fontSize: '0.9rem' }}>
                  计算中…
                </div>
              )}
              {result && (
                <div className="space-y-6">
                  {svgContent && <ChartWheel svgContent={svgContent} language={result.input_data?.language} />}
                  <PlanetTable planets={result.planets} language={result.input_data?.language} analyses={planetAnalyses} />
                  {/* 行星解读按钮 / 综合概述 */}
                  {planetInterp.error && (
                    <div style={{ color: '#e07070', fontSize: '0.82rem', padding: '8px 12px', background: '#1a0f0f', border: '1px solid #5a2a2a', borderRadius: '6px' }}>
                      ✕ {planetInterp.error}
                    </div>
                  )}
                  {!Object.keys(planetAnalyses).length ? (
                    <button onClick={() => handleInterpretPlanets()} disabled={planetInterp.loading}
                      style={{
                        width: '100%', padding: '11px',
                        background: planetInterp.loading ? '#1e1e3a' : 'linear-gradient(135deg, #2a1a4a, #1a1a3a)',
                        border: '1px solid #7a6aaa', borderRadius: '8px',
                        color: planetInterp.loading ? '#5a5a8a' : '#c9a84c',
                        fontWeight: 700, fontSize: '0.88rem', cursor: planetInterp.loading ? 'not-allowed' : 'pointer',
                        letterSpacing: '0.05em',
                      }}>
                      {planetInterp.loading ? '✦ 解读生成中… 约 10-20 秒' : '✦ 生成行星解读'}
                    </button>
                  ) : planetAnalyses.overall ? (
                    <div style={{ background: '#0f0f28', border: '1px solid #3a3a6a', borderRadius: '10px', padding: '16px 18px' }}>
                      <div style={{ color: '#9a8acc', fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '12px' }}>本命盘综合概述</div>
                      {/* 特征标签 */}
                      {planetAnalyses.overall.tags?.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
                          {planetAnalyses.overall.tags.map((tag, i) => (
                            <span key={i} style={{
                              padding: '3px 10px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: 600,
                              background: '#1e1a38', border: '1px solid #7a6aaa', color: '#c9a84c',
                            }}>{tag}</span>
                          ))}
                        </div>
                      )}
                      {/* 主要命题 */}
                      {planetAnalyses.overall.summary && (
                        <p style={{ color: '#d0d0e8', fontSize: '0.9rem', lineHeight: 1.85, marginBottom: '16px' }}>
                          {planetAnalyses.overall.summary}
                        </p>
                      )}
                      {/* 分领域详述 */}
                      {[
                        { key: 'career', label: '✦ 学业与事业' },
                        { key: 'love',   label: '✦ 恋爱与家庭' },
                        { key: 'wealth', label: '✦ 财富与物质' },
                        { key: 'health', label: '✦ 健康与身体' },
                      ].map(({ key, label }) => planetAnalyses.overall[key] ? (
                        <div key={key} style={{ marginBottom: '12px' }}>
                          <div style={{ color: '#8888aa', fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>{label}</div>
                          <p style={{ color: '#b8b8d8', fontSize: '0.86rem', lineHeight: 1.8, margin: 0 }}>{planetAnalyses.overall[key]}</p>
                        </div>
                      ) : null)}
                    </div>
                  ) : null}
                </div>
              )}
            </>
          )}

          {/* Chat panel */}
          {chatOpen && result && (
            <div className="chat-panel">
              {/* Header */}
              <div style={{
                padding: '12px 16px', borderBottom: '1px solid #2a2a5a',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <span style={{ color: '#c9a84c', fontSize: '0.75rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  ✦ 占星对话
                </span>
              </div>

              {/* Messages */}
              <div style={{
                flex: 1, padding: '16px',
                display: 'flex', flexDirection: 'column', gap: '14px',
                overflowY: 'auto',
              }}>
                {messages.length === 0 && (
                  <div style={{ color: '#3a3a6a', fontSize: '0.88rem' }}>
                    问我关于你星盘的任何问题…
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '92%',
                    backgroundColor: msg.role === 'user' ? '#1e1e50' : '#1a1a35',
                    border: `1px solid ${msg.role === 'user' ? '#3a3a8a' : '#2a2a5a'}`,
                    borderRadius: '10px',
                    padding: '12px 16px',
                    fontSize: '0.95rem',
                    color: '#e8e8ff',
                    lineHeight: 1.75,
                  }}>
                    {msg.role === 'user' ? msg.text : (<>
                      <ReactMarkdown components={{
                        h1: ({children}) => <div style={{fontSize:'1.05rem', fontWeight:700, color:'#c9a84c', marginBottom:'6px'}}>{children}</div>,
                        h2: ({children}) => <div style={{fontSize:'1rem', fontWeight:700, color:'#c9a84c', marginBottom:'5px'}}>{children}</div>,
                        h3: ({children}) => <div style={{fontSize:'0.95rem', fontWeight:700, color:'#c9a84c', marginBottom:'4px', marginTop:'12px'}}>{children}</div>,
                        p: ({children}) => <p style={{margin:'5px 0'}}>{children}</p>,
                        strong: ({children}) => <strong style={{color:'#e8c96c'}}>{children}</strong>,
                        ul: ({children}) => <ul style={{paddingLeft:'20px', margin:'5px 0'}}>{children}</ul>,
                        ol: ({children}) => <ol style={{paddingLeft:'20px', margin:'5px 0'}}>{children}</ol>,
                        li: ({children}) => <li style={{marginBottom:'4px'}}>{children}</li>,
                        hr: () => <hr style={{border:'none', borderTop:'1px solid #2a2a5a', margin:'10px 0'}} />,
                      }}>
                        {msg.text}
                      </ReactMarkdown>
                      <SourcesSection sources={msg.sources} />
                    </>)}
                  </div>
                ))}
                {chatLoading && (
                  <div style={{ color: '#6666aa', fontSize: '0.88rem' }}>思考中…</div>
                )}
              </div>

              {/* Input */}
              <form onSubmit={handleChat} style={{
                display: 'flex', gap: '8px', padding: '12px 16px',
                borderTop: '1px solid #2a2a5a',
              }}>
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  placeholder="问关于星盘的问题…"
                  disabled={chatLoading}
                  autoFocus
                  style={{
                    flex: 1,
                    backgroundColor: '#0d0d22',
                    border: '1px solid #2a2a5a',
                    color: '#e8e8ff',
                    borderRadius: '6px',
                    padding: '10px 14px',
                    fontSize: '0.95rem',
                    outline: 'none',
                  }}
                />
                <button type="submit" disabled={chatLoading || !chatInput.trim()}
                  style={{
                    backgroundColor: '#c9a84c', color: '#0a0a1a',
                    border: 'none', borderRadius: '6px',
                    padding: '10px 18px', fontWeight: 600,
                    fontSize: '0.95rem',
                    cursor: chatLoading ? 'not-allowed' : 'pointer',
                    opacity: chatLoading || !chatInput.trim() ? 0.5 : 1,
                  }}>
                  发送
                </button>
              </form>
            </div>
          )}
          {/* Rectification panel */}
          {rectifyOpen && result && (
            <div style={{ backgroundColor: '#12122a', border: '1px solid #2a2a5a', borderRadius: '12px', padding: '24px' }}>
              <div style={{ color: '#9a8acc', fontSize: '0.75rem', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '20px' }}>
                ◈ 出生时间校对
              </div>

              {/* 大致时间（可选） */}
              <div style={{ marginBottom: '16px' }}>
                <div style={labelStyle}>大致出生时间（可选）</div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <input type="number" min="0" max="23" placeholder="小时 0-23"
                    value={approxHour} onChange={e => setApproxHour(e.target.value)}
                    style={{ ...inputSm, width: '110px' }} />
                  <input type="number" min="0.5" max="12" step="0.5" placeholder="范围 ± 小时"
                    value={timeRangeHours} onChange={e => setTimeRangeHours(e.target.value)}
                    style={{ ...inputSm, width: '110px' }} />
                  <span style={{ color: '#555577', fontSize: '0.75rem' }}>不填 = 全天扫描</span>
                </div>
              </div>

              {/* 事件向导 */}
              {rectifyWizardStep <= 5 && (() => {
                const domain = RECTIFY_DOMAINS[rectifyWizardStep]
                const domEvents = rectifyEvents.filter(e => e.domainId === domain.id)
                return (
                  <div style={{ marginBottom: '12px' }}>
                    {/* 进度条 */}
                    <div style={{ display: 'flex', gap: '3px', marginBottom: '14px' }}>
                      {RECTIFY_DOMAINS.map((_, i) => (
                        <div key={i} style={{ flex: 1, height: '3px', borderRadius: '2px', backgroundColor: i < rectifyWizardStep ? '#7a6aaa' : i === rectifyWizardStep ? '#c9a84c' : '#2a2a5a', cursor: i < rectifyWizardStep ? 'pointer' : 'default' }}
                          onClick={() => { if (i < rectifyWizardStep) { setRectifyWizardStep(i); setCurrentDomainEvent(null) } }} />
                      ))}
                    </div>
                    {/* 域标签 + 问题 */}
                    <div style={{ color: '#c9a84c', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '5px' }}>
                      {rectifyWizardStep + 1} / {RECTIFY_DOMAINS.length} · {domain.label}
                    </div>
                    <div style={{ color: '#d0d0e0', fontSize: '0.88rem', marginBottom: '12px' }}>{domain.question}</div>
                    {/* 已填事件 */}
                    {domEvents.map(ev => {
                      const gi = rectifyEvents.indexOf(ev)
                      const typeLabel = domain.types.find(t => t.value === ev.event_type)?.label || ev.event_type
                      return (
                        <div key={gi} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px', padding: '6px 10px', background: '#1a1a30', borderRadius: '6px' }}>
                          <span style={{ color: '#9a8acc', fontSize: '0.8rem', flex: 1 }}>
                            {ev.year}{ev.month ? `/${String(ev.month).padStart(2,'0')}${ev.day ? `/${String(ev.day).padStart(2,'0')}` : ''}` : ' (仅年份)'} · {typeLabel}
                          </span>
                          <button onClick={() => removeEvent(gi)} style={{ background: 'none', border: 'none', color: '#4a3a5a', cursor: 'pointer', fontSize: '0.8rem', padding: '0 2px' }}
                            onMouseEnter={e => e.currentTarget.style.color = '#cc6666'}
                            onMouseLeave={e => e.currentTarget.style.color = '#4a3a5a'}>✕</button>
                        </div>
                      )
                    })}
                    {/* 填写表单 */}
                    {currentDomainEvent ? (
                      <div style={{ marginTop: '8px' }}>
                        <div style={{ display: 'flex', gap: '6px', marginBottom: '6px', flexWrap: 'wrap' }}>
                          <input type="number" placeholder="年 *" value={currentDomainEvent.year}
                            onChange={e => setCurrentDomainEvent(p => ({ ...p, year: e.target.value }))}
                            style={{ ...inputSm, width: '62px' }} />
                          <input type="number" placeholder="月" min="1" max="12" value={currentDomainEvent.month}
                            onChange={e => setCurrentDomainEvent(p => ({ ...p, month: e.target.value, day: '' }))}
                            style={{ ...inputSm, width: '46px' }} />
                          {currentDomainEvent.month && (
                            <input type="number" placeholder="日" min="1" max="31" value={currentDomainEvent.day}
                              onChange={e => setCurrentDomainEvent(p => ({ ...p, day: e.target.value }))}
                              style={{ ...inputSm, width: '46px' }} />
                          )}
                          <select value={currentDomainEvent.event_type}
                            onChange={e => setCurrentDomainEvent(p => ({ ...p, event_type: e.target.value }))}
                            style={{ ...inputSm, flex: 1, minWidth: '120px' }}>
                            {domain.types.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                          </select>
                          <select value={currentDomainEvent.weight}
                            onChange={e => setCurrentDomainEvent(p => ({ ...p, weight: Number(e.target.value) }))}
                            style={{ ...inputSm, width: '78px' }}>
                            <option value={1}>一般</option>
                            <option value={2}>重要</option>
                            <option value={3}>非常重要</option>
                          </select>
                        </div>
                        {currentDomainEvent.year && !currentDomainEvent.month && (
                          <div style={{ color: '#7a6a3a', fontSize: '0.72rem', marginBottom: '6px' }}>
                            仅填年份时权重降至 40%，填月份可提升至 70%
                          </div>
                        )}
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => {
                              if (!currentDomainEvent.year) return
                              setRectifyEvents(prev => [...prev, { ...currentDomainEvent }])
                              setCurrentDomainEvent(null)
                            }}
                            style={{ flex: 1, padding: '7px', background: '#2a2a5a', border: '1px solid #4a4a8a', color: '#d0d0f0', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem' }}>
                            保存
                          </button>
                          <button onClick={() => setCurrentDomainEvent(null)}
                            style={{ padding: '7px 14px', background: 'none', border: '1px solid #3a3a5a', color: '#7a7a9a', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem' }}>
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
                        <button
                          onClick={() => setCurrentDomainEvent({ year: '', month: '', day: '', event_type: domain.types[0].value, weight: 2, domainId: domain.id, is_turning_point: false })}
                          style={{ padding: '8px 12px', background: '#1e1e40', border: '1px solid #4a4a8a', color: '#c0c0e0', borderRadius: '6px', cursor: 'pointer', fontSize: '0.84rem', textAlign: 'left' }}>
                          {domEvents.length > 0 ? '+ 继续添加此领域事件' : '填写事件'}
                        </button>
                        {domEvents.length === 0 && (<>
                          <button onClick={() => { setRectifyWizardStep(s => s + 1); setCurrentDomainEvent(null) }}
                            style={{ padding: '8px 12px', background: 'none', border: '1px solid #2a2a5a', color: '#7a7a9a', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem', textAlign: 'left' }}>
                            此领域无重大事件
                          </button>
                          <button onClick={() => { setRectifyWizardStep(s => s + 1); setCurrentDomainEvent(null) }}
                            style={{ padding: '8px 12px', background: 'none', border: '1px solid #2a2a5a', color: '#5a5a7a', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem', textAlign: 'left' }}>
                            此领域有经历，但不便透露
                          </button>
                        </>)}
                        {domEvents.length > 0 && (
                          <button onClick={() => { setRectifyWizardStep(s => s + 1); setCurrentDomainEvent(null) }}
                            style={{ padding: '8px 12px', background: '#1e1a38', border: '1px solid #7a6aaa', color: '#c0b0e0', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 }}>
                            下一领域 →
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )
              })()}

              {/* 转折点选择 */}
              {rectifyWizardStep === 6 && (() => {
                const validEvents = rectifyEvents.filter(e => e.year && e.month && e.day)
                const tpCount = validEvents.filter(e => e.is_turning_point).length
                return (
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ color: '#c9a84c', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px' }}>
                      标记人生转折点
                    </div>
                    {validEvents.length === 0 ? (
                      <p style={{ color: '#7a7a9a', fontSize: '0.82rem', marginBottom: '10px' }}>未填写任何事件，请返回补充。</p>
                    ) : (<>
                      <div style={{ color: '#9a8acc', fontSize: '0.78rem', marginBottom: '10px' }}>
                        哪些事件从根本上改变了你的人生方向或自我认知？（通常 1–3 个）
                      </div>
                      {validEvents.map(ev => {
                        const gi = rectifyEvents.indexOf(ev)
                        const domain = RECTIFY_DOMAINS.find(d => d.id === ev.domainId)
                        const typeLabel = domain?.types.find(t => t.value === ev.event_type)?.label || ev.event_type
                        const isTP = ev.is_turning_point
                        return (
                          <div key={gi} onClick={() => updateEvent(gi, 'is_turning_point', !isTP)}
                            style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '5px', padding: '8px 12px', background: isTP ? '#1e1a38' : '#14142a', border: `1px solid ${isTP ? '#7a6aaa' : '#2a2a5a'}`, borderRadius: '8px', cursor: 'pointer' }}>
                            <div style={{ width: '14px', height: '14px', borderRadius: '3px', border: `2px solid ${isTP ? '#9a8acc' : '#4a4a6a'}`, background: isTP ? '#7a6aaa' : 'transparent', flexShrink: 0 }} />
                            <div style={{ flex: 1 }}>
                              <span style={{ color: '#d0d0e0', fontSize: '0.82rem' }}>{ev.year}/{String(ev.month).padStart(2,'0')}/{String(ev.day).padStart(2,'0')} · {typeLabel}</span>
                              {domain && <span style={{ color: '#5a5a7a', fontSize: '0.72rem', marginLeft: '6px' }}>{domain.label}</span>}
                            </div>
                          </div>
                        )
                      })}
                      {tpCount > 4 && (
                        <div style={{ color: '#c9a84c', fontSize: '0.78rem', marginTop: '8px', padding: '6px 10px', background: '#1a1600', borderRadius: '6px', border: '1px solid #3a3000' }}>
                          转折点越集中，校对越精准。确定这些都是根本性的转变吗？
                        </div>
                      )}
                    </>)}
                    <button onClick={() => { setRectifyWizardStep(0); setCurrentDomainEvent(null) }}
                      style={{ marginTop: '10px', background: 'none', border: 'none', color: '#5a5a7a', cursor: 'pointer', fontSize: '0.78rem', padding: '0' }}>
                      ← 返回修改事件
                    </button>
                  </div>
                )
              })()}

              {rectifyWizardStep === 6 && (
                <button onClick={handleRectify} disabled={rectifyLoading || rectifyEvents.filter(e => e.year && e.month && e.day).length === 0}
                  style={{ width: '100%', padding: '10px', marginTop: '8px', background: rectifyLoading ? '#1e1e3a' : '#7a6aaa', color: rectifyLoading ? '#3a3a5a' : '#ffffff', border: 'none', borderRadius: '8px', fontWeight: 700, cursor: (rectifyLoading || rectifyEvents.filter(e => e.year && e.month && e.day).length === 0) ? 'not-allowed' : 'pointer', fontSize: '0.9rem' }}>
                  {rectifyLoading ? '扫描中… 约 25-40 秒' : '开始校对'}
                </button>
              )}

              {rectifyError && <p style={{ color: '#ff7070', fontSize: '0.88rem', marginTop: '10px' }}>{rectifyError}</p>}

              {rectifyResult && !rectifyLoading && (
                <div style={{ marginTop: '20px', borderTop: '1px solid #2a2a4a', paddingTop: '20px' }}>
                  <div style={{ color: '#9a8acc', fontSize: '0.75rem', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '14px' }}>
                    Top 3 候选时间
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
                    {rectifyResult.top3.map((t, i) => (
                      <div key={i} style={{ background: i === 0 ? '#1e1a38' : '#14142a', border: `1px solid ${i === 0 ? '#7a6aaa' : '#2a2a5a'}`, borderRadius: '10px', padding: '16px 18px' }}>
                        {/* 头部：时间 + 标签 */}
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: t.reason ? '12px' : '0' }}>
                          <span style={{ color: '#e0e0f0', fontSize: '1.4rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                            {String(t.hour).padStart(2, '0')}:{String(t.minute).padStart(2, '0')}
                          </span>
                          {t.asc_sign && (
                            <span style={{ color: '#8888aa', fontSize: '0.82rem' }}>上升 {t.asc_sign}</span>
                          )}
                          <span style={{ marginLeft: 'auto', color: i === 0 ? '#c9a84c' : '#7a6aaa', fontSize: '0.72rem', fontWeight: 600 }}>
                            {i === 0 ? '★ 推荐' : `候选 ${i + 1}`}
                          </span>
                          <span style={{ color: '#555577', fontSize: '0.72rem' }}>评分 {t.score}</span>
                        </div>
                        {/* 分析理由（Markdown） */}
                        {t.reason && (
                          <div style={{ borderTop: '1px solid #2a2a4a', paddingTop: '10px', color: '#b0b0cc', fontSize: '0.88rem', lineHeight: 1.85 }}>
                            <ReactMarkdown components={{
                              p: ({children}) => <p style={{ margin: '0 0 0.5em', color: '#b0b0cc' }}>{children}</p>,
                              strong: ({children}) => <strong style={{ color: '#e0d0ff', fontWeight: 600 }}>{children}</strong>,
                              em: ({children}) => <em style={{ color: '#c9a84c', fontStyle: 'normal' }}>{children}</em>,
                              ul: ({children}) => <ul style={{ paddingLeft: '1.2em', margin: '0.4em 0' }}>{children}</ul>,
                              li: ({children}) => <li style={{ marginBottom: '0.3em', color: '#b0b0cc' }}>{children}</li>,
                            }}>{t.reason}</ReactMarkdown>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  {/* 综合分析（Markdown） */}
                  {rectifyResult.overall && (
                    <div style={{ background: '#0f0f28', border: '1px solid #3a3a6a', borderRadius: '10px', padding: '16px 18px' }}>
                      <div style={{ color: '#9a8acc', fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '10px' }}>综合推荐与验证建议</div>
                      <div style={{ color: '#d0d0e8', fontSize: '0.9rem', lineHeight: 1.85 }}>
                        <ReactMarkdown components={{
                          p: ({children}) => <p style={{ margin: '0 0 0.6em', color: '#d0d0e8' }}>{children}</p>,
                          strong: ({children}) => <strong style={{ color: '#e0d0ff', fontWeight: 600 }}>{children}</strong>,
                          em: ({children}) => <em style={{ color: '#c9a84c', fontStyle: 'normal' }}>{children}</em>,
                          ul: ({children}) => <ul style={{ paddingLeft: '1.2em', margin: '0.4em 0' }}>{children}</ul>,
                          li: ({children}) => <li style={{ marginBottom: '0.3em', color: '#d0d0e8' }}>{children}</li>,
                        }}>{rectifyResult.overall}</ReactMarkdown>
                      </div>
                    </div>
                  )}
                  {/* 进入第二阶段按钮 */}
                  {!ascQuizData && !ascQuizLoading && (
                    <button
                      onClick={() => handleLoadAscQuiz(rectifyResult.top3)}
                      style={{
                        marginTop: '16px', width: '100%', padding: '11px',
                        background: 'linear-gradient(135deg, #2a1a4a, #1a1a3a)',
                        border: '1px solid #7a6aaa', borderRadius: '8px',
                        color: '#c9a84c', fontWeight: 700, fontSize: '0.88rem',
                        cursor: 'pointer', letterSpacing: '0.05em',
                      }}>
                      ✦ 进入第二阶段：上升星座性格验证 →
                    </button>
                  )}
                </div>
              )}

              {/* ── Phase 2: 上升星座性格问卷 ── */}
              {(ascQuizLoading || ascQuizData) && (
                <div style={{ marginTop: '24px', borderTop: '1px solid #2a2a4a', paddingTop: '20px' }}>
                  <div style={{ color: '#c9a84c', fontSize: '0.78rem', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '14px' }}>
                    第二阶段 · 上升星座性格验证
                  </div>
                  {ascQuizLoading ? (
                    <div style={{ color: '#5a5a8a', fontSize: '0.85rem' }}>正在生成问卷…</div>
                  ) : (
                    <>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {ascQuizData.map(q => (
                          <div key={q.id}>
                            <div style={{ color: '#d0d0e8', fontSize: '0.88rem', marginBottom: '8px', fontWeight: 500 }}>{q.text}</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              {q.options.map(opt => (
                                <label key={opt.id} style={{
                                  display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
                                  padding: '8px 12px', borderRadius: '7px',
                                  background: ascQuizAnswers[q.id]?.id === opt.id ? '#1e1a38' : '#0e0e22',
                                  border: `1px solid ${ascQuizAnswers[q.id]?.id === opt.id ? '#7a6aaa' : '#2a2a4a'}`,
                                  fontSize: '0.83rem', color: '#c0c0e0',
                                }}>
                                  <input type="radio" name={q.id} value={opt.id}
                                    checked={ascQuizAnswers[q.id]?.id === opt.id}
                                    onChange={() => handleAscAnswer(q.id, opt)}
                                    style={{ accentColor: '#7a6aaa' }} />
                                  {opt.text}
                                </label>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                      {ascQuizData.length > 0 && (
                        <button
                          onClick={handleSubmitAscQuiz}
                          disabled={Object.keys(ascQuizAnswers).length < ascQuizData.length}
                          style={{
                            marginTop: '16px', width: '100%', padding: '10px',
                            background: Object.keys(ascQuizAnswers).length < ascQuizData.length ? '#1e1e3a' : '#7a6aaa',
                            color: Object.keys(ascQuizAnswers).length < ascQuizData.length ? '#3a3a5a' : '#fff',
                            border: 'none', borderRadius: '8px', fontWeight: 700, cursor: 'pointer', fontSize: '0.88rem',
                          }}>
                          提交 → 确定推荐时间
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ── Phase 2 结果：推荐候选 ── */}
              {recommendedIdx !== null && rectifyResult?.top3 && (
                <div style={{ marginTop: '16px', background: '#1a2a1a', border: '1px solid #3a6a3a', borderRadius: '10px', padding: '14px 16px' }}>
                  <div style={{ color: '#88cc88', fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px' }}>性格匹配推荐</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <span style={{ color: '#e0f0e0', fontSize: '1.3rem', fontWeight: 700 }}>
                      {String(rectifyResult.top3[recommendedIdx].hour).padStart(2, '0')}:{String(rectifyResult.top3[recommendedIdx].minute).padStart(2, '0')}
                    </span>
                    <span style={{ color: '#88aa88', fontSize: '0.82rem' }}>上升 {rectifyResult.top3[recommendedIdx].asc_sign}</span>
                    <span style={{ marginLeft: 'auto', color: '#66bb66', fontSize: '0.72rem', fontWeight: 600 }}>✓ 性格最匹配</span>
                  </div>
                </div>
              )}

              {/* ── Phase 3: 生命主题问卷 ── */}
              {themeQuizData && recommendedIdx !== null && (
                <div style={{ marginTop: '24px', borderTop: '1px solid #2a2a4a', paddingTop: '20px' }}>
                  <div style={{ color: '#c9a84c', fontSize: '0.78rem', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '14px' }}>
                    第三阶段 · 生命主题置信度验证
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {themeQuizData.map(q => (
                      <div key={q.id}>
                        <div style={{ color: '#d0d0e8', fontSize: '0.88rem', marginBottom: '8px', fontWeight: 500 }}>{q.text}</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {q.options.map(opt => (
                            <label key={opt.id} style={{
                              display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
                              padding: '8px 12px', borderRadius: '7px',
                              background: themeAnswers[q.id]?.id === opt.id ? '#1a1e30' : '#0e0e22',
                              border: `1px solid ${themeAnswers[q.id]?.id === opt.id ? '#4a6aaa' : '#2a2a4a'}`,
                              fontSize: '0.83rem', color: '#c0c0e0',
                            }}>
                              <input type="radio" name={`theme_${q.id}`} value={opt.id}
                                checked={themeAnswers[q.id]?.id === opt.id}
                                onChange={() => setThemeAnswers(prev => ({ ...prev, [q.id]: opt }))}
                                style={{ accentColor: '#4a6aaa' }} />
                              {opt.text}
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={handleSubmitThemeQuiz}
                    disabled={confidenceLoading || Object.keys(themeAnswers).length < themeQuizData.length}
                    style={{
                      marginTop: '16px', width: '100%', padding: '10px',
                      background: confidenceLoading || Object.keys(themeAnswers).length < themeQuizData.length ? '#1e1e3a' : '#4a6aaa',
                      color: confidenceLoading || Object.keys(themeAnswers).length < themeQuizData.length ? '#3a3a5a' : '#fff',
                      border: 'none', borderRadius: '8px', fontWeight: 700, cursor: 'pointer', fontSize: '0.88rem',
                    }}>
                    {confidenceLoading ? '评估中…' : '提交 → 计算置信度'}
                  </button>
                </div>
              )}

              {/* ── Phase 3 结果：置信度 ── */}
              {confidenceResult && (
                <div style={{ marginTop: '20px', background: '#0f0f28', border: '1px solid #3a4a6a', borderRadius: '10px', padding: '16px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                    <div style={{ color: '#9a8acc', fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>置信度评估</div>
                    <div style={{
                      marginLeft: 'auto', padding: '4px 14px', borderRadius: '20px', fontWeight: 700, fontSize: '0.9rem',
                      background: confidenceResult.score >= 70 ? '#1a3a1a' : confidenceResult.score >= 40 ? '#2a2a1a' : '#2a1a1a',
                      color: confidenceResult.score >= 70 ? '#66cc66' : confidenceResult.score >= 40 ? '#ccaa44' : '#cc6666',
                      border: `1px solid ${confidenceResult.score >= 70 ? '#3a6a3a' : confidenceResult.score >= 40 ? '#5a5a2a' : '#5a2a2a'}`,
                    }}>
                      {confidenceResult.label} · {confidenceResult.score}分
                    </div>
                  </div>
                  <div style={{ color: '#d0d0e8', fontSize: '0.9rem', lineHeight: 1.85 }}>
                    <ReactMarkdown components={{
                      p: ({children}) => <p style={{ margin: '0 0 0.6em', color: '#d0d0e8' }}>{children}</p>,
                      strong: ({children}) => <strong style={{ color: '#e0d0ff', fontWeight: 600 }}>{children}</strong>,
                      em: ({children}) => <em style={{ color: '#c9a84c', fontStyle: 'normal' }}>{children}</em>,
                      ul: ({children}) => <ul style={{ paddingLeft: '1.2em', margin: '0.4em 0' }}>{children}</ul>,
                      li: ({children}) => <li style={{ marginBottom: '0.3em', color: '#d0d0e8' }}>{children}</li>,
                    }}>{confidenceResult.analysis}</ReactMarkdown>
                  </div>
                </div>
              )}

            </div>
          )}
        </div>

      </div>
    </div>
  )
}
