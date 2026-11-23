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

        <svg
          v-else
          ref="svgRef"
          class="kgp-svg"
          :class="{ 'is-panning': panning }"
          :viewBox="viewBox"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="知识图谱"
          style="touch-action: none"
          @wheel.prevent="onWheel"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
          @dblclick="resetLayout"
        >
          <rect
            class="kgp-bg"
            :x="view.x - 2000"
            :y="view.y - 2000"
            :width="view.w + 4000"
            :height="view.h + 4000"
            fill="transparent"
          />
          <g class="kgp-edges">
            <path
              v-for="(e, index) in edges"
              :key="index"
              :d="edgePath(e)"
              fill="none"
              :stroke="edgeStroke(e)"
              :stroke-width="edgeStrokeWidth(e)"
              :stroke-opacity="edgeOpacity(e)"
            />
          </g>
          <g class="kgp-nodes">
            <g
              v-for="node in nodes"
              :key="node.point_id"
              class="kgp-node"
              :class="{
                'is-active': activeId === node.point_id,
                'is-hovered': hoverId === node.point_id,
                'is-dimmed': isDimmed(node)
              }"
              :style="{ opacity: nodeOpacity(node) }"
              @pointerenter="onNodeEnter(node)"
              @pointerleave="onNodeLeave(node)"
              @pointerdown.stop="startDrag(node, $event)"
            >
              <circle
                :class="{ 'is-breathing': breathingIds.has(node.point_id) }"
                :cx="displayPos(node).x"
                :cy="displayPos(node).y"
                :r="nodeRadius(node)"
                :fill="nodeColor(node)"
                fill-opacity="0.9"
                :stroke="hoverId === node.point_id ? '#0f172a' : isRelated(node) ? '#334155' : '#ffffff'"
                :stroke-width="hoverId === node.point_id ? 2 : 1.5"
              />
              <text
                class="kgp-label"
                :x="displayPos(node).x"
                :y="displayPos(node).y + nodeRadius(node) + 12"
                text-anchor="middle"
              >{{ shortName(node.point_name) }}</text>
            </g>
          </g>
          <g
            v-if="hoverNode"
            class="kgp-tip"
            :transform="'translate(' + tooltip.x + ',' + tooltip.y + ')'"
            pointer-events="none"
          >
            <rect :width="tooltip.w" height="46" rx="9" fill="#ffffff" stroke="#e2e8f0" />
            <text class="kgp-tip-name" x="10" y="19">{{ hoverNode.point_name }}</text>
            <text class="kgp-tip-meta" x="10" y="36">
              热度 {{ hoverNode.heat.toFixed(2) }} · 掌握 {{ (hoverNode.mastery * 100).toFixed(0) }}% · 答题 {{ hoverNode.attempt_count }} 次
            </text>
          </g>
        </svg>
        <p class="kgp-canvas-tip">缩放 / 拖拽平移 · 悬停或点按高亮关联 · 拖拽节点自动保存 · 双击复位</p>


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
              <span class="kgp-sample-meta">p={{ (s.probability * 100).toFixed(1) }}% · 吸收 {{ s.absorption_frequency.toFixed(2) }}</span>
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
        <span>吸收频率 {{ activeNode.absorption_frequency.toFixed(2) }}</span>
        <span>答题 {{ activeNode.attempt_count }} 次 / 对 {{ activeNode.correct_count }}</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

