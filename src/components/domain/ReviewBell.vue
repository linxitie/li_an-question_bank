<template>
  <!-- 艾宾浩斯复习提醒：右下角常驻入口 + 待复习面板 -->
  <div v-if="!isAnswering" class="review-bell" :class="{ 'is-open': open }">
    <button
      v-if="!open"
      class="review-fab"
      type="button"
      :aria-label="dueTotal > 0 ? '今日有 ' + dueTotal + ' 道题待复习' : '复习提醒'"
      @click="openPanel"
    >
      <span class="review-fab__icon" aria-hidden="true">🔔</span>
      <span v-if="dueTotal > 0" class="review-fab__badge">{{ dueTotal > 99 ? '99+' : dueTotal }}</span>
      <span v-else class="review-fab__dot" aria-hidden="true"></span>
    </button>

    <section
      v-else
      class="review-panel"
      role="dialog"
      aria-modal="false"
      aria-label="艾宾浩斯复习提醒"
      @keydown.esc="closePanel"
    >
      <header class="review-panel__head">
        <div>
          <h3 class="review-panel__title">遗忘曲线复习</h3>
          <p class="review-panel__sub">{{ headNote }}</p>
        </div>
        <button class="review-panel__close" type="button" aria-label="收起" @click="closePanel">×</button>
      </header>

      <div v-if="loading" class="review-panel__state">正在读取复习队列…</div>
      <div v-else-if="error" class="review-panel__state review-panel__state--error">
        {{ error }}
        <button class="review-link" type="button" @click="load">重试</button>
      </div>
      <div v-else-if="!items.length" class="review-panel__state">
        今天没有到期复习，去练几道新题，明天这里会提醒你。
      </div>
      <ul v-else class="review-list">
        <li v-for="it in items" :key="it.question_id" class="review-item">
          <span class="review-item__subject">{{ subjectLabel(it.subject_id) }}</span>
          <span class="review-item__point">{{ it.point_name || '未细分考点' }}</span>
          <span class="review-item__due" :class="{ 'is-overdue': isOverdue(it) }">
            {{ dueLabel(it) }}
          </span>
        </li>
      </ul>

      <footer class="review-panel__foot">
        <button class="review-primary" type="button" :disabled="!dueTotal" @click="startReview">
          开始复习{{ dueTotal ? '（' + dueTotal + ' 题）' : '' }}
        </button>
        <button class="review-ghost" type="button" @click="closePanel">稍后</button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

interface ReviewItem {
  question_id: number;
  subject_id: number | null;
  point_name?: string | null;
  overdue_days?: number;
  next_due_at?: string | null;
}

const router = useRouter();
const route = useRoute();
// 答题中右上角要留给「答题卡/交卷」，浮标会盖住「下一题」，故答题页整体隐藏
const isAnswering = computed(() => route.path.indexOf('/exercise') === 0);
const open = ref(false);
const loading = ref(false);
const error = ref('');
const items = ref<ReviewItem[]>([]);
const dueTotal = ref(0);
const note = ref('');
const phase = ref('');

const subjectNames: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' };
const subjectLabel = (id: number | null) => (id ? subjectNames[id] || '综合' : '综合');
const headNote = computed(() => {
  if (note.value) return note.value;
  return dueTotal.value > 0 ? `${dueTotal.value} 道题到期，按遗忘曲线排的先后顺序练` : '按遗忘曲线排程，到期自动提醒';
});
const isOverdue = (it: ReviewItem) => (it.overdue_days || 0) > 0;
const dueLabel = (it: ReviewItem) => {
  const d = it.overdue_days || 0;
  if (d >= 2) return `逾期 ${d} 天`;
  if (d === 1) return '昨天到期';
  return '今天';
};

/**
 * 只拉一小段队列用于「预览」：用户点开始复习才进入答题页，
 * 答题页会用 review=1 重新向后端取完整队列，避免这里和答题页两套取题口径。
 */
