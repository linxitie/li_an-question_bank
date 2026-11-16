<template>
  <div class="news-timeline-page ds-page">
    <header class="page-head">
      <button class="back-btn" type="button" aria-label="返回" @click="goBack">
        ←
      </button>
      <div>
        <h1>新闻时间线</h1>
        <p class="subtitle">已发布新闻 · 按日聚合 · 日报速览</p>
      </div>
      <router-link class="news-favorites-link" :to="favoritesPath">
        我的收藏 →
      </router-link>
    </header>

    <div class="tabs" role="tablist" aria-label="新闻视图">
      <button
        type="button"
        role="tab"
        :aria-selected="tab === 'timeline'"
        :class="{ active: tab === 'timeline' }"
        @click="switchTab('timeline')">
        时间线
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="tab === 'digest'"
        :class="{ active: tab === 'digest' }"
        @click="switchTab('digest')">
        日报
      </button>
    </div>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="retry">重试</button>
    </div>

    <div v-else-if="loading" class="state">加载中...</div>

    <p v-if="favoriteError" class="favorite-error">{{ favoriteError }}</p>

    <template v-else>
      <section v-if="tab === 'timeline'" class="panel">
        <div v-if="!groups.length" class="state">暂无已发布新闻</div>
        <section v-for="group in groups" :key="group.date" class="day-group">
          <h2 class="day-title">{{ group.date }}</h2>
          <article
            v-for="item in group.items"
            :key="item.news_id"
            class="news-card"
            tabindex="0"
            @click="openSource(item)"
            @keydown.enter="openSource(item)">
            <button
              class="fav-btn"
              :class="{ active: item.is_favorited }"
              type="button"
              :aria-label="item.is_favorited ? '取消收藏' : '收藏'"
              @click.stop="toggleFavorite(item)">
              {{ item.is_favorited ? '★' : '☆' }}
            </button>
            <h3>{{ item.title }}</h3>
            <p v-if="item.ai_summary" class="summary">{{ item.ai_summary }}</p>
            <div class="meta">
              <span>{{ sourceLabel(item.source) }}</span>
              <span v-if="item.category">{{ item.category }}</span>
            </div>
          </article>
        </section>
      </section>

      <section v-else class="panel">
        <div class="digest-tools">
          <label for="digest-day">日期</label>
          <input
            id="digest-day"
            v-model="day"
            type="date"
            @change="loadDigest(1)" />
          <button type="button" @click="loadDigest(1)">查询</button>
        </div>

        <div v-if="digest" class="digest-summary">
          <div class="day-nav">
            <button type="button" @click="shiftDay(-1)">前一天</button>
            <strong>{{ digest.date }}</strong>
            <button type="button" @click="shiftDay(1)">后一天</button>
          </div>
          <span>共 {{ digest.total }} 条</span>
        </div>

        <div v-if="digest?.categories?.length" class="category-list">
          <span
            v-for="c in digest.categories"
            :key="c.category_code || c.category"
            class="category-tag">
            {{ c.category }} {{ c.count }}
          </span>
        </div>

        <div v-if="!digest?.items?.length" class="state">
          当天暂无已发布新闻
        </div>
        <article
          v-for="item in digest?.items || []"
          :key="item.news_id"
          class="news-card"
          tabindex="0"
          @click="openSource(item)"
          @keydown.enter="openSource(item)">
          <button
            class="fav-btn"
            :class="{ active: item.is_favorited }"
            type="button"
            :aria-label="item.is_favorited ? '取消收藏' : '收藏'"
            @click.stop="toggleFavorite(item)">
            {{ item.is_favorited ? '★' : '☆' }}
          </button>
          <h3>{{ item.title }}</h3>
          <p v-if="item.ai_summary" class="summary">{{ item.ai_summary }}</p>
          <div class="meta">
            <span>{{ sourceLabel(item.source) }}</span>
            <span v-if="item.category">{{ item.category }}</span>
          </div>
        </article>

        <div v-if="digest && digest.total > digest.page_size" class="page-nav">
          <button
            type="button"
            :disabled="digest.page <= 1"
            @click="loadDigest(digest.page - 1)">
            上一页
          </button>
          <span>
            第 {{ digest.page }} /
            {{ Math.ceil(digest.total / digest.page_size) }} 页
          </span>
          <button
            type="button"
            :disabled="!digest.has_more"
            @click="loadDigest(digest.page + 1)">
            下一页
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  fetchNewsDigest,
  fetchNewsTimeline,
  toggleNewsFavorite,
  type NewsDigestResult,
  type NewsTimelineGroup,
  type NewsTimelineItem
} from '@/modules/news/api';

