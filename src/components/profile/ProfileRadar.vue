<template>
  <section class="radar">
    <header class="radar__head">
      <div>
        <p class="radar__title">能力画像</p>
        <p class="radar__sub">{{ state.hasProfile ? '六维自评 · 随画像更新' : '答完画像才有雷达图' }}</p>
      </div>
      <span class="radar__score">{{ avgScore }}</span>
    </header>

    <svg class="radar__svg" viewBox="0 0 220 200">
      <!-- 网格 -->
      <g v-for="ring in 4" :key="ring">
        <polygon :points="ringPoints(ring / 4)" fill="none" stroke="#eef1f7" stroke-width="1" />
      </g>
      <!-- 轴线 -->
      <line v-for="(d, i) in axes" :key="'ax' + i"
            :x1="cx" :y1="cy" :x2="d.x" :y2="d.y" stroke="#eef1f7" stroke-width="1" />
      <!-- 数据多边形 -->
      <polygon :points="dataPoints" fill="rgba(37,99,235,0.16)" stroke="#2563eb" stroke-width="2"
               stroke-linejoin="round" class="radar__poly" />
      <!-- 顶点 -->
      <circle v-for="(d, i) in dataAxes" :key="'pt' + i" :cx="d.x" :cy="d.y" r="3"
              :fill="d.value < 40 ? '#c41e3a' : '#2563eb'" />
      <!-- 轴标签 -->
      <text v-for="(d, i) in axes" :key="'lb' + i" :x="d.lx" :y="d.ly"
            class="radar__label" text-anchor="middle">{{ d.label }}</text>
    </svg>

    <ul class="radar__list">
      <li v-for="d in dims" :key="d.label" :class="{ low: d.value < 40 }">
        <span class="radar__dot" :style="{ background: d.value < 40 ? '#c41e3a' : '#2563eb' }"></span>
        <span class="radar__name">{{ d.label }}</span>
        <span class="radar__val">{{ d.value }}</span>
        <span v-if="d.value < 40" class="radar__flag">待补</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const cx = 110
const cy = 96
const R = 74
const LABELS = ['基础水平', '时间投入', '目标清晰', '弱项认知', '自我表达', '计划执行']

const state = reactive({
  hasProfile: false,
  profile: null,
  planPercent: 0,
})

const clamp = (n) => Math.max(6, Math.min(100, Math.round(n)))

const dims = computed(() => {
  const p = state.profile || {}
  const levelMap = { '零基础': 15, '了解一点': 35, '有基础': 60, '比较稳': 80, '冲刺提分': 90 }
  const level = levelMap[p.self_level] ?? 30
  const hours = clamp(((Number(p.daily_hours) || 0) / 10) * 100)
  const goalSig = (p.target_score ? 40 : 0) + (p.exam_date ? 40 : 0) + (p.target_post || p.target_region ? 20 : 0)
  const weak = Array.isArray(p.subject_weaknesses) ? p.subject_weaknesses.length : 0
  const weakScore = clamp(weak * 25)
  const intro = String(p.self_intro || '').length
  const introScore = clamp((intro / 120) * 100)
  const plan = clamp(state.planPercent)
  return [
    { label: LABELS[0], value: clamp(level) },
    { label: LABELS[1], value: hours },
    { label: LABELS[2], value: clamp(goalSig) },
    { label: LABELS[3], value: weakScore },
    { label: LABELS[4], value: introScore },
    { label: LABELS[5], value: plan },
  ]
})

const avgScore = computed(() => {
  const v = dims.value.map((d) => d.value)
  return Math.round(v.reduce((s, x) => s + x, 0) / v.length)
})

function angleOf(i, total) {
  return (Math.PI * 2 * i) / total - Math.PI / 2
}

const axes = computed(() =>
  LABELS.map((label, i) => {
    const a = angleOf(i, LABELS.length)
    return {
      label,
      x: cx + Math.cos(a) * R,
      y: cy + Math.sin(a) * R,
      lx: cx + Math.cos(a) * (R + 18),
      ly: cy + Math.sin(a) * (R + 18) + 3,
    }
  })
)

const dataAxes = computed(() =>
  dims.value.map((d, i) => {
    const a = angleOf(i, dims.value.length)
    const r = (Math.max(0, d.value) / 100) * R
    return { value: d.value, x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r }
  })
)

const dataPoints = computed(() => dataAxes.value.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' '))

function ringPoints(ratio) {
  return LABELS.map((_, i) => {
    const a = angleOf(i, LABELS.length)
    return `${(cx + Math.cos(a) * R * ratio).toFixed(1)},${(cy + Math.sin(a) * R * ratio).toFixed(1)}`
  }).join(' ')
}

function getToken() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) {
      const o = JSON.parse(raw)
      if (o && o.token) return o.token
    }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

function parseMaybeJson(v) {
  if (Array.isArray(v)) return v
  if (typeof v === 'string' && v.trim().startsWith('[')) {
    try { return JSON.parse(v) } catch (e) { return [] }
  }
  return []
}

onMounted(async () => {
  const token = getToken()
  if (!token) return
  const H = { Authorization: 'Bearer ' + token }
  try {
    const [pr, pl] = await Promise.all([
      fetch('/api/profile', { headers: H }),
      fetch('/api/plan/current', { headers: H }),
    ])
    const pd = await pr.json()
    if (pr.ok && pd && pd.has_profile !== false) {
      state.hasProfile = true
      state.profile = { ...pd, subject_weaknesses: parseMaybeJson(pd.subject_weaknesses) }
    }
    const pld = await pl.json()
    state.planPercent = pld?.progress?.percent || 0
  } catch (e) { /* 静默降级 */ }
})
</script>

<style scoped>
.radar {
  padding: 16px 18px; border-radius: 18px;
  background: linear-gradient(150deg, #fff, #f7f9ff);
  border: 1px solid #e8ecfa;
}
.radar__head { display: flex; align-items: flex-start; justify-content: space-between; }
.radar__title { margin: 0; font-size: 14px; font-weight: 700; color: #111827; }
.radar__sub { margin: 3px 0 0; font-size: 11px; color: #9ca3af; }
.radar__score { font-size: 22px; font-weight: 800; color: #2563eb; line-height: 1; }

.radar__svg { display: block; width: 100%; height: 210px; margin-top: 4px; }
.radar__poly { animation: grow 700ms cubic-bezier(0.22, 1, 0.36, 1) both; transform-origin: 110px 96px; }
@keyframes grow { from { opacity: 0; transform: scale(0.55); } to { opacity: 1; transform: scale(1); } }
.radar__label { font-size: 9px; fill: #9ca3af; }

.radar__list { list-style: none; margin: 8px 0 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; }
.radar__list li { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #4b5563; }
.radar__dot { width: 6px; height: 6px; border-radius: 50%; }
.radar__name { flex: 1; }
.radar__val { font-weight: 700; color: #374151; }
.radar__list li.low .radar__val { color: #c41e3a; }
.radar__flag { font-size: 10px; color: #c41e3a; background: rgba(196, 30, 58, 0.08); padding: 1px 6px; border-radius: 999px; }

@media (prefers-reduced-motion: reduce) {
  .radar__poly { animation: none; }
}
</style>