interface KgNode {
  point_id: number;
  point_name: string;
  mastery: number;
  heat: number;
  attempt_count: number;
  correct_count: number;
  absorption_frequency: number;
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
  absorption_frequency: number;
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

const SVG_W = 1200;
const SVG_H = 800;

/** 视图（viewBox）：任意方向拖拽平移 + 以鼠标位置为中心缩放 */
const view = reactive({ x: -SVG_W / 2, y: -SVG_H / 2, w: SVG_W, h: SVG_H });
const viewBox = computed(() => view.x + ' ' + view.y + ' ' + view.w + ' ' + view.h);

const hoverId = ref<number | null>(null);
const panning = ref(false);
let panStart: { clientX: number; clientY: number; viewX: number; viewY: number } | null = null;

/** 节点拖拽 */
const dragPos = ref<Record<number, { x: number; y: number }>>({});
const dragId = ref<number | null>(null);
let dragOffset = { dx: 0, dy: 0 };
let dragMoved = 0;
let dragStart = { x: 0, y: 0 };

const svgRef = ref<SVGSVGElement | null>(null);

const activeNode = computed(
  () => nodes.value.find((node) => node.point_id === activeId.value) || null
);
const topNodes = computed(() => [...nodes.value].sort((a, b) => b.heat - a.heat).slice(0, 5));
const temperatureHint = computed(() =>
  habits.value.temperature < 0.7
    ? '节奏稳定，聚焦薄弱点'
    : habits.value.temperature > 1.0
      ? '节奏波动大，多探索'
      : '节奏一般，正常探索'
);

const hoverNode = computed(
  () => nodes.value.find((node) => node.point_id === hoverId.value) || null
);

const adjacency = computed(() => {
  const map = new Map<number, Set<number>>();
  for (const node of nodes.value) map.set(node.point_id, new Set());
  for (const edge of edges.value) {
    map.get(edge.src_point)?.add(edge.dst_point);
    map.get(edge.dst_point)?.add(edge.src_point);
  }
  return map;
});

/** 悬停节点 + 直接邻居；null 表示当前没有悬停 */
const relatedIds = computed<Set<number> | null>(() => {
  if (hoverId.value == null) return null;
  const set = new Set<number>([hoverId.value]);
  for (const id of adjacency.value.get(hoverId.value) || []) set.add(id);
  return set;
});

function isRelated(node: KgNode): boolean {
  return relatedIds.value ? relatedIds.value.has(node.point_id) : false;
}
function isDimmed(node: KgNode): boolean {
  return relatedIds.value ? !relatedIds.value.has(node.point_id) : false;
}
function nodeOpacity(node: KgNode): number {
  return isDimmed(node) ? 0.12 : 1;
}

/** 标签宽度估算（10px 字号，中文按 10px/字） */
function labelWidth(node: KgNode): number {
  return shortName(node.point_name).length * 10;
}

/** 碰撞半径：圆 + 下方标签都算进去，保证节点不重叠 */
function collisionRadius(node: KgNode): number {
  return Math.max(nodeRadius(node), labelWidth(node) / 2) + 8;
}

/**
 * 力导向布局 + 碰撞分离。
 * 先跑斥力/弹簧/向心力，再对每一对节点做碰撞分离，最后以质心为原点。
 * 不再把布局强行拉伸铺满画布，避免压缩后节点互相压住。
 */
const layout = computed<Record<number, { x: number; y: number }>>(() => {
  const list = [...nodes.value];
  const n = list.length;
  const map: Record<number, { x: number; y: number }> = {};
  if (!n) return map;

  const xs = new Array<number>(n).fill(0);
  const ys = new Array<number>(n).fill(0);
  const radii = list.map((node) => collisionRadius(node));
  const idx: Record<number, number> = {};

  list.forEach((node, i) => {
    idx[node.point_id] = i;
    const angle = i * 2.399963229728653;
    const radius = 90 + (i % 5) * 40;
    xs[i] = Math.cos(angle) * radius;
    ys[i] = Math.sin(angle) * radius;
  });

  const links = edges.value.filter(
    (e) => idx[e.src_point] !== undefined && idx[e.dst_point] !== undefined
  );
  const k = Math.sqrt((SVG_W * SVG_H) / Math.max(1, n)) * 0.62;
  let temp = 40;

  for (let it = 0; it < 420; it++) {
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
      const f = ((d * d) / k) * 0.55;
      const fx = (vx / d) * f;
      const fy = (vy / d) * f;
      dx[i] -= fx;
      dy[i] -= fy;
      dx[j] += fx;
      dy[j] += fy;
    }

    // 向心力（防散架）
    for (let i = 0; i < n; i++) {
      dx[i] -= xs[i] * 0.03;
      dy[i] -= ys[i] * 0.03;
    }

    // 位移动画（退火）
    for (let i = 0; i < n; i++) {
      const d = Math.max(0.001, Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i]));
      const step = Math.min(d, temp);
      xs[i] += (dx[i] / d) * step;
      ys[i] += (dy[i] / d) * step;
    }

