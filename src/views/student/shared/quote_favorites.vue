<template>
  <div class="fav-page">
    <header class="fav-head">
      <button
        type="button"
        class="back-btn"
        aria-label="返回金句库"
        @click="goBack">
        ←
      </button>
      <div>
        <h1>金句收藏</h1>
        <p>你在金句库和每日金句保存的内容</p>
      </div>
      <router-link class="news-fav-link" to="/news/favorites">
        新闻收藏 →
      </router-link>
    </header>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="loading" class="state">收藏加载中...</div>
    <div v-else-if="!items.length" class="state">暂无金句收藏</div>

    <div v-else class="fav-list">
      <article
        v-for="item in items"
        :key="item.fav_type + item.fav_id"
        class="fav-card">
        <div class="fav-card__top">
          <QuoteCategoryTag :category="item.category" />
          <button
            type="button"
            class="remove-btn"
            @click="removeFavorite(item)">
            取消收藏
          </button>
        </div>
        <blockquote>{{ item.content }}</blockquote>
        <footer>
          <span>{{ item.author || item.source || '佚名' }}</span>
          <span v-if="item.author && displaySource(item.author, item.source)">
            · {{ displaySource(item.author, item.source) }}
          </span>
        </footer>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { apiClient } from '@/services/api/client';
import QuoteCategoryTag from '@/components/quotes/QuoteCategoryTag.vue';

interface QuoteFavorite {
  fav_type: 'quote';
  fav_id: number;
  quote_id: number;
  content: string;
  source: string;
  category: string;
  author: string;
  obsidian_source?: string;
  create_time: string;
}

const router = useRouter();
const route = useRoute();
const items = ref<QuoteFavorite[]>([]);
const loading = ref(false);
const error = ref('');

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const response = await apiClient.request<{ items: QuoteFavorite[] }>({
      url: '/api/collection/news-favorites',
      method: 'GET',
      params: { type: 'quote', page: 1, page_size: 100 },
      baseURL: ''
    });
    items.value = response.data.items || [];
  } catch (e) {
    error.value = e instanceof Error ? e.message : '收藏加载失败';
  } finally {
    loading.value = false;
  }
}

async function removeFavorite(item: QuoteFavorite): Promise<void> {
  try {
    if (item.quote_id) {
      await apiClient.request({
        url: `/api/quotes/${item.quote_id}/favorite`,
        method: 'POST',
        baseURL: ''
      });
    } else if (item.obsidian_source) {
      await apiClient.request({
        url: `/api/quotes/obsidian/${encodeURIComponent(item.obsidian_source)}/favorite`,
        method: 'POST',
        baseURL: ''
      });
    }
    items.value = items.value.filter((row) => row.fav_id !== item.fav_id);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '取消收藏失败';
  }
}

function goBack(): void {
  router.replace(
    route.path.startsWith('/mobile') ? '/mobile/quotes' : '/quotes'
  );
}

function displaySource(author: string, source: string): string {
  const a = (author || '').trim();
  const s = (source || '').trim();
  if (!a || !s || !s.startsWith(a)) return s;
  return s
    .slice(a.length)
    .replace(/^[\s·•—\-/|:：]+/, '')
    .trim();
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.fav-page {
  box-sizing: border-box;
  max-width: 900px;
  min-height: 100vh;
  margin: 0 auto;
  padding: 24px 18px 60px;
  background: #fbfaf7;
  color: #1f2321;
}

.fav-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 22px;
}

.fav-head h1 {
  margin: 0;
  font-size: 24px;
}

.fav-head p {
  margin: 5px 0 0;
  color: #8a928b;
  font-size: 13px;
}

.back-btn {
  padding: 2px 5px;
  border: 0;
  background: transparent;
  color: #2f5d50;
  font-size: 22px;
  cursor: pointer;
}

.news-fav-link {
  margin-left: auto;
  padding-top: 5px;
  color: #2f5d50;
  font-size: 13px;
  text-decoration: none;
}

.fav-list {
  display: grid;
  gap: 10px;
}

.fav-card {
  padding: 18px 20px;
  border: 1px solid #ece8df;
  border-radius: 13px;
  background: #fff;
  box-shadow: 0 5px 16px rgba(31, 35, 33, 0.04);
}

.fav-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.remove-btn {
  border: 0;
  background: transparent;
  color: #a09a90;
  font-size: 12px;
  cursor: pointer;
}

.fav-card blockquote {
  margin: 13px 0;
  color: #2f3933;
  font-size: 16px;
  line-height: 1.8;
}

.fav-card footer {
  color: #8a928b;
  font-size: 12px;
}

.state {
  padding: 36px 0;
  color: #8a928b;
  text-align: center;
}

.state.error {
  color: #9d4436;
}

.state button {
  margin-top: 8px;
  padding: 6px 13px;
  border: 1px solid #d9d3c8;
  border-radius: 8px;
  background: #fff;
  color: #2f5d50;
  cursor: pointer;
}

@media (max-width: 640px) {
  .fav-page {
    padding: 16px 12px 48px;
  }
}
</style>