const route = useRoute();
const router = useRouter();
const favoritesPath = computed(() =>
  route.path.startsWith('/tablet')
    ? '/tablet/news/favorites'
    : route.path.startsWith('/mobile')
      ? '/mobile/favorites'
      : '/news/favorites'
);
const tab = ref<'timeline' | 'digest'>('timeline');
const loading = ref(false);
const error = ref('');
const favoriteError = ref('');
const groups = ref<NewsTimelineGroup[]>([]);
const digest = ref<NewsDigestResult | null>(null);
const day = ref('');

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    xinhua: '新华网',
    people: '人民网',
    mps: '公安部',
    beijing: '北京市公安局',
    guangdong: '广东省公安厅',
    shandong: '山东省公安厅',
    henan: '河南省公安厅',
    sichuan: '四川省公安厅',
    cpd: '人民公安报'
  };
  return labels[source] || source || '未知来源';
}

function goBack(): void {
  const home = route.path.startsWith('/tablet')
    ? '/tablet/home'
    : route.path.startsWith('/mobile')
      ? '/mobile/home'
      : '/home';
  router.replace(home);
}

function openSource(item: NewsTimelineItem): void {
  if (route.path.startsWith('/tablet')) {
    router.push(`/tablet/news/${item.news_id}`);
    return;
  }
  if (route.path.startsWith('/mobile')) {
    router.push(`/mobile/news/${item.news_id}`);
    return;
  }
  if (route.path === '/news') {
    router.push(`/news/${item.news_id}`);
    return;
  }
  if (item.url) {
    window.open(item.url, '_blank', 'noopener,noreferrer');
  }
}

async function toggleFavorite(item: NewsTimelineItem): Promise<void> {
  favoriteError.value = '';
  try {
    const result = await toggleNewsFavorite(item.news_id);
    item.is_favorited = result.favorited;
  } catch (e) {
    favoriteError.value =
      e instanceof Error ? e.message : '收藏失败，请稍后重试';
  }
}

async function loadTimeline(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const result = await fetchNewsTimeline(80);
    groups.value = result.items || [];
  } catch (e) {
    error.value = e instanceof Error ? e.message : '时间线加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadDigest(page = 1): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    digest.value = await fetchNewsDigest(day.value, page, 20);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '日报加载失败';
  } finally {
    loading.value = false;
  }
}

function shiftDay(delta: number): void {
  const base = digest.value?.date || day.value;
  if (!base) return;
  const date = new Date(`${base}T00:00:00`);
  date.setDate(date.getDate() + delta);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const dayOfMonth = String(date.getDate()).padStart(2, '0');
  day.value = `${year}-${month}-${dayOfMonth}`;
  void loadDigest(1);
}

function switchTab(next: 'timeline' | 'digest'): void {
  tab.value = next;
  if (next === 'timeline') {
    void loadTimeline();
  } else {
    void loadDigest(1);
  }
}

function retry(): void {
  if (tab.value === 'timeline') {
    void loadTimeline();
  } else {
    void loadDigest(digest.value?.page || 1);
  }
}

onMounted(() => {
  void loadTimeline();
});
</script>

<style scoped>
.news-timeline-page {
  max-width: 920px;
  margin: 0 auto;
  padding: 24px 18px 64px;
  color: #1f2321;
  background: #fbfaf7;
  min-height: 100vh;
  box-sizing: border-box;
}

.page-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
}

.news-favorites-link {
  margin-left: auto;
  padding-top: 5px;
  color: #2f5d50;
  font-size: 13px;
  text-decoration: none;
  white-space: nowrap;
}

