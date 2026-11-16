<template>
  <div class="pomo" :class="{ 'pomo--open': open, 'pomo--running': state.running }">
    <!-- 收起态：圆形气泡 -->
    <button v-if="!open" class="pomo__bubble" @click="open = true" :title="'番茄钟 ' + display">
      <span class="pomo__bubble-icon">🍅</span>
      <span class="pomo__bubble-time">{{ display }}</span>
    </button>

    <!-- 展开态：小窗 -->
    <div v-else class="pomo__panel">
      <div class="pomo__head">
        <span class="pomo__mode">{{ state.mode === 'focus' ? '专注中' : '休息中' }}</span>
        <button class="pomo__close" @click="open = false">×</button>
      </div>

      <div class="pomo__time" :class="{ 'pomo__time--warn': state.remain <= 60 }">{{ display }}</div>

      <div class="pomo__ring">
        <svg viewBox="0 0 100 100" class="pomo__svg">
          <circle cx="50" cy="50" r="44" class="pomo__track" />
          <circle cx="50" cy="50" r="44" class="pomo__prog"
                  :stroke-dasharray="circ" :stroke-dashoffset="dashOffset"
                  :class="state.mode === 'focus' ? 'is-focus' : 'is-break'" />
        </svg>
      </div>

      <div class="pomo__actions">
        <button class="pomo__btn primary" @click="toggle">{{ state.running ? '暂停' : (state.remain < total ? '继续' : '开始') }}</button>
        <button class="pomo__btn ghost" @click="reset">重置</button>
        <button class="pomo__btn ghost" @click="openImmersive">沉浸</button>
      </div>

      <div class="pomo__foot">
        <span>今日专注 {{ state.sessionsToday }} 次</span>
        <button class="pomo__switch" @click="switchMode">
          {{ state.mode === 'focus' ? '切到休息' : '切回专注' }}
        </button>
      </div>
    </div>

    <!-- 沉浸式专注：全屏黑场 + 呼吸光晕 + 粒子（4-4） -->
    <FocusImmersive
      :visible="immersive"
      :seconds="state.remain"
      :mode="state.mode"
      @close="onImmersiveClose"
      @finish="onImmersiveFinish"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import FocusImmersive from './FocusImmersive.vue'

const FOCUS_MIN = 25
const BREAK_MIN = 5

const open = ref(false)
const immersive = ref(false)
const state = reactive({
  mode: 'focus',       // focus | break
  running: false,
  remain: FOCUS_MIN * 60,
  sessionsToday: 0,
})
let timer = null
let endAt = 0

const total = computed(() => (state.mode === 'focus' ? FOCUS_MIN : BREAK_MIN) * 60)
const display = computed(() => {
  const s = Math.max(0, state.remain)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0')
})
const circ = 2 * Math.PI * 44
const dashOffset = computed(() => circ * (1 - Math.max(0, state.remain) / total.value))

const STORE = 'li_an_pomodoro_v1'

function persist() {
  try {
    localStorage.setItem(STORE, JSON.stringify({
      mode: state.mode,
      running: state.running,
      endAt,
      sessionsToday: state.sessionsToday,
      day: new Date().toDateString(),
    }))
  } catch (e) { /* ignore */ }
}

function restore() {
  try {
    const raw = localStorage.getItem(STORE)
    if (!raw) return
    const o = JSON.parse(raw)
    if (o.day !== new Date().toDateString()) {
      // 跨天：次数归零，计时重置
      return
    }
    state.mode = o.mode || 'focus'
    state.sessionsToday = o.sessionsToday || 0
    if (o.running && o.endAt) {
      const left = Math.round((o.endAt - Date.now()) / 1000)
      if (left > 0) {
        endAt = o.endAt
        state.remain = left
        start()
      } else {
        state.remain = (state.mode === 'focus' ? FOCUS_MIN : BREAK_MIN) * 60
      }
    } else {
      state.remain = (state.mode === 'focus' ? FOCUS_MIN : BREAK_MIN) * 60
    }
  } catch (e) { /* ignore */ }
}

function start() {
  state.running = true
  endAt = endAt || Date.now() + state.remain * 1000
  if (timer) clearInterval(timer)
  timer = setInterval(tick, 1000)
  persist()
}

function tick() {
  const left = Math.round((endAt - Date.now()) / 1000)
  state.remain = Math.max(0, left)
  if (left <= 0) finish()
}

function toggle() {
  if (state.running) {
    state.running = false
    endAt = 0
    if (timer) clearInterval(timer)
    timer = null
    persist()
  } else {
    start()
  }
}

function reset() {
  state.running = false
  endAt = 0
  if (timer) clearInterval(timer)
  timer = null
  state.remain = total.value
  persist()
}

