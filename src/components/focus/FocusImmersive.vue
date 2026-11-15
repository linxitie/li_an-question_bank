<template>
  <teleport to="body">
    <transition name="imm">
      <div v-if="visible" class="imm">
        <canvas ref="canvasRef" class="imm__particles"></canvas>

        <div class="imm__halo" :class="{ 'is-break': mode === 'break' }"></div>

        <div class="imm__core">
          <p class="imm__label">{{ mode === 'focus' ? '专注中' : '休息中' }}</p>
          <p class="imm__time">{{ display }}</p>
          <p class="imm__hint">{{ hint }}</p>

          <div class="imm__actions">
            <button class="imm__btn" @click="toggle">{{ running ? '暂停' : '继续' }}</button>
            <button class="imm__btn imm__btn--ghost" @click="close">退出沉浸</button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  seconds: { type: Number, default: 25 * 60 },
  mode: { type: String, default: 'focus' },
})
const emit = defineEmits(['close', 'finish', 'tick'])

const canvasRef = ref(null)
const remain = ref(props.seconds)
const running = ref(true)

let timer = null
let raf = 0
let endAt = 0
let particles = []

const display = computed(() => {
  const s = Math.max(0, remain.value)
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0')
})
const hint = computed(() =>
  props.mode === 'focus' ? '把手机翻过去，这一屏只留给你自己' : '站起来，看看远处，让眼睛歇一会儿'
)

function spawn() {
  const canvas = canvasRef.value
  if (!canvas) return
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  particles = Array.from({ length: window.innerWidth < 768 ? 28 : 64 }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: 0.6 + Math.random() * 1.8,
    vx: (Math.random() - 0.5) * 0.12,
    vy: (Math.random() - 0.5) * 0.12,
    a: 0.15 + Math.random() * 0.3,
  }))
}

function loop() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (canvas.width !== w * dpr) { canvas.width = w * dpr; canvas.height = h * dpr }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)

  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    if (p.x < 0 || p.x > w) p.vx *= -1
    if (p.y < 0 || p.y > h) p.vy *= -1
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fillStyle = props.mode === 'focus'
      ? `rgba(255,214,102,${p.a})`
      : `rgba(120,220,180,${p.a})`
    ctx.fill()
  }
  raf = requestAnimationFrame(loop)
}

/** 用 Web Audio 合成收工钟声，避免引入音频文件 */
function chime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    const ac = new Ctx()
    const now = ac.currentTime
    ;[523.25, 659.25, 783.99].forEach((f, i) => {
      const osc = ac.createOscillator()
      const gain = ac.createGain()
      osc.type = 'sine'
      osc.frequency.value = f
      gain.gain.setValueAtTime(0, now + i * 0.12)
      gain.gain.linearRampToValueAtTime(0.18, now + i * 0.12 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.12 + 1.4)
      osc.connect(gain).connect(ac.destination)
      osc.start(now + i * 0.12)
      osc.stop(now + i * 0.12 + 1.5)
    })
    setTimeout(() => ac.close(), 2200)
  } catch (e) { /* 不支持音频就静默 */ }
}

function start() {
  running.value = true
  endAt = Date.now() + remain.value * 1000
  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    remain.value = Math.max(0, Math.round((endAt - Date.now()) / 1000))
    if (remain.value <= 0) {
      clearInterval(timer); timer = null
      running.value = false
      chime()
      emit('finish')
    }
  }, 1000)
}

function toggle() {
  if (running.value) {
    running.value = false
    if (timer) { clearInterval(timer); timer = null }
    endAt = 0
  } else start()
}

function close() {
  if (timer) { clearInterval(timer); timer = null }
  emit('close', remain.value)
}

watch(() => props.visible, (v) => {
  if (v) {
    remain.value = props.seconds
    requestAnimationFrame(() => { spawn(); if (raf) cancelAnimationFrame(raf); raf = requestAnimationFrame(loop) })
    if (raf) cancelAnimationFrame(raf)
    raf = requestAnimationFrame(loop)
    start()
  } else {
    if (raf) { cancelAnimationFrame(raf); raf = 0 }
    if (timer) { clearInterval(timer); timer = null }
  }
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.imm {
  position: fixed; inset: 0; z-index: 3000;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle at 50% 45%, #0d1220 0%, #05060a 70%);
  overflow: hidden;
}
.imm__particles { position: absolute; inset: 0; width: 100%; height: 100%; }

.imm__halo {
  position: absolute; width: 420px; height: 420px; border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 214, 102, 0.16) 0%, rgba(255, 214, 102, 0) 62%);
  animation: breathe 6s ease-in-out infinite;
}
.imm__halo.is-break {
  background: radial-gradient(circle, rgba(120, 220, 180, 0.16) 0%, rgba(120, 220, 180, 0) 62%);
}
@keyframes breathe {
  0%, 100% { transform: scale(0.92); opacity: 0.75; }
  50% { transform: scale(1.08); opacity: 1; }
}

.imm__core { position: relative; text-align: center; z-index: 2; }
.imm__label { margin: 0; font-size: 13px; letter-spacing: 0.35em; color: rgba(255, 214, 102, 0.7); }
.imm__time {
  margin: 10px 0 4px; font-size: 88px; font-weight: 200; color: #f7f3e8;
  font-variant-numeric: tabular-nums; letter-spacing: 0.04em;
}
.imm__hint { margin: 0 0 26px; font-size: 13px; color: rgba(255, 255, 255, 0.34); }

.imm__actions { display: flex; gap: 12px; justify-content: center; }
.imm__btn {
  padding: 10px 24px; border-radius: 999px; border: 1px solid rgba(255, 214, 102, 0.42);
  background: rgba(255, 214, 102, 0.1); color: #ffe9ad; font-size: 13px; cursor: pointer;
  transition: background 160ms ease;
}
.imm__btn:hover { background: rgba(255, 214, 102, 0.18); }
.imm__btn--ghost { border-color: rgba(255, 255, 255, 0.18); background: transparent; color: rgba(255, 255, 255, 0.6); }

.imm-enter-active, .imm-leave-active { transition: opacity 420ms ease; }
.imm-enter-from, .imm-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .imm__time { font-size: 60px; }
  .imm__halo { width: 280px; height: 280px; }
}
@media (prefers-reduced-motion: reduce) {
  .imm__halo { animation: none; }
  .imm-enter-active, .imm-leave-active { transition: none; }
}
</style>