    // 碰撞分离：任何两个节点（含标签）都不允许重叠
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let vx = xs[j] - xs[i];
        let vy = ys[j] - ys[i];
        let d = Math.sqrt(vx * vx + vy * vy);
        const minD = radii[i] + radii[j];
        if (d >= minD) continue;
        if (d < 0.001) {
          vx = 1;
          vy = 0;
          d = 1;
        }
        const push = (minD - d) / 2;
        xs[i] -= (vx / d) * push;
        ys[i] -= (vy / d) * push;
        xs[j] += (vx / d) * push;
        ys[j] += (vy / d) * push;
      }
    }

    temp *= 0.965;
  }

  // 收缩到合理视口范围：孤立节点/长链容易被斥力推到很远，会把整张图压小
  const maxRadius = Math.min(SVG_W, SVG_H) * 0.38;
  for (let i = 0; i < n; i++) {
    const d = Math.sqrt(xs[i] * xs[i] + ys[i] * ys[i]);
    if (d > maxRadius) {
      const ratio = maxRadius / d;
      xs[i] *= ratio;
      ys[i] *= ratio;
    }
  }
  // 收缩后可能产生新的重叠，再松弛若干轮
  for (let pass = 0; pass < 200; pass++) {
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let vx = xs[j] - xs[i];
        let vy = ys[j] - ys[i];
        let d = Math.sqrt(vx * vx + vy * vy);
        const minD = radii[i] + radii[j];
        if (d >= minD) continue;
        if (d < 0.001) {
          vx = 1;
          vy = 0;
          d = 1;
        }
        const push = (minD - d) / 2;
        xs[i] -= (vx / d) * push;
        ys[i] -= (vy / d) * push;
        xs[j] += (vx / d) * push;
        ys[j] += (vy / d) * push;
      }
    }
  }

  const cx = xs.reduce((sum, value) => sum + value, 0) / n;
  const cy = ys.reduce((sum, value) => sum + value, 0) / n;
  list.forEach((node, i) => {
    map[node.point_id] = { x: xs[i] - cx, y: ys[i] - cy };
  });
  return map;
});

function displayPos(node: KgNode): { x: number; y: number } {
  return dragPos.value[node.point_id] || layout.value[node.point_id] || { x: 0, y: 0 };
}
function displayPosById(id: number): { x: number; y: number } {
  return dragPos.value[id] || layout.value[id] || { x: 0, y: 0 };
}

/** 把当前布局完整装进视口 */
function fitView() {
  const list = nodes.value;
  if (!list.length) return;
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const node of list) {
    const point = dragPos.value[node.point_id] || layout.value[node.point_id];
    if (!point) continue;
    const r = nodeRadius(node);
    const halfLabel = labelWidth(node) / 2;
    const half = Math.max(r, halfLabel);
    minX = Math.min(minX, point.x - half);
    maxX = Math.max(maxX, point.x + half);
    minY = Math.min(minY, point.y - r);
    maxY = Math.max(maxY, point.y + r + 16);
  }
  if (!isFinite(minX)) return;
  const pad = 40;
  const width = Math.max(260, maxX - minX + pad * 2);
  const height = Math.max(200, maxY - minY + pad * 2);
  view.w = width;
  view.h = height;
  view.x = (minX + maxX) / 2 - width / 2;
  view.y = (minY + maxY) / 2 - height / 2;
}

function edgePath(e: KgEdge): string {
  const a = displayPosById(e.src_point);
  const b = displayPosById(e.dst_point);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const bend = Math.min(50, len * 0.12);
  const mx = (a.x + b.x) / 2 + nx * bend;
  const my = (a.y + b.y) / 2 + ny * bend;
  return 'M' + a.x + ',' + a.y + ' Q' + mx + ',' + my + ' ' + b.x + ',' + b.y;
}

/** client 坐标 → SVG 用户坐标（自动处理 viewBox 缩放/平移与 letterbox） */
function toSvg(e: PointerEvent | WheelEvent): { x: number; y: number } {
  const el = svgRef.value;
  if (!el) return { x: 0, y: 0 };
  const ctm = el.getScreenCTM();
  if (!ctm) {
    const rect = el.getBoundingClientRect();
    return {
      x: view.x + ((e.clientX - rect.left) / Math.max(1, rect.width)) * view.w,
      y: view.y + ((e.clientY - rect.top) / Math.max(1, rect.height)) * view.h
    };
  }
  const point = el.createSVGPoint();
  point.x = e.clientX;
  point.y = e.clientY;
  const mapped = point.matrixTransform(ctm.inverse());
  return { x: mapped.x, y: mapped.y };
}

