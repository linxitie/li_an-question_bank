<template>
  <section class="wr">
    <header class="wr__head">
      <div>
        <p class="wr__title">学习周报</p>
        <p class="wr__sub">{{ rangeText }}</p>
      </div>
      <button class="wr__export" @click="exportPng">存成图片</button>
    </header>

    <div v-if="state.loading" class="wr__skeleton"></div>

    <div v-else class="wr__body">
      <div class="wr__stats">
        <div class="wr__stat" v-for="s in stats" :key="s.label">
          <span class="wr__num">{{ s.value }}</span>
          <span class="wr__label">{{ s.label }}</span>
        </div>
      </div>

      <div class="wr__bars">
        <div class="wr__bar" v-for="b in bars" :key="b.label">
          <span class="wr__bar-label">{{ b.label }}</span>
          <div class="wr__bar-track">
            <div class="wr__bar-fill" :style="{ width: b.percent + '%', background: b.color }"></div>
          </div>
          <span class="wr__bar-val">{{ b.text }}</span>
        </div>
      </div>

      <p class="wr__comment">{{ state.comment }}</p>
    </div>

    <canvas ref="canvasRef" class="wr__canvas"></canvas>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const canvasRef = ref(null)
const state = reactive({
  loading: true,
  weekStart: '',
  weekEnd: '',
  focusMinutes: 0,
  focusSessions: 0,
  bestHour: null,
  tasksTotal: 0,
  tasksDone: 0,
  completion: 0,
  wrongNew: 0,
  wrongReviewed: 0,
  comment: '',
  hasData: false,
})

const rangeText = computed(() =>
  state.weekStart ? state.weekStart + ' ~ ' + state.weekEnd : '本周还没开始统计'
)

const stats = computed(() => [
  { label: '专注时长', value: (state.focusMinutes / 60).toFixed(1) + 'h' },
  { label: '专注次数', value: state.focusSessions },
  { label: '任务完成', value: state.tasksDone + '/' + state.tasksTotal },
  { label: '新错题', value: state.wrongNew },
])

const bars = computed(() => [
  { label: '任务完成率', percent: state.completion, text: state.completion + '%', color: '#c41e3a' },
  {
    label: '专注目标',
    percent: Math.min(100, Math.round((state.focusMinutes / 300) * 100)),
    text: Math.min(100, Math.round((state.focusMinutes / 300) * 100)) + '%',
    color: '#2563eb',
  },
  {
    label: '错题复习',
    percent: state.wrongNew ? Math.min(100, Math.round((state.wrongReviewed / Math.max(1, state.wrongNew)) * 100)) : 0,
    text: state.wrongReviewed + '/' + state.wrongNew,
    color: '#10b981',
  },
])

function token() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

function exportPng() {
  const canvas = canvasRef.value
  if (!canvas) return
  const W = 720
  const H = 420
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  const g = ctx.createLinearGradient(0, 0, W, H)
  g.addColorStop(0, '#ffffff')
  g.addColorStop(1, '#f6f8ff')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, W, H)

  ctx.fillStyle = '#1a2b5f'
  ctx.font = 'bold 26px "PingFang SC", "Microsoft YaHei", sans-serif'
  ctx.fillText('学习周报', 40, 66)
  ctx.fillStyle = '#8a8faa'
  ctx.font = '14px "PingFang SC", "Microsoft YaHei", sans-serif'
  ctx.fillText(rangeText.value || '本周', 40, 92)

  const items = [
    ['专注时长', (state.focusMinutes / 60).toFixed(1) + ' 小时'],
    ['专注次数', state.focusSessions + ' 次'],
    ['任务完成', state.tasksDone + ' / ' + state.tasksTotal],
    ['新错题', state.wrongNew + ' 道'],
  ]
  items.forEach((it, i) => {
    const x = 40 + (i % 2) * 330
    const y = 150 + Math.floor(i / 2) * 84
    ctx.fillStyle = '#c41e3a'
    ctx.font = 'bold 30px "PingFang SC", "Microsoft YaHei", sans-serif'
    ctx.fillText(String(it[1]), x, y)
    ctx.fillStyle = '#8a8faa'
    ctx.font = '13px "PingFang SC", "Microsoft YaHei", sans-serif'
    ctx.fillText(it[0], x, y + 22)
  })

  ctx.fillStyle = '#374151'
  ctx.font = '14px "PingFang SC", "Microsoft YaHei", sans-serif'
  const text = state.comment || ''
  let line = ''
  let y = 340
  for (const ch of text) {
    if (ctx.measureText(line + ch).width > W - 80) { ctx.fillText(line, 40, y); line = ch; y += 24 }
    else line += ch
  }
  if (line) ctx.fillText(line, 40, y)

  ctx.fillStyle = '#b6bcc8'
  ctx.font = '11px sans-serif'
  ctx.fillText('砺安题库 · 联考小智', 40, H - 24)

  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = '学习周报-' + (state.weekStart || '本周') + '.png'
  a.click()
}