function switchMode() {
  state.mode = state.mode === 'focus' ? 'break' : 'focus'
  state.running = false
  endAt = 0
  if (timer) clearInterval(timer)
  timer = null
  state.remain = total.value
  persist()
}

async function finish() {
  if (timer) clearInterval(timer)
  timer = null
  state.running = false
  endAt = 0
  state.remain = 0

  if (state.mode === 'focus') {
    state.sessionsToday += 1
    await recordFocus(FOCUS_MIN)
    await autoCheckin()
    // 自动进入 5 分钟休息
    state.mode = 'break'
  } else {
    state.mode = 'focus'
  }
  state.remain = total.value
  persist()
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

/** 专注结束写一条记录，供专注力热力图统计 */
async function recordFocus(minutes) {
  const token = getToken()
  if (!token) return
  try {
    await fetch("/api/v1/growth/focus/record", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ minutes: minutes, mode: "focus", source: "widget" }),
    })
  } catch (e) { /* 网络失败不影响计时 */ }
}

/** 专注结束顺手补签到：接口本身幂等，已签不会重复发奖 */
async function autoCheckin() {
  const token = getToken()
  if (!token) return
  try {
    const st = await fetch('/api/v1/growth/checkin/status', {
      headers: { Authorization: 'Bearer ' + token },
    }).then((r) => r.json())
    if (st && st.checked_in) return
    await fetch('/api/v1/growth/checkin', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token },
    })
  } catch (e) { /* 网络失败静默，不打断专注 */ }
}

function openImmersive() {
  // 进入沉浸前暂停小窗计时，避免两处同时倒数
  if (state.running) toggle()
  immersive.value = true
}

function onImmersiveClose(remainSeconds) {
  immersive.value = false
  if (typeof remainSeconds === 'number' && remainSeconds > 0) {
    state.remain = remainSeconds
    persist()
  }
}

function onImmersiveFinish() {
  immersive.value = false
  finish()
}

onMounted(() => { restore() })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.pomo { position: fixed; right: 24px; bottom: 24px; z-index: 900; }

.pomo__bubble {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border: none; border-radius: 999px;
  background: #fff; box-shadow: 0 8px 28px rgba(17, 24, 39, 0.14);
  cursor: pointer; font-size: 14px; font-weight: 700; color: #111827;
  transition: transform 160ms ease;
}
.pomo__bubble:hover { transform: translateY(-2px); }
.pomo__bubble-icon { font-size: 16px; }
.pomo--running .pomo__bubble { box-shadow: 0 8px 28px rgba(239, 68, 68, 0.28); }

.pomo__panel {
  width: 240px; padding: 16px; border-radius: 20px;
  background: #fff; box-shadow: 0 16px 48px rgba(17, 24, 39, 0.18);
  animation: pomoIn 200ms cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes pomoIn { from { opacity: 0; transform: translateY(12px) scale(0.96); } to { opacity: 1; transform: none; } }

.pomo__head { display: flex; align-items: center; justify-content: space-between; }
.pomo__mode { font-size: 12px; font-weight: 700; color: #ef4444; letter-spacing: 0.04em; }
.pomo__close { border: none; background: none; font-size: 18px; color: #9ca3af; cursor: pointer; line-height: 1; }

.pomo__time { margin: 8px 0 4px; font-size: 30px; font-weight: 800; text-align: center; color: #111827; font-variant-numeric: tabular-nums; }
.pomo__time--warn { color: #ef4444; }

.pomo__ring { position: relative; height: 84px; }
.pomo__svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.pomo__track { fill: none; stroke: #f1f5f9; stroke-width: 8; }
.pomo__prog { fill: none; stroke-width: 8; stroke-linecap: round; transition: stroke-dashoffset 900ms linear; }
.pomo__prog.is-focus { stroke: #ef4444; }
.pomo__prog.is-break { stroke: #10b981; }

.pomo__actions { display: flex; gap: 8px; margin-top: 10px; }
.pomo__btn { flex: 1; padding: 9px 0; border: none; border-radius: 12px; font-size: 13px; font-weight: 700; cursor: pointer; }
.pomo__btn.primary { background: #ef4444; color: #fff; }
.pomo__btn.ghost { background: #f3f4f6; color: #374151; }

.pomo__foot { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; font-size: 11px; color: #9ca3af; }
.pomo__switch { border: none; background: none; color: #2563eb; font-size: 11px; cursor: pointer; }

@media (max-width: 768px) {
  .pomo { right: 14px; bottom: 84px; }
  .pomo__panel { width: 210px; }
}
@media (prefers-reduced-motion: reduce) {
  .pomo__panel { animation: none; }
  .pomo__prog { transition: none; }
}
</style>
