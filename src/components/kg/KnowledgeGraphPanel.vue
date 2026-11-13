<template>
  <div class="kgp" :class="{ 'is-compact': compact, 'is-global': mode === 'global' }">
    <div v-if="error" class="kgp-error">{{ error }}</div>

    <section class="kgp-grid">
      <div class="kgp-canvas-card">
        <div v-if="loading" class="kgp-empty">加载中…</div>
        <div v-else-if="!nodes.length" class="kgp-empty">
          <p>还没有图谱数据。</p>
          <p class="kgp-hint">去刷几道题，系统会自动为你的知识点建节点、连边。</p>
        </div>

        <svg v-else ref="svgRef" class="kgp-svg" :viewBox="zoomViewBox"
          preserveAspectRatio="xMidYMid slice" role="img" aria-label="知识图谱" @wheel.prevent="onWheel" style="touch-action: none" @pointermove="onDragMove" @pointerup="endDrag" @pointerleave="endDrag">
          <g class="kgp-edges">
            <path
              v-for="e in edges"
              :key="e.src_point + '-' + e.dst_point"
              :d="edgePath(e)"
              fill="none"
              :stroke-width="Math.min(1.6, edgeWidth(e) * 0.55)"
              :stroke-opacity="0.16"
              stroke="#94a3b8"
            />
          </g>
          <g class="kgp-nodes">
            <g
              v-for="node in nodes"
              :key="node.point_id"
              class="kgp-node"
              :class="{ 'is-active': activeId === node.point_id }"
              @click="activeId = node.point_id"
              @pointerdown.stop="startDrag(node, $event)"
            >
              <circle
                :cx="displayPos(node).x"
                :cy="displayPos(node).y"
                :r="nodeRadius(node)"
                :fill="nodeColor(node)"
                fill-opacity="0.85"
                stroke="#1f2937"
                stroke-width="1"
              />
              <text
                :x="displayPos(node).x"
                :y="displayPos(node).y + 4"
                class="kgp-label"
                text-anchor="middle"
              >
                {{ shortName(node.point_name) }}
              </text>
            </g>
          </g>
        </svg>


      </div>

      <aside class="kgp-side">
        <div class="kgp-card">
          <h3>做题习惯</h3>
          <p class="kgp-summary">{{ habits.habit_summary }}</p>
          <dl class="kgp-kv">
            <dt>偏好时段</dt><dd>{{ slotText(habits.preferred_slot) }}</dd>
            <dt>节奏稳定度</dt><dd>{{ (habits.stability * 100).toFixed(0) }}%</dd>
            <dt>单次时长</dt><dd>{{ habits.avg_time_spent }} 秒</dd>
            <dt>近 30 天记录</dt><dd>{{ habits.total_records }} 条</dd>
            <dt>采样温度 T</dt><dd>{{ habits.temperature }}（{{ temperatureHint }}）</dd>
          </dl>
        </div>

        <div class="kgp-card">
          <h3>本周任务候选</h3>
          <ul class="kgp-samples">
            <li v-for="s in samples" :key="s.point_id">
              <span class="kgp-sample-name">{{ s.point_name }}</span>
              <span class="kgp-sample-meta">p={{ (s.probability * 100).toFixed(1) }}% · 贡献 {{ s.contribution.toFixed(2) }}</span>
            </li>
          </ul>
          <p v-if="!samples.length" class="kgp-hint">暂无候选（先积累答题行为）</p>
        </div>

        <div class="kgp-card">
          <h3>最热的节点</h3>
          <ul class="kgp-samples">
            <li v-for="n in topNodes" :key="n.point_id">
              <span class="kgp-sample-name">{{ n.point_name }}</span>
              <span class="kgp-sample-meta">热度 {{ n.heat.toFixed(2) }} · 掌握 {{ (n.mastery * 100).toFixed(0) }}%</span>
            </li>
          </ul>
        </div>
      </aside>
      <div v-if="activeNode" class="kgp-node-detail kgp-node-detail-bottom">
        <strong>{{ activeNode.point_name }}</strong>
        <span>掌握度 {{ (activeNode.mastery * 100).toFixed(0) }}%</span>
        <span>热度 {{ activeNode.heat.toFixed(2) }}</span>
        <span>贡献度 {{ activeNode.contribution.toFixed(2) }}</span>
        <span>答题 {{ activeNode.attempt_count }} 次 / 对 {{ activeNode.correct_count }}</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

