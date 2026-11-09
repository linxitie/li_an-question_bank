<template>
  <div class="quote-browser">
    <header class="quote-browser__head">
      <button
        type="button"
        class="back-btn"
        aria-label="返回首页"
        @click="goHome">
        ←
      </button>
      <div>
        <h1>金句库</h1>
        <p>按主题浏览 · 收藏你的申论素材</p>
      </div>
      <router-link class="favorites-link" to="/quotes/favorites">
        我的收藏 →
      </router-link>
    </header>

    <div class="search-row">
      <input
        v-model="keyword"
        type="search"
        placeholder="搜索金句内容..."
        aria-label="搜索金句内容"
        @keyup.enter="search" />
      <input
        v-model="author"
        type="search"
        placeholder="作者 / 出处"
        aria-label="按作者或出处搜索"
        @keyup.enter="search" />
      <button type="button" class="search-btn" @click="search">检索</button>
      <button
        v-if="keyword || author"
        type="button"
        class="reset-btn"
        @click="resetSearch">
        重置
      </button>
    </div>

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

    <p class="result-count">共 {{ total }} 条</p>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="loading" class="state">金句加载中...</div>
    <div v-else-if="!items.length" class="state">暂无匹配金句</div>

    <div v-else class="quote-list">
      <article v-for="item in items" :key="item.quote_id" class="quote-card">
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
        <footer>
          <span>{{ item.author || item.source || '佚名' }}</span>
          <span v-if="item.author && item.source"> · {{ item.source }}</span>
        </footer>
      </article>
    </div>

    <div v-if="total > items.length" class="load-more">
      <button type="button" :disabled="loadingMore" @click="loadMore">
        {{ loadingMore ? '加载中...' : '加载更多' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
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
  router.replace('/home');
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.quote-browser {
  box-sizing: border-box;
  max-width: 880px;
  min-height: 100vh;
  margin: 0 auto;
  padding: 24px 18px 60px;
  background: #fbfaf7;
  color: #1f2321;
}

.quote-browser__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 20px;
}

.quote-browser__head h1 {
  margin: 0;
  font-size: 24px;
}

.quote-browser__head p {
  margin: 5px 0 0;
  color: #8a928b;
  font-size: 13px;
}

.favorites-link {
  margin-left: auto;
  padding-top: 5px;
  color: #2f5d50;
  font-size: 13px;
  text-decoration: none;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.search-row input {
  flex: 1;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid #e3ded4;
  border-radius: 9px;
  background: #fff;
  color: #2f3933;
  outline: none;
}

.search-row input:focus {
  border-color: #2f5d50;
}

.search-btn,
.reset-btn {
  flex: 0 0 auto;
  padding: 0 15px;
  border-radius: 9px;
  font-size: 13px;
  cursor: pointer;
}

.search-btn {
  border: 1px solid #2f5d50;
  background: #2f5d50;
  color: #fff;
}

.reset-btn {
  border: 1px solid #e3ded4;
  background: #fff;
  color: #59635c;
}

.result-count {
  margin: 0 0 12px;
  color: #9aa19c;
  font-size: 12px;
}

.back-btn {
  padding: 2px 5px;
  border: 0;
  background: transparent;
  color: #2f5d50;
  font-size: 22px;
  cursor: pointer;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.category-tab {
  padding: 6px 13px;
  border: 1px solid #e3ded4;
  border-radius: 999px;
  background: #fff;
  color: #59635c;
  font-size: 13px;
  cursor: pointer;
}

.category-tab.active {
  border-color: #2f5d50;
  background: #2f5d50;
  color: #fff;
}

.quote-list {
  display: grid;
  gap: 12px;
}

.quote-card {
  padding: 18px 20px;
  border: 1px solid #ece8df;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 5px 16px rgba(31, 35, 33, 0.04);
}

.quote-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.quote-card blockquote {
  margin: 13px 0;
  color: #2f3933;
  font-size: 16px;
  line-height: 1.8;
}

.quote-card footer {
  color: #8a928b;
  font-size: 12px;
}

.fav-btn {
  border: 0;
  background: transparent;
  color: #c9a74a;
  font-size: 20px;
  cursor: pointer;
}

.fav-btn.active {
  color: #d0902e;
}

.state {
  padding: 36px 0;
  color: #8a928b;
  text-align: center;
}

.state.error {
  color: #9d4436;
}

.state button,
.load-more button {
  margin-top: 8px;
  padding: 7px 14px;
  border: 1px solid #d9d3c8;
  border-radius: 8px;
  background: #fff;
  color: #2f5d50;
  cursor: pointer;
}

.load-more {
  padding-top: 18px;
  text-align: center;
}

@media (max-width: 640px) {
  .quote-browser {
    padding: 16px 12px 48px;
  }

  .quote-card {
    padding: 15px;
  }
}
</style>
