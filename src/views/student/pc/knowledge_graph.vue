<template>
  <div class="kg-page">
    <header class="kg-head">
      <div>
        <h1>我的知识图谱</h1>
        <p class="kg-sub">
          节点大小 = 生长热度，颜色 = 掌握度（红→绿）；连线粗细 = 边权重。图谱只反映你自己的学习轨迹。
        </p>
      </div>
      <div class="kg-actions">
        <button class="kg-btn" :disabled="generating" @click="generateTasks">
          {{ generating ? '生成中…' : '生成本周个性化任务' }}
        </button>
        <button class="kg-btn" @click="loadAll">刷新</button>
      </div>
    </header>

    <div v-if="error" class="kg-error">{{ error }}</div>

    <section class="kg-grid">
      <div class="kg-canvas-card">
        <div v-if="loading" class="kg-empty">加载中…</div>
        <div v-else-if="!nodes.length" class="kg-empty">
          <p>还没有图谱数据。</p>
          <p class="kg-hint">去刷几道题，系统会自动为你的知识点建节点、连边。</p>
        </div>

        <svg v-else class="kg-svg" :viewBox="`0 0 ${svgW} ${svgH}`" role="img" aria-label="知识图谱">
          <g class="kg-edges">
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
          <g class="kg-nodes">
            <g
              v-for="node in nodes"
              :key="node.point_id"
              class="kg-node"
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
                class="kg-label"
                text-anchor="middle"
              >
                {{ shortName(node.point_name) }}
              </text>
            </g>
          </g>
        </svg>

        <div v-if="activeNode" class="kg-node-detail">
          <strong>{{ activeNode.point_name }}</strong>
          <span>掌握度 {{ (activeNode.mastery * 100).toFixed(0) }}%</span>
          <span>热度 {{ activeNode.heat.toFixed(2) }}</span>
          <span>贡献度 {{ activeNode.contribution.toFixed(2) }}</span>
          <span>答题 {{ activeNode.attempt_count }} 次 / 对 {{ activeNode.correct_count }}</span>
        </div>
      </div>

      <aside class="kg-side">
        <div class="kg-card">
          <h3>做题习惯</h3>
          <p class="kg-summary">{{ habits.habit_summary }}</p>
          <dl class="kg-kv">
            <dt>偏好时段</dt><dd>{{ slotText(habits.preferred_slot) }}</dd>
            <dt>节奏稳定度</dt><dd>{{ (habits.stability * 100).toFixed(0) }}%</dd>
            <dt>单次时长</dt><dd>{{ habits.avg_time_spent }} 秒</dd>
            <dt>近 30 天记录</dt><dd>{{ habits.total_records }} 条</dd>
            <dt>采样温度 T</dt><dd>{{ habits.temperature }}（{{ temperatureHint }}）</dd>
          </dl>
        </div>

        <div class="kg-card">
          <h3>本周任务候选</h3>
          <ul class="kg-samples">
            <li v-for="s in samples" :key="s.point_id">
              <span class="kg-sample-name">{{ s.point_name }}</span>
              <span class="kg-sample-meta">p={{ (s.probability * 100).toFixed(1) }}% · 贡献 {{ s.contribution.toFixed(2) }}</span>
            </li>
          </ul>
          <p v-if="!samples.length" class="kg-hint">暂无候选（先积累答题行为）</p>
        </div>

        <div class="kg-card">
          <h3>最热的节点</h3>
          <ul class="kg-samples">
            <li v-for="n in topNodes" :key="n.point_id">
              <span class="kg-sample-name">{{ n.point_name }}</span>
              <span class="kg-sample-meta">热度 {{ n.heat.toFixed(2) }} · 掌握 {{ (n.mastery * 100).toFixed(0) }}%</span>
            </li>
          </ul>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

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
const generating = ref(false);
const error = ref('');
const activeId = ref<number | null>(null);

const svgW = 640;
const svgH = 480;

