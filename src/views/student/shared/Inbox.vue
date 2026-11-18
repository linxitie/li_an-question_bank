<template>
  <div class="ib-page">
    <!-- 收件箱：复习提醒、系统通知、任务提醒都落在 /api/notifications 这一张表里 -->
    <header class="ib-head">
      <div class="ib-titlebar">
        <button class="ib-back" type="button" aria-label="返回" @click="goBack">‹</button>
        <div>
          <h1>收件箱</h1>
          <p class="ib-sub">复习提醒、任务与系统通知都收在这里；未读会同步到右下角铃铛。</p>
        </div>
        <button
          v-if="unread > 0"
          class="ib-ghost"
          type="button"
          :disabled="busy"
          @click="markAll"
        >全部已读</button>
      </div>

      <div class="ib-tabs" role="tablist">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          role="tab"
          :aria-selected="tab === t.key"
          :class="['ib-tab', { active: tab === t.key }]"
          @click="switchTab(t.key)"
        >
          {{ t.label }}
          <span v-if="t.key === 'unread' && unread > 0" class="ib-tab__badge">{{ unread }}</span>
        </button>
      </div>
    </header>

    <p v-if="error" class="ib-alert" role="alert">
      {{ error }}
      <button type="button" @click="reload">重试</button>
    </p>

    <section v-if="loading && !items.length" class="ib-list" aria-busy="true">
      <article v-for="n in 4" :key="'sk' + n" class="ib-item skeleton">
        <div class="sk-line w40"></div>
        <div class="sk-line w90"></div>
      </article>
    </section>

    <section v-else-if="!items.length" class="ib-empty">
      <p class="ib-empty-title">{{ tab === 'unread' ? '没有未读消息' : '收件箱是空的' }}</p>
      <p class="ib-empty-hint">复习提醒会在每天早、晚各推一次；练几道题并收进错题本后就会开始提醒。</p>
    </section>

    <section v-else class="ib-list">
      <article
        v-for="it in items"
        :key="it.notification_id"
        :class="['ib-item', { unread: !it.is_read }]"
      >
        <div class="ib-item__top">
          <span class="ib-item__icon" aria-hidden="true">{{ iconOf(it.type) }}</span>
          <span class="ib-item__title">{{ it.title || '通知' }}</span>
          <span class="ib-item__time">{{ timeLabel(it.created_at) }}</span>
        </div>
        <p v-if="it.content" class="ib-item__body">{{ it.content }}</p>
        <div class="ib-item__actions">
          <button
            v-if="it.link"
            class="ib-primary"
            type="button"
            @click="openLink(it)"
          >去看看</button>
          <button
            v-if="!it.is_read"
            class="ib-ghost"
            type="button"
            :disabled="busy"
            @click="markRead(it)"
          >标为已读</button>
        </div>
      </article>
    </section>

    <div v-if="items.length && hasMore" class="ib-more">
      <button class="ib-ghost" type="button" :disabled="loading" @click="loadMore">
        {{ loading ? '加载中…' : '加载更多' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

interface Notice {
  notification_id: number;
  type?: string | null;
  title?: string | null;
  content?: string | null;
  link?: string | null;
  is_read?: boolean;
  created_at?: string | null;
}

const router = useRouter();
type TabKey = 'all' | 'unread';
const tabs: { key: TabKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'unread', label: '未读' },
];

const tab = ref<TabKey>('all');
const items = ref<Notice[]>([]);
const unread = ref(0);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const busy = ref(false);
const error = ref('');

const hasMore = computed(() => items.value.length < total.value);

const authFetch = (url: string, opts?: RequestInit) => {
  const auth = (window as any).__VTJ_AUTH__;
  return auth && auth.apiFetch ? auth.apiFetch(url, opts) : fetch(url, opts);
};

function iconOf(type?: string | null) {
  const map: Record<string, string> = {
    review_due: '⏰',
    weekly_review: '📊',
    task: '🎯',
    system: '🔔',
    forum: '💬',
  };
  return (type && map[type]) || '🔔';
}

function timeLabel(iso?: string | null) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return min + ' 分钟前';
  const hour = Math.floor(min / 60);
  if (hour < 24) return hour + ' 小时前';
  const day = Math.floor(hour / 24);
  if (day < 7) return day + ' 天前';
  return iso.slice(0, 10);
}

async function load(reset = false) {
  loading.value = true;
  error.value = '';
  if (reset) {
    page.value = 1;
    items.value = [];
  }
  try {
    const params = new URLSearchParams();
    if (tab.value === 'unread') params.set('unread_only', 'true');
    params.set('page', String(page.value));
    params.set('page_size', String(pageSize));
    const res = await authFetch('/api/notifications?' + params.toString());
    if (!res || !res.ok) throw new Error('HTTP ' + (res ? res.status : 0));
    const data = await res.json();
    const rows: Notice[] = Array.isArray(data.items) ? data.items : [];
    items.value = page.value === 1 ? rows : items.value.concat(rows);
    unread.value = Number(data.unread || 0);
    total.value = Number(data.total || 0);
  } catch (e: any) {
    error.value = '收件箱加载失败，请稍后再试';
  } finally {
    loading.value = false;
  }
}

