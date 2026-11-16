<template>
  <div class="fg3d" ref="wrapRef">
    <canvas ref="canvasRef" class="fg3d__canvas" @mousedown="onDown" @mousemove="onMove" @mouseup="onUp"
            @mouseleave="onUp" @wheel.prevent="onWheel" @click="onClick"></canvas>
    <div class="fg3d__legend">
      <span><i class="dot dot--subject"></i>科目/模块</span>
      <span><i class="dot dot--point"></i>考点</span>
      <span><i class="dot dot--weak"></i>薄弱</span>
    </div>
    <p class="fg3d__hint" v-if="!state.loading">拖拽旋转 · 滚轮缩放 · 点节点看详情</p>
    <div class="fg3d__loading" v-if="state.loading">图谱加载中…</div>
    <div class="fg3d__empty" v-if="!state.loading && !state.nodes.length">题库还没有知识点数据</div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from "vue"

const emit = defineEmits(["select"])
const wrapRef = ref(null)
const canvasRef = ref(null)

const state = reactive({
  loading: true,
  nodes: [],
  edges: [],
  rotX: -0.32,
  rotY: 0.5,
  zoom: 1,
  drag: false,
})

let raf = 0
let reduced = false
let lastX = 0
let lastY = 0
let ticks = 0

function project(p, w, h) {
  const cosY = Math.cos(state.rotY), sinY = Math.sin(state.rotY)
  const cosX = Math.cos(state.rotX), sinX = Math.sin(state.rotX)
  let x = p.x * cosY - p.z * sinY
  let z = p.x * sinY + p.z * cosY
  let y = p.y * cosX - z * sinX
  z = p.y * sinX + z * cosX
  // 节点坐标半径约 260，缩放系数必须与之匹配，否则整张图会跑到视口外
  const scale = (Math.min(w, h) / 700) * state.zoom
  const depth = 1 + z / 900
  return { sx: w / 2 + x * scale * depth, sy: h / 2 + y * scale * depth, depth: depth, z: z }
}

function initLayout() {
  const n = state.nodes.length || 1
  state.nodes.forEach(function (node, i) {
    const golden = Math.PI * (3 - Math.sqrt(5))
    const y = 1 - (i / Math.max(1, n - 1)) * 2
    const r = Math.sqrt(Math.max(0, 1 - y * y))
    const theta = golden * i
    node.x = node.x !== undefined ? node.x : Math.cos(theta) * r * 260
    node.y = node.y !== undefined ? node.y : y * 200
    node.z = node.z !== undefined ? node.z : Math.sin(theta) * r * 260
    node.vx = 0; node.vy = 0; node.vz = 0
  })
}

function tick() {
  const nodes = state.nodes
  const edges = state.edges
  const idx = {}
  nodes.forEach(function (n) { idx[n.id] = n })
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j]
      let dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z
      let d2 = dx * dx + dy * dy + dz * dz + 0.01
      const f = 1400 / d2
      const d = Math.sqrt(d2)
      dx /= d; dy /= d; dz /= d
      a.vx += dx * f; a.vy += dy * f; a.vz += dz * f
      b.vx -= dx * f; b.vy -= dy * f; b.vz -= dz * f
    }
  }
  edges.forEach(function (e) {
    const a = idx[e.source], b = idx[e.target]
    if (!a || !b) return
    const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z
    const d = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01
    const f = (d - 110) * 0.012
    a.vx += (dx / d) * f; a.vy += (dy / d) * f; a.vz += (dz / d) * f
    b.vx -= (dx / d) * f; b.vy -= (dy / d) * f; b.vz -= (dz / d) * f
  })
  const LIMIT = 300  // 越界钳制：防止力导后期把球体顶出画布
  nodes.forEach(function (n) {
    n.vx -= n.x * 0.0016; n.vy -= n.y * 0.0016; n.vz -= n.z * 0.0016
    n.vx *= 0.86; n.vy *= 0.86; n.vz *= 0.86
    n.x += n.vx; n.y += n.vy; n.z += n.vz
    const len = Math.sqrt(n.x * n.x + n.y * n.y + n.z * n.z)
    if (len > LIMIT) {
      const k = LIMIT / len
      n.x *= k; n.y *= k; n.z *= k
    }
  })
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext("2d")
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (canvas.width !== w * dpr) { canvas.width = w * dpr; canvas.height = h * dpr }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)

  // 窄屏节点多、O(n^2) 逐帧计算代价高，收敛帧数按视口降档
  const tickBudget = window.innerWidth < 768 ? 140 : 260
  if (!reduced && ticks < tickBudget) { tick(); ticks += 1 }

  const pos = {}
  state.nodes.forEach(function (n) {
    const p = project(n, w, h)
    pos[n.id] = p
  })

  state.edges.forEach(function (e) {
    const a = pos[e.source], b = pos[e.target]
    if (!a || !b) return
    const alpha = e.rel === "confusable" ? 0.16 : e.rel === "prerequisite_of" ? 0.22 : 0.3
    ctx.strokeStyle = e.rel === "confusable" ? "rgba(196,30,58," + alpha + ")"
      : e.rel === "prerequisite_of" ? "rgba(245,158,11," + alpha + ")"
      : "rgba(120,140,190," + alpha + ")"
    ctx.lineWidth = e.rel === "contains" ? 0.7 : 0.55
    ctx.beginPath()
    ctx.moveTo(a.sx, a.sy)
    ctx.lineTo(b.sx, b.sy)
    ctx.stroke()
  })

  const sorted = state.nodes.slice().sort(function (a, b) { return pos[a.id].depth - pos[b.id].depth })
  sorted.forEach(function (n) {
    const p = pos[n.id]
    const r = (n.level === 1 ? 4.2 : n.level === 2 ? 2.2 : 3) * p.depth
    // mastery 为 0 / 缺失表示“还没有该考点的数据”，不能当作薄弱，否则整张图全是红的
    const weak = typeof n.mastery === "number" && n.mastery > 0 && n.mastery < 0.5
    ctx.beginPath()
    ctx.arc(p.sx, p.sy, Math.max(1, r), 0, Math.PI * 2)
    ctx.fillStyle = n.level === 1 ? "#2563eb" : weak ? "#c41e3a" : "rgba(148,163,184,0.9)"
    ctx.fill()
    if (n.hover) {
      ctx.strokeStyle = "#111827"
      ctx.lineWidth = 1
      ctx.stroke()
      ctx.font = "11px system-ui"
      ctx.fillStyle = "#111827"
      ctx.fillText(n.name, p.sx + 8, p.sy - 6)
    }
  })

  raf = requestAnimationFrame(draw)
}

