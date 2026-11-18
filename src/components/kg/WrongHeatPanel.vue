<template>
  <section class="wh" aria-labelledby="wh-title">
    <div class="wh-head">
      <h2 id="wh-title">错题热力</h2>
      <p>颜色越深 = 错得越多；百分比 = 该范围的错题数占该范围题量的比例。</p>
    </div>

    <div v-if="loading" class="wh-skeleton" aria-live="polite" aria-busy="true">
      <span class="sk-title"></span>
      <span v-for="i in 5" :key="i" class="sk-bar"></span>
    </div>

    <p v-else-if="error" class="wh-state wh-error" role="alert">
      {{ error }}
      <button type="button" class="wh-retry" @click="loadAll">重试</button>
    </p>

    <template v-else>
      <p v-if="!subcats.length && !points.length" class="wh-state">
        还没有错题热力数据。先做一组练习，错题会自动落到考点上。
      </p>

      <div v-if="subcats.length" class="wh-block">
        <h3>子科目热力</h3>
        <ul class="wh-bars">
          <li v-for="item in subcats" :key="item.key">
            <span class="wh-bar-label" :title="item.name">{{ item.name }}</span>
            <span class="wh-bar-track">
              <span
                class="wh-bar-fill"
                :style="{ width: barWidth(item) + '%', background: fill(item.wrong_rate) }"></span>
            </span>
            <span class="wh-bar-num">
              {{ item.wrong_count }}<small>/{{ item.total }}</small>
            </span>
          </li>
        </ul>
      </div>

      <div v-if="points.length" class="wh-block">
        <h3>考点热力（前 {{ points.length }}）</h3>
        <ul class="wh-cells">
          <li
            v-for="item in points"
            :key="item.key"
            class="wh-cell"
            :style="{ background: fill(item.wrong_rate), color: onDark(item.wrong_rate) ? '#fff' : '#7f1d1d' }"
            :title="item.name + '：错 ' + item.wrong_count + ' 题 / 共 ' + item.total + ' 题，错误率 ' + item.wrong_rate + '%'">
            <span class="wh-cell-name">{{ item.name }}</span>
            <span class="wh-cell-num">{{ item.wrong_count }}</span>
          </li>
        </ul>
      </div>

      <p v-if="foldedFallback" class="wh-folded">
        已把 {{ foldedFallback }} 个「其他（未细分）」收容节点移出排名：它们没有细分考点，
        题量还会跨节点重叠，画进热力图只会变成「满屏其他」。这些错题仍可在错题集里
        用关键词检索、或到练习中心「其他（未细分）」直接练。
      </p>

      <p class="wh-hint">
        数据口径：本人错题 × 题目考点（question_knowledge），同一道题挂多个考点时分别计数；
        子科目热力的百分比 = 该子科目错题数 / 该子科目总题量。
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

interface HeatItem {
  key: string | number;
  name: string;
  wrong_count: number;
  error_count: number;
  total: number;
  wrong_rate: number;
}

const loading = ref(true);
const error = ref('');
const subcats = ref<HeatItem[]>([]);
const points = ref<HeatItem[]>([]);
/** 被移出排名的收容桶节点数（「其他（未细分）」），用于脚注说明而不是画格子 */
const foldedFallback = ref(0);

const maxRate = computed(() => {
  const rates = subcats.value.map((i) => i.wrong_rate).concat(points.value.map((i) => i.wrong_rate));
  return Math.max(5, ...rates);
});

function apiFetch(url: string): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url);
  return fetch(url, { credentials: 'include' });
}

/** 错误率 → 五档红色（分级阈值来自实测分布：多数子科目 <10%，热点考点 >25%） */
function fill(rate: number): string {
  if (rate >= 25) return '#ef4444';
  if (rate >= 15) return '#f87171';
  if (rate >= 8) return '#fca5a5';
  if (rate >= 3) return '#fecaca';
  return '#fee2e2';
}

function onDark(rate: number): boolean {
  return rate >= 15;
}

function barWidth(item: HeatItem): number {
  return Math.max(4, Math.round((item.wrong_rate / maxRate.value) * 100));
}

const FALLBACK_RE = /^(其他|未分类|未归类)/;

interface HeatPayload {
  items: HeatItem[];
  /** 被折叠的收容桶节点数（「其他（未细分）」在库里是 91 个独立节点） */
  foldedFallback: number;
}

