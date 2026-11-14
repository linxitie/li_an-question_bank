<template>
  <div class="quote-browser ds-page">
    <header class="quote-hero">
      <div class="quote-hero__main">
        <button
          type="button"
          class="back-btn"
          aria-label="返回首页"
          @click="goHome">
          ←
        </button>
        <div>
          <span class="ds-eyebrow">每日金句 · 申论素材</span>
          <h1>金句库</h1>
          <p>按主题、作者和关键词，找到能写进申论的那句话。</p>
        </div>
      </div>
      <router-link class="ds-button ds-button--ghost" :to="favoritesPath">
        我的收藏 →
      </router-link>
    </header>

    <section class="search-panel ds-card">
      <label class="search-field">
        <span class="search-icon" aria-hidden="true">⌕</span>
        <input
          v-model="keyword"
          type="search"
          placeholder="搜索金句内容..."
          aria-label="搜索金句内容"
          @keyup.enter="search" />
      </label>
      <label class="search-field search-field--author">
        <span class="search-icon" aria-hidden="true">✎</span>
        <input
          v-model="author"
          type="search"
          placeholder="作者 / 出处"
          aria-label="按作者或出处搜索"
          @keyup.enter="search" />
      </label>
      <button type="button" class="search-btn" @click="search">搜索</button>
      <button
        v-if="keyword || author"
        type="button"
        class="ds-button ds-button--ghost reset-btn"
        @click="resetSearch">
        重置
      </button>
    </section>

    <div class="filter-row">
      <div class="category-tabs" role="tablist" aria-label="金句分类">
        <button
          v-for="category in categories"
          :key="category"
          type="button"
          role="tab"
          :aria-selected="activeCategory === category"
          :class="['category-tab', { active: activeCategory === category }]"
          @click="selectCategory(category)">
          {{ category }}
        </button>
      </div>
      <span class="result-count">共 {{ total }} 条</span>
    </div>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" class="ds-button ds-button--primary" @click="load">
        重试
      </button>
    </div>
    <div v-else-if="loading" class="state">金句加载中...</div>
    <div v-else-if="!items.length" class="state">暂无匹配金句</div>

    <div v-else class="quote-list">
      <article
        v-for="item in items"
        :key="item.quote_id"
        class="quote-card ds-card">
        <div class="quote-card__top">
          <QuoteCategoryTag :category="item.category" />
          <button
            type="button"
            class="fav-btn"
            :class="{ active: item.favorited }"
            :aria-label="item.favorited ? '取消收藏' : '收藏金句'"
            @click="toggleFavorite(item)">
            {{ item.favorited ? '★' : '☆' }}
          </button>
        </div>
        <blockquote>{{ item.content }}</blockquote>
        <footer class="quote-card__foot">
          <span class="author">{{ item.author || item.source || '佚名' }}</span>
          <span
            v-if="item.author && displaySource(item.author, item.source)"
            class="source">
            {{ displaySource(item.author, item.source) }}
          </span>
        </footer>
      </article>
    </div>

    <div v-if="total > items.length" class="load-more">
      <button
        type="button"
        class="ds-button ds-button--ghost"
        :disabled="loadingMore"
        @click="loadMore">
        {{ loadingMore ? '加载中...' : '加载更多' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { apiClient } from '@/services/api/client';
import QuoteCategoryTag from '@/components/quotes/QuoteCategoryTag.vue';

interface QuoteItem {
  quote_id: number;
  content: string;
  source: string;
  category: string;
  author: string;
  favorited: boolean;
}

const categories = [
  '全部',
  '公安专题',
  '政治',
  '法治',
  '民生',
  '文化',
  '生态',
  '经济',
  '古典名言'
];
const router = useRouter();
const route = useRoute();
const favoritesPath = computed(() =>
  route.path.startsWith('/tablet')
    ? '/tablet/quotes/favorites'
    : route.path.startsWith('/mobile')
      ? '/mobile/quotes/favorites'
      : '/quotes/favorites'
);
const activeCategory = ref('全部');
const keyword = ref('');
const author = ref('');
const items = ref<QuoteItem[]>([]);
const total = ref(0);
const page = ref(1);
const loading = ref(false);
const loadingMore = ref(false);
const error = ref('');

const pageSize = 18;

async function requestQuotes(targetPage: number): Promise<void> {
  const params: Record<string, string | number> = {
    page: targetPage,
    page_size: pageSize
  };
  if (activeCategory.value !== '全部') {
    params.category = activeCategory.value;
  }
  if (keyword.value.trim()) {
    params.keyword = keyword.value.trim();
  }
  if (author.value.trim()) {
    params.author = author.value.trim();
  }
  const response = await apiClient.request<{
    total: number;
    items: QuoteItem[];
  }>({ url: '/api/quotes', method: 'GET', params, baseURL: '' });
  total.value = response.data.total;
  if (targetPage === 1) {
    items.value = response.data.items;
  } else {
    items.value = [...items.value, ...response.data.items];
  }
  page.value = targetPage;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    await requestQuotes(1);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '金句加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadMore(): Promise<void> {
  if (loadingMore.value || items.value.length >= total.value) return;
  loadingMore.value = true;
  try {
    await requestQuotes(page.value + 1);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载更多失败';
  } finally {
    loadingMore.value = false;
  }
}

function selectCategory(category: string): void {
  if (activeCategory.value === category) return;
  activeCategory.value = category;
  void load();
}

function search(): void {
  void load();
}

function displaySource(author: string, source: string): string {
  const a = (author || '').trim();
  const s = (source || '').trim();
  if (!a || !s) return s;
  if (!s.startsWith(a)) return s;
  return s
    .slice(a.length)
    .replace(/^[\s·•—\-/|:：]+/, '')
    .trim();
}

function resetSearch(): void {
  keyword.value = '';
  author.value = '';
  void load();
}

async function toggleFavorite(item: QuoteItem): Promise<void> {
  try {
    const response = await apiClient.request<{ favorited: boolean }>({
      url: `/api/quotes/${item.quote_id}/favorite`,
      method: 'POST',
      baseURL: ''
    });
    item.favorited = response.data.favorited;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '收藏失败';
  }
}

function goHome(): void {
  router.replace(route.path.startsWith('/mobile') ? '/mobile/home' : '/home');
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.quote-browser {
  max-width: 1120px;
}

.quote-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.quote-hero__main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.quote-hero h1 {
  margin: 5px 0 4px;
  color: var(--ds-navy-deep);
  font-size: 30px;
  line-height: 1.2;
}

.quote-hero p {
  margin: 0;
  color: var(--ds-muted);
  font-size: 14px;
}

.back-btn {
  margin-top: 4px;
  padding: 3px 5px;
  border: 0;
  background: transparent;
  color: var(--ds-navy);
  font-size: 23px;
  line-height: 1;
  cursor: pointer;
}

.search-panel {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  margin-bottom: 18px;
  box-shadow: var(--ds-shadow);
}

.search-field {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  gap: 8px;
  padding: 0 12px;
  height: 42px;
  border: 1px solid var(--ds-border);
  border-radius: 9px;
  background: #fbfcfe;
  transition: var(--ds-transition);
}

.search-field:focus-within {
  border-color: var(--ds-ink);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(47, 93, 80, 0.08);
}

.search-field--author {
  flex: 0 1 230px;
}

.search-field input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ds-text);
  font-size: 14px;
}

.search-icon {
  color: var(--ds-subtle);
  font-size: 18px;
  line-height: 1;
}

.search-btn {
  flex: 0 0 auto;
  height: 42px;
  padding: 0 22px;
  border: 0;
  border-radius: 9px;
  background: var(--ds-ink);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: var(--ds-transition);
}

.search-btn:hover {
  background: var(--ds-ink-deep);
  box-shadow: 0 5px 14px rgba(47, 93, 80, 0.22);
}

.reset-btn {
  height: 42px;
}

.filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.category-tab {
  padding: 7px 13px;
  border: 1px solid transparent;
  border-radius: 20px;
  background: #e9eef4;
  color: #627184;
  font-size: 13px;
  cursor: pointer;
  transition: var(--ds-transition);
}

.category-tab:hover {
  background: #dfe7ef;
}

.category-tab.active {
  background: var(--ds-ink);
  color: #fff;
  box-shadow: 0 4px 12px rgba(47, 93, 80, 0.18);
}

.result-count {
  flex: 0 0 auto;
  color: var(--ds-subtle);
  font-size: 12px;
}

.quote-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.quote-card {
  display: flex;
  flex-direction: column;
  min-height: 190px;
  padding: 20px 22px;
  border-radius: var(--ds-radius-md, 14px);
}

.quote-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
}

