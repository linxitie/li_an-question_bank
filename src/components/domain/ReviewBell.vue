<template>
  <!-- 复习提醒 + 收件箱：由顶部导航铃铛触发（全局唯一弹窗，不再有右下角浮标） -->
  <div v-if="open" class="review-mask" @click.self="closePanel">
    <section class="review-modal" role="dialog" aria-modal="true" aria-label="通知与复习提醒">
      <header class="review-head">
        <div>
          <h3 class="review-title">通知中心</h3>
          <p class="review-sub">{{ headNote }}</p>
        </div>
        <button class="review-close" type="button" aria-label="关闭" @click="closePanel">×</button>
      </header>

      <div class="review-tabs">
        <button :class="['review-tab', { active: tab === 'review' }]" @click="tab = 'review'">
          复习提醒<span v-if="dueTotal" class="tab-dot">{{ dueTotal }}</span>
        </button>
        <button :class="['review-tab', { active: tab === 'inbox' }]" @click="switchInbox">
          收件箱<span v-if="unread" class="tab-dot">{{ unread > 99 ? '99+' : unread }}</span>
        </button>
      </div>

      <div v-if="tab === 'review'" class="review-body">
        <div v-if="loading" class="review-state">正在读取复习队列…</div>
        <div v-else-if="error" class="review-state review-state--error">
          {{ error }}
          <button class="review-link" type="button" @click="load">重试</button>
        </div>
        <div v-else-if="!items.length" class="review-state">
          今天没有到期复习，去练几道新题，明天这里会提醒你。
        </div>
        <ul v-else class="review-list">
          <li v-for="it in items" :key="it.question_id" class="review-item">
            <span class="review-item__subject">{{ subjectLabel(it.subject_id) }}</span>
            <span class="review-item__point">{{ it.point_name || '未细分考点' }}</span>
            <span class="review-item__due" :class="{ 'is-overdue': isOverdue(it) }">{{ dueLabel(it) }}</span>
          </li>
        </ul>
        <footer class="review-foot">
          <button class="review-primary" type="button" :disabled="!dueTotal" @click="startReview">
            开始复习{{ dueTotal ? '（' + dueTotal + ' 题）' : '' }}
          </button>
          <button class="review-ghost" type="button" @click="switchInbox">收件箱</button>
          <button class="review-ghost" type="button" @click="closePanel">稍后</button>
        </footer>
      </div>

      <div v-else class="review-body review-inbox">
        <div v-if="inboxLoading" class="review-state">正在读取收件箱…</div>
        <div v-else-if="!inbox.length" class="review-state">收件箱为空</div>
        <ul v-else class="inbox-list">
          <li
            v-for="n in inbox"
            :key="n.notification_id"
            :class="['inbox-item', { unread: !n.is_read }]"
            @click="openNotification(n)"
          >
            <span class="inbox-icon">{{ inboxIcon(n.type) }}</span>
            <span class="inbox-main">
              <strong class="inbox-title">{{ n.title }}</strong>
              <span class="inbox-content">{{ n.content }}</span>
              <span class="inbox-time">{{ fmtTime(n.created_at) }}</span>
            </span>
            <span v-if="!n.is_read" class="inbox-dot"></span>
          </li>
        </ul>
        <footer class="review-foot">
          <button class="review-ghost" type="button" @click="goInboxPage">查看全部</button>
          <button class="review-ghost" type="button" @click="markAllRead">全部已读</button>
        </footer>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

interface ReviewItem {
  question_id: number;
  subject_id: number | null;
  point_name?: string | null;
  overdue_days?: number;
  next_due_at?: string | null;
}

interface InboxItem {
  notification_id: number;
  type: string;
  title: string;
  content?: string | null;
  link?: string | null;
  is_read: boolean;
  created_at?: string | null;
}

const router = useRouter();
const open = ref(false);
const tab = ref<'review' | 'inbox'>('review');
const loading = ref(false);
const error = ref('');
const items = ref<ReviewItem[]>([]);
const dueTotal = ref(0);
const unread = ref(0);
const note = ref('');
const inbox = ref<InboxItem[]>([]);
const inboxLoading = ref(false);