.back-btn {
  border: 0;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  padding: 4px 6px;
  color: #2f5d50;
}

.page-head h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.25;
}

.subtitle {
  margin: 5px 0 0;
  color: #6b726e;
  font-size: 13px;
}

.tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background: #ece9e1;
  margin-bottom: 20px;
}

.tabs button {
  border: 0;
  background: transparent;
  padding: 8px 18px;
  border-radius: 9px;
  cursor: pointer;
  color: #505852;
  font-size: 14px;
}

.tabs button.active {
  background: #fff;
  color: #2f5d50;
  box-shadow: 0 1px 4px rgba(31, 35, 33, 0.12);
  font-weight: 600;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.day-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.day-title {
  margin: 10px 0 0;
  font-size: 15px;
  color: #2f5d50;
  border-left: 3px solid #c8763f;
  padding-left: 9px;
}

.news-card {
  display: block;
  position: relative;
  padding: 14px 52px 14px 16px;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.fav-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: #f5f2eb;
  color: #8a908b;
  font-size: 17px;
  line-height: 1;
  cursor: pointer;
}

.fav-btn.active {
  color: #c8763f;
  background: #fbf0e7;
}

.favorite-error {
  margin: 0 0 10px;
  color: #a33b2d;
  font-size: 13px;
}

.news-card:hover,
.news-card:focus-visible {
  border-color: #c8763f;
  box-shadow: 0 3px 12px rgba(31, 35, 33, 0.08);
}

.news-card h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.45;
}

.summary {
  margin: 7px 0 0;
  color: #626a64;
  font-size: 13px;
  line-height: 1.7;
}

.meta {
  display: flex;
  gap: 12px;
  margin-top: 9px;
  color: #8a908b;
  font-size: 12px;
}

.digest-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px;
  background: #fff;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
}

.digest-tools label {
  color: #626a64;
  font-size: 13px;
}

.digest-tools input,
.digest-tools button {
  border: 1px solid #d9d3c8;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 13px;
  background: #fff;
}

.digest-tools button {
  cursor: pointer;
  color: #2f5d50;
}

.digest-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #505852;
  font-size: 14px;
}

.day-nav,
.page-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.day-nav button,
.page-nav button {
  border: 1px solid #d9d3c8;
  border-radius: 7px;
  background: #fff;
  color: #2f5d50;
  padding: 5px 9px;
  font-size: 12px;
  cursor: pointer;
}

.page-nav {
  justify-content: center;
  padding-top: 8px;
}

.page-nav button:disabled {
  color: #b8bdb9;
  cursor: not-allowed;
}

.category-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.category-tag {
  padding: 4px 9px;
  border-radius: 999px;
  background: #eef3f0;
  color: #2f5d50;
  font-size: 12px;
}

.state {
  padding: 34px 12px;
  text-align: center;
  color: #737a75;
  font-size: 14px;
}

.state.error {
  color: #a33b2d;
}

.state.error button {
  margin-top: 10px;
  border: 1px solid #c8763f;
  background: #fff;
  color: #a0522d;
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
}

@media (max-width: 640px) {
  .news-timeline-page {
    padding: 16px 12px 48px;
  }

  .page-head h1 {
    font-size: 20px;
  }

  .news-card {
    padding: 12px;
  }

  .news-card h3 {
    font-size: 15px;
  }
}

/* ── 内容页统一视觉规范 ───────────────────────────── */
.news-timeline-page {
  max-width: 1000px;
  padding: 36px 28px 64px;
  background: var(--ds-bg);
  color: var(--ds-text);
}

.page-head {
  align-items: center;
  padding: 22px 24px;
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-lg);
  background: var(--ds-surface);
  box-shadow: var(--ds-shadow);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border-radius: 50%;
  background: #f0f4f8;
  color: var(--ds-navy);
  font-size: 19px;
}

.page-head h1 {
  color: var(--ds-navy-deep);
  font-size: 28px;
  font-weight: 700;
}