interface KgNode {
  point_id: number;
  point_name: string;
  mastery: number;
  heat: number;
  attempt_count: number;
  correct_count: number;
  contribution: number;
}
interface KgEdge {
  src_point: number;
  dst_point: number;
  weight: number;
  heat: number;
}
interface KgSample {
  point_id: number;
  point_name: string;
  probability: number;
  contribution: number;
}
interface HabitProfile {
  preferred_slot: string | null;
  preferred_subject: number | null;
  stability: number;
  avg_time_spent: number;
  total_records: number;
  temperature: number;
  habit_summary: string;
  slot_distribution: Record<string, number>;
}

const props = withDefaults(defineProps<{ compact?: boolean; generateSignal?: number; mode?: 'mine' | 'global' }>(), {
  compact: false,
  generateSignal: 0,
  mode: 'mine'
});
const emit = defineEmits<{ (e: 'changed'): void }>();

const nodes = ref<KgNode[]>([]);
const edges = ref<KgEdge[]>([]);
const samples = ref<KgSample[]>([]);
const habits = ref<HabitProfile>({
  preferred_slot: null,
  preferred_subject: null,
  stability: 0,
  avg_time_spent: 0,
  total_records: 0,
  temperature: 0.8,
  habit_summary: '',
  slot_distribution: {}
});
const loading = ref(false);
const error = ref('');
const activeId = ref<number | null>(null);

const svgW = 640;
const svgH = 420;

const activeNode = computed(() => nodes.value.find((n) => n.point_id === activeId.value) || null);
const topNodes = computed(() => [...nodes.value].sort((a, b) => b.heat - a.heat).slice(0, 5));

const temperatureHint = computed(() =>
  habits.value.temperature < 0.7
    ? '节奏稳定，聚焦薄弱点'
    : habits.value.temperature > 1.0
      ? '节奏波动大，多探索'
      : '节奏一般，正常探索'
);

const pos = computed<Record<number, { x: number; y: number }>>(() => {
  const list = [...nodes.value];
  const n = list.length;
  const map: Record<number, { x: number; y: number }> = {};
  if (!n) return map;

  const idx: Record<number, number> = {};
  const xs: number[] = [];
  const ys: number[] = [];
  list.forEach((node, i) => {
    idx[node.point_id] = i;
    const angle = i * 2.399963229728653; // 黄金角，打散初始圆环
    const radius = Math.min(svgW, svgH) * (0.12 + ((i * 37) % 100) / 100 * 0.3);
    xs[i] = svgW / 2 + Math.cos(angle) * radius;
    ys[i] = svgH / 2 + Math.sin(angle) * radius;
  });

  const links = edges.value.filter(
    (e) => idx[e.src_point] !== undefined && idx[e.dst_point] !== undefined
  );
  const k = Math.sqrt((svgW * svgH) / Math.max(1, n)) * 0.9;
  let temp = Math.min(svgW, svgH) / 8;

  for (let it = 0; it < 240; it++) {
    const dx = new Array<number>(n).fill(0);
    const dy = new Array<number>(n).fill(0);

    // 斥力
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let vx = xs[i] - xs[j];
        let vy = ys[i] - ys[j];
        let d2 = vx * vx + vy * vy;
        if (d2 < 1) {
          vx = (Math.random() - 0.5) * 2;
          vy = (Math.random() - 0.5) * 2;
          d2 = vx * vx + vy * vy;
        }
        const d = Math.sqrt(d2);
        const f = (k * k) / d;
        const fx = (vx / d) * f;
        const fy = (vy / d) * f;
        dx[i] += fx;
        dy[i] += fy;
        dx[j] -= fx;
        dy[j] -= fy;
      }
    }

    // 弹簧（边）
    for (const e of links) {
      const i = idx[e.src_point];
      const j = idx[e.dst_point];
      const vx = xs[i] - xs[j];
      const vy = ys[i] - ys[j];
      const d = Math.max(1, Math.sqrt(vx * vx + vy * vy));
      const f = ((d * d) / k) * 0.95;
      const fx = (vx / d) * f;
      const fy = (vy / d) * f;
      dx[i] -= fx;
      dy[i] -= fy;
      dx[j] += fx;
      dy[j] += fy;
    }

    // 向心力
    for (let i = 0; i < n; i++) {
      dx[i] += (svgW / 2 - xs[i]) * 0.006;
      dy[i] += (svgH / 2 - ys[i]) * 0.006;
    }

    // 位移动画（退火）
    for (let i = 0; i < n; i++) {
      const d = Math.max(0.001, Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i]));
      const step = Math.min(d, temp);
      xs[i] = Math.max(34, Math.min(svgW - 34, xs[i] + (dx[i] / d) * step));
      ys[i] = Math.max(34, Math.min(svgH - 34, ys[i] + (dy[i] / d) * step));
    }
    temp *= 0.97;
  }

  // 归一化到画布：保证节点铺满可视区域，而不是缩在中心
  const pad = 100;
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scaleX = (svgW - pad * 2) / spanX;
  const scaleY = (svgH - pad * 2) / spanY;

  list.forEach((node, i) => {
    map[node.point_id] = {
      x: pad + (xs[i] - minX) * scaleX,
      y: pad + (ys[i] - minY) * scaleY
    };
  });
  return map;
});