function onWheel(e: WheelEvent) {
  const cursor = toSvg(e);
  const factor = e.deltaY > 0 ? 1.15 : 0.87;
  const nextW = Math.min(6000, Math.max(140, view.w * factor));
  const k = nextW / view.w;
  view.x = cursor.x - (cursor.x - view.x) * k;
  view.y = cursor.y - (cursor.y - view.y) * k;
  view.w = nextW;
  view.h = view.h * k;
}

function onPointerDown(e: PointerEvent) {
  if (dragId.value != null) return;
  const target = e.target as Element | null;
  if (!target) return;
  const isBackground = target === svgRef.value || target.classList.contains('kgp-bg');
  if (!isBackground) return;
  panStart = { clientX: e.clientX, clientY: e.clientY, viewX: view.x, viewY: view.y };
  panning.value = true;
  svgRef.value?.setPointerCapture?.(e.pointerId);
}

function onPointerMove(e: PointerEvent) {
  if (dragId.value != null) {
    dragMoved = Math.max(
      dragMoved,
      Math.abs(e.clientX - dragStart.x) + Math.abs(e.clientY - dragStart.y)
    );
    const cursor = toSvg(e);
    dragPos.value = {
      ...dragPos.value,
      [dragId.value]: { x: cursor.x + dragOffset.dx, y: cursor.y + dragOffset.dy }
    };
    return;
  }
  if (!panStart) return;
  const el = svgRef.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  // preserveAspectRatio=meet：x/y 使用同一个缩放比
  const unitsPerPx = Math.max(
    view.w / Math.max(1, rect.width),
    view.h / Math.max(1, rect.height)
  );
  view.x = panStart.viewX - (e.clientX - panStart.clientX) * unitsPerPx;
  view.y = panStart.viewY - (e.clientY - panStart.clientY) * unitsPerPx;
}

function onPointerUp() {
  if (dragId.value != null) {
    const moved = dragMoved >= 5;
    if (!moved) activeId.value = dragId.value;
    dragId.value = null;
    dragMoved = 0;
    // 真拖拽（不是点击选中）才写库，避免点一下就产生一次保存请求
    if (moved) scheduleSaveLayout();
  }
  panStart = null;
  panning.value = false;
}

function onNodeEnter(node: KgNode) {
  if (dragId.value == null) hoverId.value = node.point_id;
}
function onNodeLeave(node: KgNode) {
  if (hoverId.value === node.point_id) hoverId.value = null;
}