.quote-card blockquote {
  flex: 1;
  margin: 18px 0 20px;
  color: var(--ds-navy-deep);
  font-size: 17px;
  font-weight: 600;
  line-height: 1.85;
}

.quote-card__foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--ds-muted);
  font-size: 12px;
}

.quote-card__foot .source {
  color: var(--ds-subtle);
}

.quote-card__foot .source::before {
  content: '·';
  margin-right: 8px;
}

.fav-btn {
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #b8c1cb;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: var(--ds-transition);
}

.fav-btn:hover {
  background: #fff7df;
  color: #d5a52e;
}

.fav-btn.active {
  color: #d9a72d;
}

.state {
  padding: 70px 16px;
  color: var(--ds-muted);
  text-align: center;
}

.state.error {
  color: #a33b2d;
}

.state .ds-button {
  margin-top: 12px;
}

.load-more {
  padding-top: 24px;
  text-align: center;
}

@media (max-width: 800px) {
  .quote-list {
    grid-template-columns: 1fr;
  }

  .quote-hero h1 {
    font-size: 26px;
  }

  .search-panel {
    flex-wrap: wrap;
  }

  .search-field,
  .search-field--author {
    flex: 1 1 100%;
  }

  .search-btn {
    flex: 1;
  }
}

@media (max-width: 640px) {
  .quote-hero {
    display: block;
  }

  .quote-hero .ds-button {
    margin: 14px 0 0 24px;
  }

  .filter-row {
    display: block;
  }

  .result-count {
    display: block;
    margin-top: 10px;
  }

  .quote-card {
    padding: 17px;
  }
}
</style>