function reload() {
  void load(true);
}

function switchTab(key: TabKey) {
  if (tab.value === key) return;
  tab.value = key;
  void load(true);
}

function loadMore() {
  if (loading.value || !hasMore.value) return;
  page.value += 1;
  void load(false);
}

async function markRead(it: Notice) {
  if (busy.value || it.is_read) return;
  busy.value = true;
  try {
    const res = await authFetch('/api/notifications/' + it.notification_id + '/read', { method: 'PUT' });
    if (res && res.ok) {
      it.is_read = true;
      unread.value = Math.max(0, unread.value - 1);
    }
  } finally {
    busy.value = false;
  }
}

async function markAll() {
  busy.value = true;
  try {
    const res = await authFetch('/api/notifications/read-all', { method: 'PUT' });
    if (res && res.ok) {
      items.value = items.value.map((x) => ({ ...x, is_read: true }));
      unread.value = 0;
    }
  } finally {
    busy.value = false;
  }
}

function openLink(it: Notice) {
  void markRead(it);
  const link = String(it.link || '');
  if (!link) return;
  // 后端存的是 hash 链接（#/wrong-questions?tab=review），这里只取 path+query
  const stripped = link.replace(/^#/, '');
  if (stripped.startsWith('/')) router.push(stripped);
  else router.push('/' + stripped);
}

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push('/question-bank');
}

onMounted(() => {
  void load(true);
});
</script>

<style scoped>
.ib-page {
  max-width: 820px;
  margin: 0 auto;
  padding: 20px 16px 96px;
}

.ib-head {
  margin-bottom: 14px;
}

.ib-titlebar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.ib-back {
  width: 32px;
  height: 32px;
  border: 1px solid #e2e8f2;
  border-radius: 8px;
  background: #fff;
  color: #25324a;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.ib-head h1 {
  margin: 0;
  font-size: 20px;
  color: #14264a;
}

.ib-sub {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: #6b7a92;
}

.ib-tabs {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.ib-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid #e2e8f2;
  border-radius: 999px;
  background: #fff;
  color: #5b6b85;
  font-size: 13px;
  cursor: pointer;
}

.ib-tab.active {
  border-color: #14264a;
  background: #14264a;
  color: #fff;
}

.ib-tab__badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #dc2626;
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

.ib-alert {
  margin: 0 0 12px;
  padding: 10px 14px;
  border: 1px solid #f3c3c3;
  border-radius: 10px;
  background: #fdecec;
  color: #b91c1c;
  font-size: 13px;
}

.ib-alert button {
  margin-left: 10px;
  border: 1px solid #b91c1c;
  border-radius: 6px;
  background: #fff;
  color: #b91c1c;
  padding: 3px 9px;
  cursor: pointer;
}

.ib-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ib-item {
  padding: 14px 16px;
  border: 1px solid #e2e8f2;
  border-radius: 12px;
  background: #fff;
}

.ib-item.unread {
  border-color: #c7d7f2;
  box-shadow: inset 3px 0 0 #2563eb;
}

.ib-item__top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ib-item__icon {
  font-size: 15px;
}

.ib-item__title {
  flex: 1;
  font-size: 14.5px;
  font-weight: 600;
  color: #14264a;
}

.ib-item__time {
  font-size: 12px;
  color: #8b97a8;
  white-space: nowrap;
}

.ib-item__body {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #4a586e;
  white-space: pre-wrap;
}

.ib-item__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.ib-primary,
.ib-ghost {
  border-radius: 8px;
  font-size: 13px;
  padding: 6px 12px;
  cursor: pointer;
}

.ib-primary {
  border: 1px solid #14264a;
  background: #14264a;
  color: #fff;
}

.ib-ghost {
  border: 1px solid #d5dde9;
  background: #fff;
  color: #25324a;
}

.ib-primary:focus-visible,
.ib-ghost:focus-visible,
.ib-back:focus-visible,
.ib-tab:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

.ib-ghost:disabled,
.ib-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ib-empty {
  padding: 48px 20px;
  border: 1px solid #e2e8f2;
  border-radius: 12px;
  background: #fff;
  text-align: center;
}

.ib-empty-title {
  margin: 0 0 6px;
  font-size: 15px;
  color: #14264a;
}

.ib-empty-hint {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: #7a8699;
}

.ib-more {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

.sk-line {
  height: 12px;
  border-radius: 6px;
  background: #eef2f8;
  margin-bottom: 8px;
}

.sk-line.w40 { width: 40%; }
.sk-line.w90 { width: 90%; }

@media (max-width: 700px) {
  .ib-page {
    padding: 14px 12px 88px;
  }

  .ib-item__time {
    font-size: 11px;
  }

  .ib-item__actions {
    flex-direction: column;
  }

  .ib-primary,
  .ib-ghost {
    width: 100%;
  }
}
</style>