function startDrag(node: KgNode, e: PointerEvent) {
  const point = displayPos(node);
  const cursor = toSvg(e);
  dragOffset = { dx: point.x - cursor.x, dy: point.y - cursor.y };
  dragId.value = node.point_id;
  dragMoved = 0;
  dragStart = { x: e.clientX, y: e.clientY };
  (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
}

const tooltip = computed(() => {
  const node = hoverNode.value;
  if (!node) return { x: 0, y: 0, w: 0 };
  const point = displayPos(node);
  const r = nodeRadius(node);
  const w = Math.max(170, Math.min(280, 30 + node.point_name.length * 12));
  const right = point.x + r + 10;
  const x = right + w > view.x + view.w ? point.x - r - 10 - w : right;
  return { x, y: point.y - 18, w };
});

const NODE_PALETTE = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4'];
function nodeColor(node: KgNode): string {
  return NODE_PALETTE[Math.abs(node.point_id) % NODE_PALETTE.length];
}

/** 呼吸感只给「最值得吸收」的一小撮节点：全图一起动既晃眼也掉帧。 */
const breathingIds = computed(() => {
  const top = [...nodes.value]
    .filter((n) => (n.heat || 0) > 0)
    .sort((a, b) => (b.absorption_frequency || 0) - (a.absorption_frequency || 0))
    .slice(0, 30);
  return new Set(top.map((n) => n.point_id));
});

function nodeRadius(node: KgNode): number {
  return Math.min(30, 12 + Math.sqrt(Math.max(0, node.heat)) * 5);
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

function isEdgeRelated(e: KgEdge): boolean {
  if (hoverId.value == null) return false;
  return e.src_point === hoverId.value || e.dst_point === hoverId.value;
}

/** 悬停时：相关边高亮成节点色，其余边淡到几乎看不见 */
function edgeStroke(e: KgEdge): string {
  if (isEdgeRelated(e) && hoverNode.value) return nodeColor(hoverNode.value);
  return '#94a3b8';
}

function edgeStrokeWidth(e: KgEdge): number {
  if (isEdgeRelated(e)) return Math.min(4, 1.4 + Math.max(0, e.weight - 1) * 0.6);
  return Math.min(1.6, 0.8 + Math.max(0, e.weight - 1) * 0.3);
}

function edgeOpacity(e: KgEdge): number {
  if (hoverId.value != null) return isEdgeRelated(e) ? 0.6 : 0.04;
  return Math.min(0.45, 0.12 + Math.max(0, e.weight - 1) * 0.08);
}

function slotText(slot: string | null): string {
  return { morning: '上午', afternoon: '下午', evening: '晚上', night: '深夜' }[slot || ''] || '暂无';
}

function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
}

/**
 * 布局持久化（2026-11-15）：
 * - 拖拽结束 → 700ms 防抖写回 /api/knowledge/kg/layout（(user,mode,point_id) 幂等 upsert）；
 * - 重新载入 / 换设备 → 先按自动布局算，再把库里的坐标盖上去；
 * - 双击复位 → 清空该模式的坐标并写库，下次进来回到自动布局。
 */
let restoringLayout = false;
let saveTimer: ReturnType<typeof setTimeout> | null = null;

/** 只提交当前图上仍存在的节点，避免历史节点坐标越攒越多 */
function layoutNodesPayload(): Array<{ point_id: number; x: number; y: number }> {
  const ids = new Set(nodes.value.map((node) => node.point_id));
  return Object.entries(dragPos.value)
    .map(([id, point]) => ({
      point_id: Number(id),
      x: Math.round(point.x * 100) / 100,
      y: Math.round(point.y * 100) / 100
    }))
    .filter((item) => ids.has(item.point_id));
}

async function applySavedLayout(): Promise<void> {
  try {
    const res = await apiFetch('/api/knowledge/kg/layout?mode=' + props.mode);
    if (!res.ok) return;
    const data = await res.json();
    const ids = new Set(nodes.value.map((node) => node.point_id));
    const map: Record<number, { x: number; y: number }> = {};
    for (const item of data.nodes || []) {
      if (ids.has(item.point_id)) map[item.point_id] = { x: item.x, y: item.y };
    }
    dragPos.value = map;
  } catch (e) {
    /* 读不到坐标就用自动布局，不打扰用户 */
  }
}

async function saveLayout(): Promise<void> {
  const items = layoutNodesPayload();
  if (!items.length) return;
  try {
    await apiFetch('/api/knowledge/kg/layout', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: props.mode, nodes: items })
    });
  } catch (e) {
    /* 写库失败不影响本次拖拽效果 */
  }
}

function scheduleSaveLayout(): void {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveTimer = null;
    void saveLayout();
  }, 700);
}

/** 双击复位：清空手动坐标 → 回到自动布局，并把「已清空」写回后端 */
async function resetLayout(): Promise<void> {
  dragPos.value = {};
  hoverId.value = null;
  fitView();
  try {
    await apiFetch('/api/knowledge/kg/layout', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: props.mode, reset: true })
    });
  } catch (e) {
    /* 复位已在本地生效；写库失败时下次拖拽会重新覆盖 */
  }
}

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = '';
  restoringLayout = true;
  try {
    if (props.mode === 'global') {
      const res = await apiFetch('/api/knowledge/kg/global?limit=800');
      const data = await res.json();
      nodes.value = (data.nodes || []).map((n: any) => ({
        point_id: n.point_id,
        point_name: n.point_name,
        mastery: n.mastery || 0,
        heat: n.heat || 0,
        attempt_count: n.attempt_count || 0,
        correct_count: n.correct_count || 0,
        absorption_frequency: n.absorption_frequency || 0
      }));
      edges.value = data.edges || [];
    } else {
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
    }
    if (!activeId.value && nodes.value.length) activeId.value = nodes.value[0].point_id;
    // 节点就位后再盖手动坐标，否则等于白读
    await applySavedLayout();
  } catch (e: any) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
    nextTick(() => {
      restoringLayout = false;
      fitView();
    });
  }
}

defineExpose({ loadAll });

