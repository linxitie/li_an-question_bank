<template>
  <!-- 无错题时整块隐藏，避免与上方的复习引导卡重复 -->
  <section v-if="state.loading || state.items.length > 0" class="mc">
    <header class="mc__head">
      <div>
        <p class="mc__title">记忆强度</p>
        <p class="mc__sub">{{ subtitle }}</p>
      </div>
      <span class="mc__badge">{{ state.items.length }} 题待复习</span>
    </header>

    <div v-if="state.loading" class="mc__skeleton"></div>

    <div v-else-if="!state.items.length" class="mc__empty">
      <p>还没有需要复习的错题</p>
      <p class="mc__empty-tip">做几道题，答错的会自动进入遗忘曲线排程</p>
    </div>

    <svg v-else class="mc__chart" viewBox="0 0 320 120" preserveAspectRatio="none">
      <defs>
        <linearGradient id="mcFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#c41e3a" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#c41e3a" stop-opacity="0" />
        </linearGradient>
      </defs>
      <path :d="areaPath" fill="url(#mcFill)" />
      <path :d="linePath" fill="none" stroke="#c41e3a" stroke-width="1.8" stroke-linecap="round" />
      <circle v-for="(p, i) in points" :key="i" :cx="p.x" :cy="p.y" r="2.6" fill="#fff" stroke="#c41e3a" stroke-width="1.6" />
    </svg>

    <div v-if="state.items.length" class="mc__bars">
      <div v-for="b in buckets" :key="b.label" class="mc__bar">
        <div class="mc__bar-fill" :style="{ height: b.percent + '%' }" :class="{ 'is-danger': b.danger }"></div>
        <span class="mc__bar-label">{{ b.label }}</span>
        <span class="mc__bar-count">{{ b.count }}</span>
      </div>
    </div>

    <p v-if="state.items.length" class="mc__tip">{{ tip }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const state = reactive({ loading: true, items: [], summary: null })

const subtitle = computed(() => {
  if (!state.items.length) return '遗忘曲线排程'
  const avg = state.items.reduce((s, i) => s + (i.ease || 2.5), 0) / state.items.length
  return `平均难度因子 ${avg.toFixed(2)}（越高越稳）`
})

/** 按逾期天数分档，形成柱状分布 */
const buckets = computed(() => {
  const defs = [
    { label: '今天', test: (d) => d === 0, danger: false },
    { label: '1-2 天', test: (d) => d >= 1 && d <= 2, danger: false },
    { label: '3-6 天', test: (d) => d >= 3 && d <= 6, danger: true },
    { label: '7 天+', test: (d) => d >= 7, danger: true },
  ]
  const counts = defs.map((d) => state.items.filter((i) => d.test(i.overdue_days || 0)).length)
  const max = Math.max(1, ...counts)
  return defs.map((d, i) => ({
    label: d.label,
    count: counts[i],
    danger: d.danger,
    percent: Math.round((counts[i] / max) * 100),
  }))
})

const tip = computed(() => {
  const late = state.items.filter((i) => (i.overdue_days || 0) >= 3).length
  if (late >= 5) return `有 ${late} 题已经压了 3 天以上，先清它们，别攒`
  if (late > 0) return `${late} 题逾期较久，今天优先处理`
  return '排程健康，按节奏复习就好'
})

/** 把待复习题按逾期天数画成一条下坠曲线（逾期越久，记忆强度越低） */
const points = computed(() => {
  const sorted = [...state.items].sort((a, b) => (a.overdue_days || 0) - (b.overdue_days || 0))
  const n = Math.min(sorted.length, 12)
  return Array.from({ length: n }, (_, i) => {
    const item = sorted[Math.floor((i * sorted.length) / n)]
    const overdue = item.overdue_days || 0
    // 记忆强度：第一天 100%，之后按 ease 指数衰减，最低 15%
    const ease = item.ease || 2.5
    const strength = Math.max(0.15, Math.exp(-overdue / (ease * 2)))
    return { x: (i / Math.max(1, n - 1)) * 312 + 4, y: 112 - strength * 100 }
  })
})

const linePath = computed(() => points.value.map((p, i) => (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' '))
const areaPath = computed(() => linePath.value + ` L316 120 L4 120 Z`)

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

onMounted(async () => {
  const token = getToken()
  if (!token) { state.loading = false; return }
  try {
    const res = await fetch('/api/v1/growth/review/due?limit=60', {
      headers: { Authorization: 'Bearer ' + token },
    })
    const d = await res.json()
    state.items = d.items || []
  } catch (e) { /* 静默 */ }
  finally { state.loading = false }
})
</script>

<style scoped>
.mc {
  margin: 0 0 14px; padding: 16px 18px; border-radius: 18px;
  background: linear-gradient(150deg, #fff, #fff8f9);
  border: 1px solid #f6dfe4;
}
.mc__head { display: flex; align-items: flex-start; justify-content: space-between; }
.mc__title { margin: 0; font-size: 14px; font-weight: 700; color: #111827; }
.mc__sub { margin: 3px 0 0; font-size: 11px; color: #9ca3af; }
.mc__badge {
  font-size: 11px; font-weight: 700; color: #c41e3a;
  background: rgba(196, 30, 58, 0.08); padding: 3px 9px; border-radius: 999px;
}

.mc__chart { display: block; width: 100%; height: 96px; margin: 10px 0 4px; }

.mc__bars { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 6px; }
.mc__bar { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.mc__bar-fill {
  width: 100%; max-width: 34px; height: 0; min-height: 2px;
  border-radius: 6px 6px 2px 2px; background: #f3b6c1;
  transition: height 500ms cubic-bezier(0.22, 1, 0.36, 1);
}
.mc__bar-fill.is-danger { background: #c41e3a; }
.mc__bar-label { font-size: 10px; color: #9ca3af; }
.mc__bar-count { font-size: 11px; font-weight: 700; color: #4b5563; }

.mc__tip { margin: 10px 0 0; font-size: 11px; color: #b45309; }
.mc__empty { padding: 16px 0 6px; text-align: center; }
.mc__empty p { margin: 0; font-size: 12px; color: #9ca3af; }
.mc__empty-tip { margin-top: 4px !important; font-size: 11px !important; color: #c7cbd4 !important; }
.mc__skeleton { height: 96px; border-radius: 10px; background: #f6eef0; }

@media (prefers-reduced-motion: reduce) {
  .mc__bar-fill { transition: none; }
}
</style>