const activeNode = computed(() => nodes.value.find((n) => n.point_id === activeId.value) || null);
const topNodes = computed(() => [...nodes.value].sort((a, b) => b.heat - a.heat).slice(0, 5));

const temperatureHint = computed(() =>
  habits.value.temperature < 0.7
    ? '节奏稳定，聚焦薄弱点'
    : habits.value.temperature > 1.0
      ? '节奏波动大，多探索'
      : '节奏一般，正常探索'
);

/** 环形布局：按节点数均分角度，热度大的靠内圈 */
const pos = computed<Record<number, { x: number; y: number }>>(() => {
  const list = [...nodes.value].sort((a, b) => b.heat - a.heat);
  const cx = svgW / 2;
  const cy = svgH / 2;
  const map: Record<number, { x: number; y: number }> = {};
  list.forEach((node, i) => {
    const angle = (i / Math.max(1, list.length)) * Math.PI * 2 - Math.PI / 2;
    const ring = 90 + (i % 3) * 55;
    map[node.point_id] = {
      x: cx + Math.cos(angle) * ring,
      y: cy + Math.sin(angle) * ring
    };
  });
  return map;
});

function nodeRadius(node: KgNode): number {
  return Math.min(30, 10 + Math.sqrt(Math.max(0, node.heat)) * 6);
}

function masteryColor(mastery: number): string {
  // 红(0) → 黄(0.5) → 绿(1)
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
    const nodeBody = await nodeRes.json();
    const edgeBody = await edgeRes.json();
    const habitBody = await habitRes.json();
    const sampleBody = await sampleRes.json();

    nodes.value = nodeBody.items || [];
    edges.value = edgeBody.items || [];
    habits.value = { ...habits.value, ...habitBody };
    samples.value = sampleBody.items || [];
    if (!activeId.value && nodes.value.length) activeId.value = nodes.value[0].point_id;
  } catch (e: any) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function generateTasks(): Promise<void> {
  generating.value = true;
  try {
    const res = await apiFetch('/api/knowledge/kg/generate?n=2', { method: 'POST' });
    const body = await res.json();
    ElMessage.success(`已生成 ${body.created ?? 0} 个个性化任务`);
    await loadAll();
  } catch (e: any) {
    ElMessage.error(e?.message || '生成失败');
  } finally {
    generating.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
.kg-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  font-family: 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
  color: #1a1a1a;
}
.kg-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.kg-head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
}
.kg-sub {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}
.kg-actions {
  display: flex;
  gap: 8px;
}
.kg-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.kg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.kg-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
}
.kg-canvas-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #fff;
  padding: 12px;
  min-height: 520px;
}
.kg-svg {
  width: 100%;
  height: 480px;
}
.kg-label {
  font-size: 10px;
  fill: #1f2937;
  pointer-events: none;
}
.kg-node {
  cursor: pointer;
}
.kg-node.is-active circle {
  stroke: #f59e0b;
  stroke-width: 3;
}
.kg-node-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  font-size: 12px;
  color: #4b5563;
}

.kg-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kg-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  padding: 14px 16px;
}
.kg-card h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}
.kg-summary {
  margin: 0 0 10px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}
.kg-kv {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 4px 8px;
  margin: 0;
  font-size: 12px;
}
.kg-kv dt {
  color: #9ca3af;
}
.kg-kv dd {
  margin: 0;
  color: #1f2937;
}
.kg-samples {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kg-samples li {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: 6px;
  border-bottom: 1px dashed #eef2f7;
}
.kg-samples li:last-child {
  border-bottom: none;
}
.kg-sample-name {
  font-size: 13px;
  color: #1f2937;
}
.kg-sample-meta {
  font-size: 11px;
  color: #9ca3af;
}
.kg-empty {
  padding: 60px 16px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}
.kg-hint {
  font-size: 12px;
  color: #9ca3af;
}
.kg-error {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

@media (max-width: 980px) {
  .kg-grid {
    grid-template-columns: 1fr;
  }
}
</style>
