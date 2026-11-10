<template>
  <div class="kgp" :class="{ 'is-compact': compact }">
    <div v-if="error" class="kgp-error">{{ error }}</div>

    <section class="kgp-grid">
      <div class="kgp-canvas-card">
        <div v-if="loading" class="kgp-empty">加载中…</div>
        <div v-else-if="!nodes.length" class="kgp-empty">
          <p>还没有图谱数据。</p>
          <p class="kgp-hint">去刷几道题，系统会自动为你的知识点建节点、连边。</p>
        </div>

        <svg v-else class="kgp-svg" :viewBox="`0 0 ${svgW} ${svgH}`" role="img" aria-label="知识图谱">
          <g class="kgp-edges">
            <line
              v-for="e in edges"
              :key="`${e.src_point}-${e.dst_point}`"
              :x1="pos[e.src_point]?.x ?? 0"
              :y1="pos[e.src_point]?.y ?? 0"
              :x2="pos[e.dst_point]?.x ?? 0"
              :y2="pos[e.dst_point]?.y ?? 0"
              :stroke-width="edgeWidth(e)"
              :stroke-opacity="edgeOpacity(e)"
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
            >
              <circle
                :cx="pos[node.point_id]?.x ?? 0"
                :cy="pos[node.point_id]?.y ?? 0"
                :r="nodeRadius(node)"
                :fill="masteryColor(node.mastery)"
                fill-opacity="0.85"
                stroke="#1f2937"
                stroke-width="1"
              />
              <text
                :x="pos[node.point_id]?.x ?? 0"
                :y="(pos[node.point_id]?.y ?? 0) + 4"
                class="kgp-label"
                text-anchor="middle"
              >
                {{ shortName(node.point_name) }}
              </text>
            </g>
          </g>
        </svg>

        <div v-if="activeNode" class="kgp-node-detail">
          <strong>{{ activeNode.point_name }}</strong>
          <span>掌握度 {{ (activeNode.mastery * 100).toFixed(0) }}%</span>
          <span>热度 {{ activeNode.heat.toFixed(2) }}</span>
          <span>贡献度 {{ activeNode.contribution.toFixed(2) }}</span>
          <span>答题 {{ activeNode.attempt_count }} 次 / 对 {{ activeNode.correct_count }}</span>
        </div>
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

const props = withDefaults(defineProps<{ compact?: boolean; generateSignal?: number }>(), {
  compact: false,
  generateSignal: 0
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
  const list = [...nodes.value].sort((a, b) => b.heat - a.heat);
  const cx = svgW / 2;
  const cy = svgH / 2;
  const map: Record<number, { x: number; y: number }> = {};
  list.forEach((node, i) => {
    const angle = (i / Math.max(1, list.length)) * Math.PI * 2 - Math.PI / 2;
    const ring = 80 + (i % 3) * 50;
    map[node.point_id] = {
      x: cx + Math.cos(angle) * ring,
      y: cy + Math.sin(angle) * ring
    };
  });
  return map;
});

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
</style>