onMounted(async () => {
  const t = token()
  if (!t) { state.loading = false; return }
  try {
    const res = await fetch('/api/v1/growth/report/weekly?weeks_ago=0', {
      headers: { Authorization: 'Bearer ' + t },
    })
    const d = await res.json()
    state.weekStart = d.week_start || ''
    state.weekEnd = d.week_end || ''
    state.focusMinutes = d.focus?.minutes || 0
    state.focusSessions = d.focus?.sessions || 0
    state.bestHour = d.focus?.best_hour
    state.tasksTotal = d.tasks?.total || 0
    state.tasksDone = d.tasks?.done || 0
    state.completion = d.tasks?.completion || 0
    state.wrongNew = d.wrong?.new || 0
    state.wrongReviewed = d.wrong?.reviewed || 0
    state.comment = d.comment || ''
    state.hasData = !!d.has_data
  } catch (e) { /* 静默 */ }
  finally { state.loading = false }
})
</script>

<style scoped>
.wr { margin: 12px 0 0; padding: 16px 18px; border-radius: 12px; background: #fff; border: 1px solid #eef1f7; box-shadow: 0 1px 4px rgba(17,24,39,.06); }
.wr__head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px; }
.wr__title { margin: 0; font-size: 14px; font-weight: 700; color: #1a2b5f; }
.wr__sub { margin: 3px 0 0; font-size: 11.5px; color: #8a8faa; }
.wr__export { border: 1px solid #e3e6ec; background: #fff; border-radius: 8px; padding: 6px 12px; font-size: 12px; color: #5c6270; cursor: pointer; }
.wr__export:hover { border-color: #c41e3a; color: #c41e3a; }
.wr__stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.wr__stat { background: #f8f9fc; border-radius: 10px; padding: 10px 12px; }
.wr__num { display: block; font-size: 20px; font-weight: 800; color: #1a2b5f; }
.wr__label { font-size: 11px; color: #8a8faa; }
.wr__bars { display: flex; flex-direction: column; gap: 8px; }
.wr__bar { display: flex; align-items: center; gap: 10px; font-size: 11.5px; color: #5c6270; }
.wr__bar-label { width: 68px; flex: 0 0 68px; }
.wr__bar-track { flex: 1; height: 7px; background: #eef1f7; border-radius: 999px; overflow: hidden; }
.wr__bar-fill { height: 100%; border-radius: 999px; transition: width 500ms cubic-bezier(0.22,1,0.36,1); }
.wr__bar-val { width: 52px; text-align: right; color: #374151; font-weight: 600; }
.wr__comment { margin: 12px 0 0; font-size: 12px; color: #b45309; line-height: 1.6; }
.wr__skeleton { height: 120px; border-radius: 10px; background: #f3f5f9; }
.wr__canvas { display: none; }
@media (max-width: 900px) { .wr__stats { grid-template-columns: repeat(2, 1fr); } }
@media (prefers-reduced-motion: reduce) { .wr__bar-fill { transition: none; } }
</style>