// 数据变化后重置拖拽并重新适配视口（节点铺满但不重叠）；回填坐标期间不重置
watch(
  [nodes, edges],
  () => {
    if (restoringLayout) return;
    dragPos.value = {};
    hoverId.value = null;
    nextTick(() => fitView());
  },
  { flush: 'post' }
);

onMounted(loadAll);
onBeforeUnmount(() => {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
});
</script>

<style scoped>
.kgp-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 14px;
}
.kgp-canvas-card {
  position: relative;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  padding: 10px;
}
.kgp-svg {
  width: 100%;
  height: 380px;
  cursor: grab;
  background: #fff;
}
.kgp-svg.is-panning {
  cursor: grabbing;
}
.is-compact .kgp-svg {
  height: 330px;
}
.kgp-label {
  font-size: 10px;
  fill: #475569;
  pointer-events: none;
  paint-order: stroke;
  stroke: #ffffff;
  stroke-width: 3px;
  stroke-linejoin: round;
}
.kgp-node {
  cursor: grab;
  transition: opacity 0.16s ease;
}
.kgp-node:active {
  cursor: grabbing;
}
.kgp-node circle {
  transition: stroke 0.16s ease, stroke-width 0.16s ease;
}
.kgp-node.is-active circle {
  stroke: #f59e0b;
  stroke-width: 3;
}
@keyframes kgp-breathe {
  0%, 100% { opacity: 0.82; filter: drop-shadow(0 0 0 rgba(37, 99, 235, 0)); }
  50% { opacity: 1; filter: drop-shadow(0 0 7px rgba(37, 99, 235, 0.55)); }
}
.kgp-node circle.is-breathing {
  animation: kgp-breathe 2.8s ease-in-out infinite;
  transform-box: fill-box;
  transform-origin: center;
}
@media (prefers-reduced-motion: reduce) {
  .kgp-node circle.is-breathing { animation: none; }
}
.kgp-tip-name {
  font-size: 12px;
  font-weight: 600;
  fill: #0f172a;
}
.kgp-tip-meta {
  font-size: 10.5px;
  fill: #64748b;
}
.kgp-canvas-tip {
  position: absolute;
  left: 18px;
  bottom: 14px;
  margin: 0;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  font-size: 11px;
  color: #94a3b8;
  pointer-events: none;
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
  .kgp-canvas-tip { left: 10px; bottom: 8px; font-size: 10px; }
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

/* ===== 手机端（2026-11-15）：单列 + 紧凑排版，避免 1fr+300px 两列在 390px 屏上挤成一团 ===== */
@media (max-width: 640px) {
  .kgp-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
  }
  .kgp-canvas-card {
    padding: 6px;
    border-radius: 14px;
    background: linear-gradient(180deg, #f8fafc 0%, #ffffff 42%);
  }
  .kgp-svg {
    height: 300px;
  }
  .is-compact .kgp-svg {
    height: 270px;
  }
  /* 提示从「压在画布上」改成「画布下方一行」，小屏不再遮挡节点 */
  .kgp-canvas-tip {
    position: static;
    margin: 6px 0 0;
    padding: 0;
    background: transparent;
    font-size: 10.5px;
    line-height: 1.5;
    text-align: center;
    color: #9aa4b8;
  }
  .kgp-side {
    gap: 8px;
  }
  .kgp-card {
    padding: 10px 12px;
    border-radius: 12px;
  }
  .kgp-card h3 {
    margin: 0 0 6px;
    font-size: 12.5px;
  }
  .kgp-summary {
    font-size: 11.5px;
    margin-bottom: 6px;
  }
  .kgp-kv {
    grid-template-columns: 72px 1fr;
    font-size: 11.5px;
  }
  /* 候选/最热节点：小屏改单行「名称 …… 指标」，比堆两行更省高度也更好扫读 */
  .kgp-samples li {
    flex-direction: row;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    padding: 0 0 6px;
    border-bottom: 1px dashed #eef2f7;
  }
  .kgp-samples li:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
  .kgp-sample-name {
    font-size: 12px;
    color: #1f2937;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kgp-sample-meta {
    font-size: 10.5px;
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
  }
  .kgp-node-detail {
    padding: 8px 10px;
    font-size: 11.5px;
    gap: 4px 12px;
  }
  .kgp-node-detail-bottom {
    position: sticky;
    bottom: 8px;
    z-index: 5;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
  }
}
</style>