const zoom = ref(1);
const zoomViewBox = computed(() => {
  const w = svgW / zoom.value;
  const h = svgH / zoom.value;
  const x = (svgW - w) / 2;
  const y = (svgH - h) / 2;
  return x + ' ' + y + ' ' + w + ' ' + h;
});
function onWheel(e: WheelEvent) {
  zoom.value = Math.max(0.05, zoom.value * (e.deltaY > 0 ? 0.9 : 1.1));
}

const svgRef = ref<SVGSVGElement | null>(null);
const dragPos = ref<Record<number, { x: number; y: number }>>({});
const dragId = ref<number | null>(null);
const dragOffset = ref({ dx: 0, dy: 0 });

function displayPos(node: KgNode): { x: number; y: number } {
  return dragPos.value[node.point_id] || pos.value[node.point_id] || { x: 0, y: 0 };
}
function displayPosById(id: number): { x: number; y: number } {
  return dragPos.value[id] || pos.value[id] || { x: 0, y: 0 };
}
function edgePath(e: any): string {
  const a = displayPosById(e.src_point);
  const b = displayPosById(e.dst_point);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const bend = Math.min(60, len * 0.15);
  const mx = (a.x + b.x) / 2 + nx * bend;
  const my = (a.y + b.y) / 2 + ny * bend;
  return 'M' + a.x + ',' + a.y + ' Q' + mx + ',' + my + ' ' + b.x + ',' + b.y;
}

function toSvg(e: PointerEvent): { x: number; y: number } {
  const el = svgRef.value;
  if (!el) return { x: 0, y: 0 };
  const r = el.getBoundingClientRect();
  const sx = svgW / r.width;
  const sy = svgH / r.height;
  return { x: (e.clientX - r.left) * sx, y: (e.clientY - r.top) * sy };
}
function startDrag(node: KgNode, e: PointerEvent) {
  const p = displayPos(node);
  const q = toSvg(e);
  dragOffset.value = { dx: p.x - q.x, dy: p.y - q.y };
  dragId.value = node.point_id;
  (e.target as Element).setPointerCapture?.(e.pointerId);
}
function onDragMove(e: PointerEvent) {
  if (dragId.value == null) return;
  const q = toSvg(e);
  dragPos.value = {
    ...dragPos.value,
    [dragId.value]: { x: q.x + dragOffset.value.dx, y: q.y + dragOffset.value.dy }
  };
}
function endDrag() {
  dragId.value = null;
}

const NODE_PALETTE = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4'];
function nodeColor(node: KgNode): string {
  return NODE_PALETTE[Math.abs(node.point_id) % NODE_PALETTE.length];
}

function nodeRadius(node: KgNode): number {
  return Math.min(28, 9 + Math.sqrt(Math.max(0, node.heat)) * 6);
}

function masteryColor(mastery: number): string {
  const m = Math.max(0, Math.min(1, mastery));
  const r = Math.round(239 - 120 * m);
  const g = Math.round(68 + 150 * m);
  const b = Math.round(68 + 60 * m);
  return `rgb(${r},${g},${b})`;
}

function shortName(name: string): string {
  return name.length > 7 ? `${name.slice(0, 6)}…` : name;
}

function edgeWidth(e: KgEdge): number {
  return Math.min(6, 1 + Math.max(0, e.weight - 1) * 3);
}

function edgeOpacity(e: KgEdge): number {
  return Math.min(0.8, 0.25 + (e.weight - 1) * 0.4);
}

function slotText(slot: string | null): string {
  return { morning: '上午', afternoon: '下午', evening: '晚上', night: '深夜' }[slot || ''] || '暂无';
}