// 认证是手动加头的（见 src/auth.ts apiFetch），直接 fetch 会 401，
// 面板就只剩「读取失败」——必须走 window.__VTJ_AUTH__.apiFetch。
const authFetch = (url: string, opts?: RequestInit) => {
  const auth = (window as unknown as { __VTJ_AUTH__?: { apiFetch?: typeof fetch } }).__VTJ_AUTH__;
  return auth?.apiFetch ? auth.apiFetch(url, opts) : fetch(url, opts);
};

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    const res = await authFetch('/api/review/due?limit=8');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    items.value = Array.isArray(data.items) ? data.items : [];
    dueTotal.value = Number(data.due_now ?? data.total ?? items.value.length) || 0;
    note.value = data.note || '';
    phase.value = data.phase || '';
  } catch (e) {
    error.value = '复习队列读取失败，稍后再试';
  } finally {
    loading.value = false;
  }
};

const openPanel = () => {
  open.value = true;
  void load();
};
const closePanel = () => {
  open.value = false;
};

const startReview = () => {
  if (!dueTotal.value) return;
  // 用队列里第一题的主科目进入答题页；复习模式不按科目过滤，subject 仅用于文案
  const first = items.value[0];
  const key = first && first.subject_id === 2 ? 'sl' : first && first.subject_id === 3 ? 'ga' : 'xc';
  open.value = false;
  void router.push('/exercise?review=1&subject=' + key + '&count=20');
};

// 面板挂着时 5 分钟刷新一次，避免长时间停留后数字过期（切回标签页也会刷）
const timer = window.setInterval(() => {
  if (document.visibilityState === 'visible') void load();
}, 5 * 60 * 1000);

onMounted(() => {
  void load();
});
onBeforeUnmount(() => {
  window.clearInterval(timer);
});
</script>

<style scoped>
.review-bell {
  position: fixed;
  right: 24px;
  bottom: 88px;
  z-index: 1500;
}
.review-fab {
  position: relative;
  width: 48px;
  height: 48px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 6px 20px rgb(26 43 95 / 14%);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.review-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgb(26 43 95 / 20%);
}
.review-fab:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
.review-fab__badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 999px;
  background: #dc2626;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
}
.review-fab__dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #10b981;
}
.review-panel {
  width: 320px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 16px 40px rgb(26 43 95 / 18%);
}
.review-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.review-panel__title {
  margin: 0;
  font-size: 16px;
  color: #1a1a1a;
}
.review-panel__sub {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}
.review-panel__close {
  border: none;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
}
.review-panel__close:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
  border-radius: 4px;
}
.review-panel__state {
  padding: 16px 0;
  font-size: 13px;
  color: #6b7280;
  text-align: center;
}
.review-panel__state--error {
  color: #b91c1c;
}
.review-list {
  flex: 1;
  margin: 12px 0;
  padding: 0;
  list-style: none;
  overflow-y: auto;
}
.review-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
  font-size: 13px;
}
.review-item__subject {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
}
.review-item__point {
  flex: 1;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.review-item__due {
  flex: 0 0 auto;
  font-size: 11px;
  color: #6b7280;
}
.review-item__due.is-overdue {
  color: #b45309;
}
.review-panel__foot {
  display: flex;
  gap: 8px;
}
.review-primary {
  flex: 1;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
.review-primary:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}
.review-primary:focus-visible,
.review-ghost:focus-visible,
.review-link:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
.review-ghost {
  height: 36px;
  padding: 0 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #4b5563;
  font-size: 13px;
  cursor: pointer;
}
.review-link {
  border: none;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  text-decoration: underline;
}
@media (width <= 700px) {
  .review-bell {
    right: 16px;
    bottom: 72px;
  }
  .review-panel {
    width: calc(100vw - 32px);
    max-height: 62vh;
  }
}
@media (prefers-reduced-motion: reduce) {
  .review-fab {
    transition: none;
  }
}
</style>