const badgeCount = computed(() => (unread.value > 0 ? unread.value : dueTotal.value));

function pushBadge() {
  window.dispatchEvent(new CustomEvent('la-bell-badge', { detail: badgeCount.value }));
}

const subjectNames: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' };
const subjectLabel = (id: number | null) => (id ? subjectNames[id] || '综合' : '综合');
const headNote = computed(() => {
  if (tab.value === 'inbox') return unread.value ? '有 ' + unread.value + ' 条未读消息' : '复习提醒与系统通知都在这里';
  if (note.value) return note.value;
  return dueTotal.value > 0 ? dueTotal.value + ' 道题到期，按遗忘曲线排的先后顺序练' : '按遗忘曲线排程，到期自动提醒';
});
const isOverdue = (it: ReviewItem) => (it.overdue_days || 0) > 0;
const dueLabel = (it: ReviewItem) => {
  const d = it.overdue_days || 0;
  if (d >= 2) return '逾期 ' + d + ' 天';
  if (d === 1) return '昨天到期';
  return '今天';
};

const authFetch = (url: string, opts?: RequestInit) => {
  const auth = (window as unknown as { __VTJ_AUTH__?: { apiFetch?: typeof fetch } }).__VTJ_AUTH__;
  return auth?.apiFetch ? auth.apiFetch(url, opts) : fetch(url, opts);
};

const loadUnread = async () => {
  try {
    const res = await authFetch('/api/notifications?unread_only=true&page=1&page_size=1');
    if (!res || !res.ok) return;
    const data = await res.json();
    unread.value = Number(data.unread || 0);
    pushBadge();
  } catch {
    /* 收件箱接口抖动不影响复习面板 */
  }
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
    await loadUnread();
  } catch {
    error.value = '复习队列读取失败，稍后再试';
  } finally {
    loading.value = false;
  }
};

const loadInbox = async () => {
  inboxLoading.value = true;
  try {
    const res = await authFetch('/api/notifications?page=1&page_size=20');
    if (!res.ok) return;
    const data = await res.json();
    inbox.value = Array.isArray(data.items) ? data.items : [];
    unread.value = Number(data.unread || 0);
    pushBadge();
  } finally {
    inboxLoading.value = false;
  }
};

const switchInbox = () => {
  tab.value = 'inbox';
  void loadInbox();
};

const openNotification = async (n: InboxItem) => {
  if (!n.is_read) {
    try {
      await authFetch('/api/notifications/' + n.notification_id + '/read', { method: 'PUT' });
      n.is_read = true;
      unread.value = Math.max(0, unread.value - 1);
      pushBadge();
    } catch {
      /* 已读失败不阻断跳转 */
    }
  }
  if (n.link) {
    open.value = false;
    void router.push(n.link);
  }
};

const markAllRead = async () => {
  try {
    await authFetch('/api/notifications/read-all', { method: 'PUT' });
    inbox.value = inbox.value.map((n) => ({ ...n, is_read: true }));
    unread.value = 0;
    pushBadge();
  } catch {
    /* 忽略 */
  }
};

const goInboxPage = () => {
  open.value = false;
  void router.push('/inbox');
};

const inboxIcon = (type: string) => {
  if (type === 'feedback_reply') return '💬';
  if (type === 'review') return '📚';
  if (type === 'task') return '🎯';
  return '🔔';
};

const fmtTime = (v?: string | null) => {
  if (!v) return '';
  return String(v).replace('T', ' ').slice(0, 16);
};

const openPanel = () => {
  open.value = true;
  tab.value = 'review';
  void load();
  void loadInbox();
};
const closePanel = () => {
  open.value = false;
};

const startReview = () => {
  if (!dueTotal.value) return;
  const first = items.value[0];
  const key = first && first.subject_id === 2 ? 'sl' : first && first.subject_id === 3 ? 'ga' : 'xc';
  open.value = false;
  void router.push('/exercise?review=1&subject=' + key + '&count=20');
};

const onOpenEvent = () => openPanel();

const timer = window.setInterval(() => {
  if (document.visibilityState === 'visible') void loadUnread();
}, 5 * 60 * 1000);

