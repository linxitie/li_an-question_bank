<template>
  <div class="fav-page">
    <header class="fav-head">
      <button
        type="button"
        class="back-btn"
        aria-label="返回新闻"
        @click="goBack">
        ←
      </button>
      <div>
        <h1>新闻收藏</h1>
        <p>你在新闻模块保存的内容</p>
      </div>
      <router-link class="quote-fav-link" to="/quotes/favorites">
        金句收藏 →
      </router-link>
    </header>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="loading" class="state">收藏加载中...</div>
    <div v-else-if="!items.length" class="state">暂无新闻收藏</div>

    <div v-else class="fav-list">
      <router-link
        v-for="item in items"
        :key="item.fav_id"
        class="fav-card"
        :to="`/news/${item.news_id}`">
        <span class="type-badge">新闻</span>
        <div class="fav-card__body">
          <h2>{{ item.title || item.content }}</h2>
          <p class="meta">
            <span v-if="item.source">{{ item.source }}</span>
            <span v-if="item.category">{{ item.category }}</span>
            <span>{{ formatTime(item.create_time) }}</span>
          </p>
        </div>
        <span class="arrow" aria-hidden="true">›</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { apiClient } from '@/services/api/client';

interface NewsFavorite {
  fav_id: number;
  news_id: number;
  title: string;
  content: string;
  source: string;
  category: string;
  create_time: string;
}

const router = useRouter();
const items = ref<NewsFavorite[]>([]);
const loading = ref(false);
const error = ref('');

function formatTime(value: string): string {
  return value ? value.slice(0, 10) : '';
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const response = await apiClient.request<{ items: NewsFavorite[] }>({
      url: '/api/collection/news-favorites',
      method: 'GET',
      params: { type: 'news', page: 1, page_size: 100 },
      baseURL: ''
    });
    items.value = response.data.items || [];
  } catch (e) {
    error.value = e instanceof Error ? e.message : '收藏加载失败';
  } finally {
    loading.value = false;
  }
}

function goBack(): void {
  router.replace('/news');
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

.quote-fav-link {
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
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 17px 18px;
  border: 1px solid #ece8df;
  border-radius: 13px;
  background: #fff;
  color: inherit;
  text-decoration: none;
  box-shadow: 0 5px 16px rgba(31, 35, 33, 0.04);
}

.type-badge {
  flex: 0 0 auto;
  padding: 3px 7px;
  border-radius: 6px;
  background: #eaf2fb;
  color: #356a9c;
  font-size: 11px;
}

.fav-card__body {
  flex: 1;
  min-width: 0;
}

.fav-card h2 {
  margin: 0;
  font-size: 16px;
  line-height: 1.55;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 8px 0 0;
  color: #8a928b;
  font-size: 12px;
}

.arrow {
  color: #b8b0a2;
  font-size: 20px;
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