function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
}

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = '';
  if (props.mode === 'global') {
    try {
      const res = await apiFetch('/api/knowledge/kg/global?limit=800');
      const data = await res.json();
      nodes.value = (data.nodes || []).map((n: any) => ({
        point_id: n.point_id,
        point_name: n.point_name,
        mastery: n.mastery || 0,
        heat: n.heat || 0,
        attempt_count: n.attempt_count || 0,
        correct_count: n.correct_count || 0,
        contribution: n.contribution || 0
      }));
      edges.value = data.edges || [];
      dragPos.value = {};
      if (!activeId.value && nodes.value.length) activeId.value = nodes.value[0].point_id;
    } catch (e: any) {
      error.value = e?.message || '加载失败';
    } finally {
      loading.value = false;
    }
    return;
  }
  try {
    const [nodeRes, edgeRes, habitRes, sampleRes] = await Promise.all([
      apiFetch('/api/knowledge/kg/nodes/mine?limit=60'),
      apiFetch('/api/knowledge/kg/edges/mine?limit=120'),
      apiFetch('/api/knowledge/kg/habits/mine?days=30'),
      apiFetch('/api/knowledge/kg/sample?n=5')
    ]);
    nodes.value = (await nodeRes.json()).items || [];
    edges.value = (await edgeRes.json()).items || [];
    habits.value = { ...habits.value, ...(await habitRes.json()) };
    samples.value = (await sampleRes.json()).items || [];
    if (!activeId.value && nodes.value.length) activeId.value = nodes.value[0].point_id;
  } catch (e: any) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

defineExpose({ loadAll });

onMounted(loadAll);
</script>

<style scoped>
.kgp-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 14px;
}
.kgp-canvas-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  padding: 10px;
}
.kgp-svg {
  width: 100%;
  height: 380px;
}
.is-compact .kgp-svg {
  height: 330px;
}
.kgp-label {
  font-size: 10px;
  fill: #1f2937;
  pointer-events: none;
}
.kgp-node {
  cursor: pointer;
}
.kgp-node.is-active circle {
  stroke: #f59e0b;
  stroke-width: 3;
}
.kgp-node-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
  font-size: 12px;
  color: #4b5563;
}

.kgp-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kgp-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
}
.kgp-card h3 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}
.kgp-summary {
  margin: 0 0 8px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}
.kgp-kv {
  display: grid;
  grid-template-columns: 82px 1fr;
  gap: 3px 8px;
  margin: 0;
  font-size: 12px;
}
.kgp-kv dt {
  color: #9ca3af;
}
.kgp-kv dd {
  margin: 0;
  color: #1f2937;
}
.kgp-samples {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kgp-samples li {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-bottom: 5px;
  border-bottom: 1px dashed #eef2f7;
}
.kgp-samples li:last-child {
  border-bottom: none;
}
.kgp-sample-name {
  font-size: 12px;
  color: #1f2937;
}
.kgp-sample-meta {
  font-size: 11px;
  color: #9ca3af;
}
.kgp-empty {
  padding: 48px 16px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}
.kgp-hint {
  font-size: 12px;
  color: #9ca3af;
}
.kgp-error {
  margin-bottom: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

@media (max-width: 860px) {
  .kgp-grid {
    grid-template-columns: 1fr;
  }
}
/* 2026-11-09：手机端图谱布局（单列、矮画布、紧凑标签） */
@media (max-width: 768px) {
  .kgp-svg { height: 260px; }
  .is-compact .kgp-svg { height: 240px; }
  .kgp-label { font-size: 9px; }
  .kgp-canvas-card { padding: 6px; }
  .kgp-node-detail { gap: 4px 10px; font-size: 12px; padding: 6px 8px; }
  .kgp-side { gap: 10px; }
  .kgp-card { padding: 10px 12px; }
}
.kgp-node-detail-bottom {
  grid-column: 1 / -1;
  margin-top: 2px;
  background: #fff;
  border: 1px solid #e5e7eb;
}
/* 2026-11-09：弹窗内撑满高度，画布占据左侧全部空间，详情条固定在底部 */
.kgp { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.kgp-grid { flex: 1; min-height: 0; }
.kgp-canvas-card { min-height: 0; display: flex; flex-direction: column; }
.kgp-svg { flex: 1; height: auto; min-height: 320px; }
.is-compact .kgp-svg { flex: 1; height: auto; min-height: 260px; }
.kgp-side { overflow-y: auto; min-height: 0; }
.is-global .kgp-grid { grid-template-columns: minmax(0, 1fr); }
.is-global .kgp-side { display: none; }
</style>
