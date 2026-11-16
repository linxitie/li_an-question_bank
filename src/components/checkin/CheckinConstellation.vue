<template>
  <div class="starmap" ref="wrapRef">
    <div class="starmap__head">
      <span class="starmap__title">签到星图</span>
      <span class="starmap__badge">{{ state.streak }} 天 · {{ shape.name }}</span>
    </div>
    <canvas ref="canvasRef" class="starmap__canvas"></canvas>
    <p class="starmap__tip">{{ tipText }}</p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

/** 星座骨架：坐标归一化到 0-1，按连续签到天数解锁 */
const SHAPES = [
  {
    id: 'dippers',
    name: '小北斗',
    min: 0,
    stars: [
      [0.18, 0.30], [0.30, 0.24], [0.42, 0.30], [0.54, 0.36], [0.66, 0.42], [0.76, 0.54], [0.68, 0.70],
    ],
    links: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6]],
  },
  {
    id: 'orion',
    name: '猎户座',
    min: 14,
    stars: [
      [0.20, 0.18], [0.34, 0.30], [0.30, 0.46], [0.34, 0.62], [0.24, 0.78],
      [0.55, 0.40], [0.55, 0.58], [0.44, 0.26], [0.46, 0.72], [0.70, 0.32], [0.72, 0.62], [0.82, 0.48],
    ],
    links: [[0, 1], [1, 2], [2, 3], [3, 4], [5, 6], [1, 7], [7, 5], [2, 8], [8, 6], [5, 9], [6, 10], [9, 11], [10, 11]],
  },
  {
    id: 'cygnus',
    name: '天鹅座',
    min: 30,
    stars: [
      [0.50, 0.10], [0.50, 0.26], [0.50, 0.42], [0.50, 0.58], [0.50, 0.76],
      [0.30, 0.34], [0.22, 0.46], [0.70, 0.34], [0.78, 0.46], [0.40, 0.86], [0.62, 0.86],
    ],
    links: [[0, 1], [1, 2], [2, 3], [3, 4], [2, 5], [5, 6], [2, 7], [7, 8], [4, 9], [4, 10]],
  },
]

const wrapRef = ref(null)
const canvasRef = ref(null)
const state = reactive({ streak: 0, checkedIn: false, ready: false })

const shape = computed(() => {
  const hit = [...SHAPES].reverse().find((s) => state.streak >= s.min)
  return hit || SHAPES[0]
})

/** 连续几天就点亮几颗星，其余保持暗淡 */
const litCount = computed(() => {
  const total = shape.value.stars.length
  if (state.streak <= 0) return 0
  return Math.min(total, Math.max(1, state.streak % (total + 1) || total))
})

const tipText = computed(() => {
  if (!state.streak) return '签到一次，点亮第一颗星'
  const need = (SHAPES.find((s) => s.min > state.streak)?.min ?? null)
  if (!need) return `已点亮 ${shape.value.name}，连续 ${state.streak} 天`
  return `再签 ${need - state.streak} 天，解锁「${SHAPES.find((s) => s.min === need)?.name}」`
})

let raf = 0
let start = 0
let reduced = false

function hash(n) {
  const x = Math.sin(n * 127.1) * 43758.5453
  return x - Math.floor(x)
}

function draw(ts) {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr
    canvas.height = h * dpr
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)

  const t = reduced ? 0 : (ts - start) / 1000
  const sh = shape.value
  const lit = litCount.value

  // 背景星尘
  for (let i = 0; i < 46; i++) {
    const x = hash(i * 3.7) * w
    const y = hash(i * 8.1 + 2) * h
    const a = reduced ? 0.18 : 0.1 + 0.12 * Math.abs(Math.sin(t * 0.7 + i))
    ctx.beginPath()
    ctx.arc(x, y, 0.7, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(255,255,255,${a})`
    ctx.fill()
  }

  // 连线
  sh.links.forEach(([a, b], idx) => {
    const p1 = sh.stars[a]
    const p2 = sh.stars[b]
    const on = lit > Math.max(a, b)
    const g = ctx.createLinearGradient(p1[0] * w, p1[1] * h, p2[0] * w, p2[1] * h)
    const alpha = on ? 0.55 : 0.12
    g.addColorStop(0, `rgba(255,214,102,${alpha})`)
    g.addColorStop(1, `rgba(196,30,58,${alpha})`)
    ctx.strokeStyle = g
    ctx.lineWidth = on ? 1.3 : 0.8
    ctx.beginPath()
    ctx.moveTo(p1[0] * w, p1[1] * h)
    ctx.lineTo(p2[0] * w, p2[1] * h)
    ctx.stroke()
  })

  // 星点
  sh.stars.forEach((p, i) => {
    const on = i < lit
    const pulse = reduced ? 1 : 0.82 + 0.18 * Math.sin(t * 2 + i * 1.7)
    const r = (on ? 3.2 : 2) * pulse
    const x = p[0] * w
    const y = p[1] * h

    if (on) {
      const halo = ctx.createRadialGradient(x, y, 0, x, y, r * 5)
      halo.addColorStop(0, 'rgba(255,214,102,0.55)')
      halo.addColorStop(1, 'rgba(255,214,102,0)')
      ctx.fillStyle = halo
      ctx.beginPath()
      ctx.arc(x, y, r * 5, 0, Math.PI * 2)
      ctx.fill()
    }

    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = on ? 'rgba(255,236,170,0.98)' : 'rgba(255,255,255,0.22)'
    ctx.fill()
  })

  raf = requestAnimationFrame(draw)
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

async function load() {
  const token = getToken()
  if (!token) { state.ready = true; return }
  try {
    const res = await fetch('/api/v1/growth/checkin/status', {
      headers: { Authorization: 'Bearer ' + token },
    })
    const d = await res.json()
    state.streak = d.continuous_days || 0
    state.checkedIn = !!d.checked_in
  } catch (e) { /* 静默降级 */ }
  finally { state.ready = true }
}

onMounted(() => {
  reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  start = performance.now()
  load()
  raf = requestAnimationFrame(draw)
})
onBeforeUnmount(() => { if (raf) cancelAnimationFrame(raf) })
</script>

<style scoped>
.starmap {
  margin-top: 12px;
  padding: 14px 16px 10px;
  border-radius: 18px;
  background: radial-gradient(120% 100% at 50% 0%, #141a2e 0%, #0b0e18 70%);
  border: 1px solid rgba(255, 214, 102, 0.14);
}
.starmap__head { display: flex; align-items: baseline; justify-content: space-between; }
.starmap__title { font-size: 13px; font-weight: 700; color: #f6e7b8; letter-spacing: 0.04em; }
.starmap__badge {
  font-size: 11px; font-weight: 700; color: #ffd666;
  background: rgba(255, 214, 102, 0.1); padding: 3px 9px; border-radius: 999px;
}
.starmap__canvas { display: block; width: 100%; height: 132px; margin: 6px 0 2px; }
.starmap__tip { margin: 0; font-size: 11px; color: rgba(255, 255, 255, 0.42); text-align: center; }

@media (max-width: 768px) {
  .starmap__canvas { height: 108px; }
}
</style>