function onDown(e) { state.drag = true; lastX = e.clientX; lastY = e.clientY }
function onUp() { state.drag = false }
function onMove(e) {
  if (!state.drag) return
  state.rotY += (e.clientX - lastX) * 0.006
  state.rotX += (e.clientY - lastY) * 0.006
  state.rotX = Math.max(-1.3, Math.min(1.3, state.rotX))
  lastX = e.clientX; lastY = e.clientY
}
function onWheel(e) {
  state.zoom = Math.max(0.4, Math.min(3, state.zoom * (e.deltaY > 0 ? 0.92 : 1.08)))
}
function onClick(e) {
  const canvas = canvasRef.value
  if (!canvas || !state.nodes.length) return
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  let best = null
  // 命中半径随视口放宽：球体缩小后节点密集，16px 实测点不中，改为 30px 起步
  let bestD = Math.max(30, Math.min(48, rect.width / 30))
  let bestProjected = null
  state.nodes.forEach(function (n) {
    const p = project(n, rect.width, rect.height)
    const d = Math.hypot(p.sx - mx, p.sy - my)
    if (d < bestD) { bestD = d; best = n; bestProjected = p }
  })
  state.nodes.forEach(function (n) { n.hover = n === best })
  if (best) {
    // 带上一跳邻居，供外层做下钻面板
    const neighbors = state.edges
      .filter(function (e) { return e.source === best.id || e.target === best.id })
      .map(function (e) {
        const otherId = e.source === best.id ? e.target : e.source
        const other = state.nodes.find(function (n) { return n.id === otherId })
        return other ? { id: other.id, name: other.name, rel: e.rel } : null
      })
      .filter(Boolean)
    emit("select", {
      id: best.id,
      name: best.name,
      level: best.level,
      degree: neighbors.length,
      neighbors: neighbors.slice(0, 12),
    })
  }
}

function token() {
  try {
    const raw = localStorage.getItem("__VTJ_AUTH_STATE__")
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem("token") || ""
}

onMounted(async function () {
  reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  raf = requestAnimationFrame(draw)
  try {
    const res = await fetch("/api/knowledge/kg/global?limit=800", {
      headers: { Authorization: "Bearer " + token() },
    })
    const data = await res.json()
    const rawNodes = data.nodes || []
    state.nodes = rawNodes.map(function (n, i) {
      return {
        id: n.point_id !== undefined ? n.point_id : i,
        name: n.point_name || ("点" + i),
        level: n.subject_id ? 2 : 1,
        mastery: n.mastery,
      }
    })
    const ids = {}
    state.nodes.forEach(function (n) { ids[n.id] = true })
    state.edges = (data.edges || [])
      .filter(function (e) { return ids[e.src_point] && ids[e.dst_point] })
      .map(function (e) { return { source: e.src_point, target: e.dst_point, rel: e.rel_type } })
    initLayout()
  } catch (e) { /* 静默 */ }
  finally { state.loading = false }
})

onBeforeUnmount(function () { if (raf) cancelAnimationFrame(raf) })
</script>

<style scoped>
.fg3d { position: relative; height: 520px; border-radius: 18px; overflow: hidden;
  background: radial-gradient(120% 100% at 50% 0%, #101828 0%, #070b14 75%); }
.fg3d__canvas { width: 100%; height: 100%; display: block; cursor: grab; }
.fg3d__canvas:active { cursor: grabbing; }
.fg3d__legend { position: absolute; left: 14px; bottom: 12px; display: flex; gap: 14px; font-size: 11px; color: rgba(255,255,255,0.55); }
.fg3d__legend .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; }
.dot--subject { background: #2563eb; }
.dot--point { background: rgba(148,163,184,0.9); }
.dot--weak { background: #c41e3a; }
.fg3d__hint { position: absolute; right: 14px; bottom: 12px; margin: 0; font-size: 11px; color: rgba(255,255,255,0.35); }
.fg3d__loading, .fg3d__empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 13px; color: rgba(255,255,255,0.55); }
@media (max-width: 768px) {
  .fg3d { height: 360px; }
  .fg3d__hint { display: none; }
  .fg3d__legend { font-size: 10px; gap: 10px; }
}
</style>