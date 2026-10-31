<template>
  <div class="recent-records">
    <div class="rr-head">
      <span class="rr-title">最近做题记录</span>
      <span class="rr-hint" v-if="!loading && !items.length">暂无记录</span>
      <span class="rr-hint" v-else-if="!loading">{{ total }} 条</span>
    </div>

    <div v-if="loading" class="rr-empty">加载中...</div>

    <div v-else-if="!items.length" class="rr-empty">
      还没有做题记录，完成练习后这里会显示最近的做题情况
    </div>

    <ul v-else class="rr-list">
      <li
        v-for="r in items"
        :key="r.record_key"
        class="rr-item"
        @click="go(r)"
      >
        <div class="rr-main">
          <div class="rr-name" :title="r.name">{{ r.name }}</div>
          <div class="rr-meta">
            <span class="rr-badge" :class="sourceClass(r.source)">{{ r.source }}</span>
            <span v-if="r.status === 'in_progress'" class="rr-doing">进行中</span>
            <span v-else-if="r.question_count">共 {{ r.question_count }} 题</span>
          </div>
        </div>
        <div class="rr-right">
          <div v-if="r.status === 'in_progress'" class="rr-cta">继续</div>
          <template v-else>
            <div v-if="r.score != null" class="rr-score">{{ r.score }} 分</div>
            <div class="rr-acc">{{ r.accuracy }}%</div>
          </template>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
/**
 * 最近做题记录（三端共用）
 *
 * 为什么做成共享组件：用户反馈「三端的最近做题记录不一致」。
 * 根因不是各自排错，而是三端**各写一套**渲染与排序逻辑。这里把
 * 数据获取、排序、空态、样式全部收敛到一处，三端渲染同一份代码，
 * 从结构上消除不一致的可能。
 *
 * 排序契约：完全依赖后端 `/api/practice/recent-records` 返回的顺序
 * （后端已按 recency 倒序），**前端不再二次排序**。若前端自行排序，
 * 三端会因各自的比较实现而重新产生分歧。
 *
 * limit 三端统一为 5，与用户可见区域匹配。
 */
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useDataSync } from '@/composables/useDataSync';

const props = withDefaults(defineProps<{ limit?: number }>(), { limit: 5 });

const router = useRouter();
const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);

/** 来源徽标配色：与项目既有主题一致，四来源可区分 */
function sourceClass(source: string) {
  const map: Record<string, string> = {
    快速练习: 'rp-qp',
    历年试卷: 'rp-paper',
    小模考: 'rp-mock',
    智能组卷: 'rp-smart',
  };
  return map[source] || 'rp-other';
}

async function load() {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth || !auth.isLoggedIn()) return;
  loading.value = true;
  try {
    const res = await auth.apiFetch(
      `/api/practice/recent-records?limit=${props.limit}`
    );
    if (!res.ok) {
      items.value = [];
      total.value = 0;
      return;
    }
    const d = await res.json();
    items.value = Array.isArray(d.items) ? d.items : [];
    total.value = Number(d.total) || 0;
  } catch (e) {
    console.error('获取最近做题记录失败:', e);
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

/** 跳转沿用后端下发的 jump 契约，组件不自行拼路由，避免与后端映射漂移 */
function go(r: any) {
  const jump = r && r.jump;
  if (!jump || !jump.path) return;
  const params = jump.params || {};
  const q = Object.keys(params)
    .filter((k) => params[k] !== undefined && params[k] !== '')
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
    .join('&');
  router.push(q ? `${jump.path}?${q}` : jump.path);
}

// 只订阅练习相关变更；防抖 800ms 保留原有连续答题合并刷新的体验
useDataSync({
  domains: ['exam'],
  types: ['practice.submit', 'practice.record.created', 'paper.completed'],
  debounceMs: 800,
  handler: () => { load(); }
});

onMounted(() => {
  load();
});

defineExpose({ reload: load });
</script>

<style scoped>
.recent-records {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.rr-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}
.rr-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}
.rr-hint {
  font-size: 11px;
  color: #8a8faa;
}
.rr-empty {
  font-size: 13px;
  color: #8a8faa;
  padding: 14px 0;
  line-height: 1.6;
  text-align: center;
}
.rr-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.rr-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid #f2f4f8;
  cursor: pointer;
}
.rr-item:first-child {
  border-top: none;
}
.rr-item:active {
  opacity: 0.7;
}
.rr-main {
  min-width: 0;
  flex: 1;
}
.rr-name {
  font-size: 13px;
  color: #2c3550;
  /* 单行省略：三端统一，避免长试卷名撑破布局 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rr-meta {
  margin-top: 3px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #8a8faa;
}
.rr-badge {
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
  color: #fff;
}
.rp-qp { background: #2a5298; }
.rp-paper { background: #0ea5e9; }
.rp-mock { background: #f59e0b; }
.rp-smart { background: #8b5cf6; }
.rp-other { background: #94a3b8; }
.rr-doing {
  color: #f59e0b;
}
.rr-right {
  text-align: right;
  flex-shrink: 0;
}
.rr-score {
  font-size: 13px;
  font-weight: 700;
  color: #1a2b5f;
}
.rr-acc {
  font-size: 12px;
  color: #5a6488;
}
.rr-cta {
  font-size: 12px;
  color: #2a5298;
  font-weight: 600;
}
</style>