/**
 * 同名考点合并 + 收容桶剔除。
 * 后端 dimension=point 按 point_id 聚合，91 个「其他（未细分）」节点会各占一行，
 * 直接渲染就是用户最初投诉的「满屏其他」；且它们的题目互相重叠，
 * 折叠成一行再相加会重复计数 —— 所以这里整段移出热力排名，只在脚注说明。
 */
function mergeItems(items: HeatItem[], limit: number): HeatPayload {
  const buckets = new Map<string, HeatItem>();
  let foldedFallback = 0;
  items.forEach((item) => {
    const name = String(item.name || '未命名');
    if (FALLBACK_RE.test(name)) {
      foldedFallback += 1;
      return;
    }
    const prev = buckets.get(name);
    if (prev) {
      prev.wrong_count += item.wrong_count;
      prev.error_count += item.error_count;
      prev.total += item.total;
    } else {
      buckets.set(name, {
        ...item,
        name,
        wrong_count: item.wrong_count,
        error_count: item.error_count,
        total: item.total
      });
    }
  });
  const merged = Array.from(buckets.values())
    .map((item) => ({
      ...item,
      wrong_rate: item.total > 0 ? Math.round((item.wrong_count * 1000) / item.total) / 10 : 0
    }))
    .sort((a, b) => b.wrong_count - a.wrong_count)
    .slice(0, limit);
  return { items: merged, foldedFallback };
}

async function loadOne(dimension: 'subcategory' | 'point', limit: number): Promise<HeatPayload> {
  const res = await apiFetch('/api/wrong-questions/point-stats?dimension=' + dimension + '&limit=' + limit);
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const body = await res.json();
  return mergeItems((body.items || []) as HeatItem[], limit);
}

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const [sc, pt] = await Promise.all([loadOne('subcategory', 12), loadOne('point', 50)]);
    subcats.value = sc.items;
    points.value = pt.items;
    foldedFallback.value = pt.foldedFallback;
  } catch (e: any) {
    error.value = '错题热力加载失败：' + (e?.message || '网络异常');
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
.wh {
  background: #fff;
  border-radius: 16px;
  padding: 20px 24px 24px;
  box-shadow: 0 1px 8px rgba(26, 43, 95, 0.06);
  font-family: 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
  color: #1a1a1a;
}
.wh-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
  line-height: 1.25;
  font-weight: 600;
}
.wh-head p {
  margin: 0 0 16px;
  font-size: 13px;
  color: #6b7280;
}
.wh-block + .wh-block {
  margin-top: 24px;
}
.wh-block h3 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}
.wh-bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wh-bars li {
  display: grid;
  grid-template-columns: 120px 1fr 64px;
  align-items: center;
  gap: 12px;
}
.wh-bar-label {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wh-bar-track {
  height: 12px;
  border-radius: 999px;
  background: #f3f4f6;
  overflow: hidden;
}
.wh-bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 240ms ease;
}
.wh-bar-num {
  font-size: 12px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #374151;
}
.wh-bar-num small {
  color: #9ca3af;
}
.wh-cells {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 8px;
}
.wh-cell {
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid rgba(239, 68, 68, 0.16);
  min-height: 52px;
}
.wh-cell-name {
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.wh-cell-num {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.wh-folded {
  margin: 16px 0 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  font-size: 12px;
  line-height: 1.7;
  color: #9a3412;
}
.wh-hint {
  margin: 16px 0 0;
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
}
.wh-state {
  margin: 8px 0;
  font-size: 13px;
  color: #6b7280;
}
.wh-error {
  color: #b91c1c;
}
.wh-retry {
  margin-left: 8px;
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.wh-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wh-skeleton .sk-title,
.wh-skeleton .sk-bar {
  display: block;
  border-radius: 8px;
  background: linear-gradient(90deg, #f3f4f6, #e5e7eb, #f3f4f6);
  background-size: 200% 100%;
  animation: wh-shimmer 1.2s infinite linear;
}
.wh-skeleton .sk-title {
  width: 40%;
  height: 16px;
}
.wh-skeleton .sk-bar {
  height: 12px;
}
@keyframes wh-shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}
.wh-retry:focus-visible,
.wh-cell:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
  .wh-bar-fill { transition: none; }
  .wh-skeleton .sk-title,
  .wh-skeleton .sk-bar { animation: none; }
}
</style>