.subtitle {
  color: var(--ds-muted);
  font-size: 13px;
}

.news-favorites-link {
  padding: 8px 13px;
  border: 1px solid var(--ds-border);
  border-radius: 9px;
  background: var(--ds-surface);
  color: var(--ds-ink);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: var(--ds-transition);
}

.news-favorites-link:hover {
  border-color: var(--ds-ink);
  box-shadow: 0 4px 12px rgba(47, 93, 80, 0.12);
}

.tabs {
  padding: 4px;
  border-radius: 999px;
  background: #e9eef4;
  margin: 20px 0 26px;
}

.tabs button {
  padding: 8px 22px;
  border-radius: 999px;
  color: #627184;
  font-size: 13px;
  font-weight: 600;
  transition: var(--ds-transition);
}

.tabs button.active {
  background: var(--ds-ink);
  color: #fff;
  box-shadow: 0 4px 12px rgba(47, 93, 80, 0.2);
}

.panel {
  gap: 26px;
}

.day-group {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 122px;
  padding-bottom: 8px;
}

.day-group::before {
  content: '';
  position: absolute;
  top: 8px;
  bottom: 0;
  left: 92px;
  width: 1px;
  background: #dfe7ef;
}

.day-title {
  position: absolute;
  top: 2px;
  left: 0;
  width: 78px;
  margin: 0;
  padding: 0;
  border-left: 0;
  color: var(--ds-navy);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.news-card {
  padding: 20px 52px 20px 22px;
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius);
  background: var(--ds-surface);
  box-shadow: var(--ds-shadow);
  transition: var(--ds-transition);
}

.news-card:hover,
.news-card:focus-visible {
  border-color: #d6e0e8;
  box-shadow: var(--ds-shadow-hover);
  transform: translateY(-1px);
}

.news-card h3 {
  color: var(--ds-navy-deep);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.5;
}

.summary {
  margin: 9px 0 0;
  color: #6b7a90;
  font-size: 14px;
  line-height: 1.65;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 13px;
  color: var(--ds-muted);
  font-size: 12px;
}

.meta span {
  padding: 4px 9px;
  border-radius: 999px;
  background: #f0f4f8;
  color: #53657a;
}

.fav-btn {
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  background: #f4f7fa;
  color: #aab5c1;
  font-size: 18px;
  transition: var(--ds-transition);
}

.fav-btn:hover {
  background: #fff7df;
  color: #d5a52e;
}

.fav-btn.active {
  background: #fff7df;
  color: #d9a72d;
}

.digest-tools {
  padding: 14px 16px;
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius);
  background: var(--ds-surface);
  box-shadow: var(--ds-shadow);
}

.digest-tools input {
  border-color: var(--ds-border);
  border-radius: 8px;
}

.digest-tools button,
.day-nav button,
.page-nav button {
  border: 1px solid var(--ds-border);
  border-radius: 8px;
  background: #fff;
  color: var(--ds-ink);
  transition: var(--ds-transition);
}

.digest-tools button:hover,
.day-nav button:hover,
.page-nav button:hover {
  border-color: var(--ds-ink);
}

.digest-summary {
  color: #53657a;
}

.category-tag {
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--ds-ink-soft);
  color: var(--ds-ink);
  font-size: 12px;
}

.page-nav {
  padding-top: 12px;
}

.state {
  padding: 64px 16px;
  color: var(--ds-muted);
}

@media (max-width: 720px) {
  .news-timeline-page {
    padding: 22px 14px 48px;
  }

  .page-head {
    padding: 16px;
  }

  .page-head h1 {
    font-size: 22px;
  }

  .news-favorites-link {
    display: none;
  }

  .day-group {
    padding-left: 0;
    padding-bottom: 14px;
  }

  .day-group::before {
    display: none;
  }

  .day-title {
    position: static;
    width: auto;
    margin: 4px 0 2px;
    font-size: 16px;
  }

  .news-card {
    padding: 16px 44px 16px 16px;
  }

  .news-card h3 {
    font-size: 16px;
  }

  .summary {
    font-size: 13px;
  }
}
</style>