const onVisible = () => {
  if (document.visibilityState === 'visible') void loadUnread();
};

onMounted(() => {
  void loadUnread();
  window.addEventListener('la-open-bell', onOpenEvent);
  document.addEventListener('visibilitychange', onVisible);
});

onBeforeUnmount(() => {
  window.clearInterval(timer);
  window.removeEventListener('la-open-bell', onOpenEvent);
  document.removeEventListener('visibilitychange', onVisible);
});
</script>

<style scoped>
.review-mask {
  position: fixed;
  inset: 0;
  z-index: 2400;
  background: rgb(12 26 44 / 45%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.review-modal {
  width: min(720px, 52vw);
  height: min(560px, 62vh);
  min-height: 360px;
  display: flex;
  flex-direction: column;
  padding: 18px 20px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 24px 60px rgb(12 26 44 / 28%);
}
.review-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.review-title { margin: 0; font-size: 18px; color: #1a1a1a; }
.review-sub { margin: 4px 0 0; font-size: 12px; line-height: 1.6; color: #6b7280; }
.review-close { border: none; background: transparent; font-size: 22px; line-height: 1; color: #9ca3af; cursor: pointer; }
.review-tabs { display: flex; gap: 6px; margin: 12px 0 8px; border-bottom: 1px solid #eef1f6; }
.review-tab {
  border: none; background: transparent; padding: 8px 10px; font-size: 13px; color: #5a6488;
  cursor: pointer; border-bottom: 2px solid transparent; display: inline-flex; align-items: center; gap: 6px;
}
.review-tab.active { color: #1a2b5f; border-bottom-color: #2563eb; font-weight: 700; }
.tab-dot { min-width: 16px; height: 16px; padding: 0 4px; border-radius: 999px; background: #dc2626; color: #fff; font-size: 10px; line-height: 16px; text-align: center; }
.review-body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.review-state { padding: 24px 0; font-size: 13px; color: #6b7280; text-align: center; }
.review-state--error { color: #b91c1c; }
.review-list { flex: 1; margin: 8px 0; padding: 0; list-style: none; overflow-y: auto; }
.review-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 13px; }
.review-item__subject { flex: 0 0 auto; padding: 1px 6px; border-radius: 4px; background: #eff6ff; color: #2563eb; font-size: 11px; }
.review-item__point { flex: 1; color: #1a1a1a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.review-item__due { flex: 0 0 auto; font-size: 11px; color: #6b7280; }
.review-item__due.is-overdue { color: #b45309; }
.review-foot { display: flex; gap: 8px; padding-top: 10px; border-top: 1px solid #eef1f6; }
.review-primary { flex: 1; height: 36px; border: none; border-radius: 8px; background: #2563eb; color: #fff; font-size: 13px; cursor: pointer; }
.review-primary:disabled { background: #e5e7eb; color: #9ca3af; cursor: not-allowed; }
.review-ghost { height: 36px; padding: 0 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; color: #4b5563; font-size: 13px; cursor: pointer; }
.review-link { border: none; background: transparent; color: #2563eb; cursor: pointer; text-decoration: underline; }
.review-inbox { overflow: hidden; }
.inbox-list { flex: 1; margin: 0; padding: 0; list-style: none; overflow-y: auto; }
.inbox-item { display: flex; gap: 10px; padding: 10px 6px; border-bottom: 1px solid #f3f4f6; cursor: pointer; align-items: flex-start; }
.inbox-item:hover { background: #f7f9fd; }
.inbox-item.unread { background: #f8fbff; }
.inbox-icon { font-size: 16px; line-height: 1.4; }
.inbox-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.inbox-title { font-size: 13px; color: #1a2b5f; font-weight: 600; }
.inbox-content { font-size: 12px; color: #5a6488; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.inbox-time { font-size: 11px; color: #9aa2b5; }
.inbox-dot { width: 7px; height: 7px; border-radius: 999px; background: #dc2626; margin-top: 6px; }
@media (width <= 900px) {
  .review-mask { padding: 12px; }
  .review-modal { width: 94vw; height: 78vh; min-height: 320px; padding: 14px; }
}
</style>
