<template>
  <section class="heat">
    <header class="heat__head">
      <div>
        <p class="heat__title">专注力热力图</p>
        <p class="heat__sub">最近 {{ state.weeks }} 周 · 累计 {{ hours }} 小时 · {{ state.sessionCount }} 次专注</p>
      </div>
      <span class="heat__best" v-if="state.bestSlot.weekday !== null">
        最强时段 {{ weekName(state.bestSlot.weekday) }} {{ pad(state.bestSlot.hour) }}:00
      </span>
    </header>

    <div v-if="state.loading" class="heat__skeleton"></div>

    <div v-else-if="state.total === 0" class="heat__empty">
      <p>还没有专注记录</p>
      <p class="heat__empty-tip">点右下角番茄钟，专注 25 分钟就会在这里留一格</p>
    </div>

    <div v-else class="heat__grid-wrap">
      <div class="heat__hours">
        <span v-for="h in 24" :key="h" class="heat__hour">{{ (h - 1) % 6 === 0 ? (h - 1) : '' }}</span>
      </div>
      <div class="heat__grid">
        <template v-for="wd in 7" :key="wd">
          <span class="heat__day">{{ weekName(wd - 1) }}</span>
          <span v-for="h in 24" :key="wd + '-' + h"
                class="heat__cell"
                :style="{ background: cellColor(wd - 1, h - 1) }"
                :title="weekName(wd - 1) + ' ' + pad(h - 1) + ':00 · ' + (state.matrix[wd - 1][h - 1] || 0) + ' 分钟'"></span>
        </template>
      </div>
    </div>

    <div v-if="state.total > 0" class="heat__legend">
      <span>少</span>
      <i v-for="n in 5" :key="n" :style="{ background: levelColor(n - 1) }"></i>
      <span>多</span>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const state = reactive({
  loading: true,
  weeks: 4,
  matrix: Array.from({ length: 7 }, () => new Array(24).fill(0)),
  total: 0,
  sessionCount: 0,
  bestSlot: { weekday: null, hour: null, minutes: 0 },
})

const NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const LEVELS = ['#eef1f7', '#c9d7ff', '#9db4ff', '#6d8cff', '#3f63f5']

const hours = computed(() => Math.round(state.total / 60))

function weekName(i) { return NAMES[i] || '' }
function pad(n) { return String(n).padStart(2, '0') }

function levelOf(minutes) {
  if (!minutes) return 0
  if (minutes < 15) return 1
  if (minutes < 40) return 2
  if (minutes < 90) return 3
  return 4
}
function levelColor(level) { return LEVELS[level] || LEVELS[0] }
function cellColor(wd, hr) { return levelColor(levelOf(state.matrix[wd]?.[hr] || 0)) }

function token() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

onMounted(async () => {
  const t = token()
  if (!t) { state.loading = false; return }
  try {
    const res = await fetch('/api/v1/growth/focus/heatmap?weeks=4', {
      headers: { Authorization: 'Bearer ' + t },
    })
    const d = await res.json()
    if (Array.isArray(d.matrix)) state.matrix = d.matrix
    state.total = d.total_minutes || 0
    state.sessionCount = d.session_count || 0
    state.bestSlot = d.best_slot || state.bestSlot
    state.weeks = d.weeks || 4
  } catch (e) { /* 静默降级为空图 */ }
  finally { state.loading = false }
})
</script>

<style scoped>
.heat { margin: 12px 0 0; padding: 16px 18px; border-radius: 12px; background: #fff; border: 1px solid #eef1f7; box-shadow: 0 1px 4px rgba(17,24,39,.06); }
.heat__head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.heat__title { margin: 0; font-size: 14px; font-weight: 700; color: #1a2b5f; }
.heat__sub { margin: 3px 0 0; font-size: 11.5px; color: #8a8faa; }
.heat__best { font-size: 11px; color: #c41e3a; background: rgba(196,30,58,.08); padding: 3px 9px; border-radius: 999px; }
.heat__hours { display: grid; grid-template-columns: 32px repeat(24, 1fr); font-size: 9px; color: #b6bcc8; }
.heat__hour { text-align: center; }
.heat__grid { display: grid; grid-template-columns: 32px repeat(24, 1fr); gap: 2px; align-items: center; }
.heat__day { font-size: 10px; color: #9aa0aa; }
.heat__cell { display: block; height: 14px; border-radius: 3px; transition: transform 120ms ease; }
.heat__cell:hover { transform: scale(1.25); }
.heat__legend { display: flex; align-items: center; gap: 4px; justify-content: flex-end; margin-top: 8px; font-size: 10px; color: #b6bcc8; }
.heat__legend i { width: 12px; height: 10px; border-radius: 2px; display: inline-block; }
.heat__empty { padding: 14px 0 6px; text-align: center; }
.heat__empty p { margin: 0; font-size: 12px; color: #9aa0aa; }
.heat__empty-tip { margin-top: 4px !important; font-size: 11px !important; color: #c2c7cf !important; }
.heat__skeleton { height: 110px; border-radius: 8px; background: #f3f5f9; }
@media (max-width: 900px) { .heat__cell { height: 11px; } }
@media (prefers-reduced-motion: reduce) { .heat__cell { transition: none; } }
</style>
