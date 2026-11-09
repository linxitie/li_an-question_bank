<template>
  <div class="news-detail-page">
    <header class="detail-head">
      <button class="back-btn" type="button" aria-label="返回" @click="goBack">
        ←
      </button>
      <h1>新闻详情</h1>
    </header>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="loading" class="state">加载中...</div>

    <article v-else-if="item" class="detail-card">
      <div class="title-row">
        <h2>{{ item.title }}</h2>
        <button
          class="fav-btn"
          :class="{ active: item.is_favorited }"
          type="button"
          :aria-label="item.is_favorited ? '取消收藏' : '收藏'"
          @click="toggleFavorite">
          {{ item.is_favorited ? '★' : '☆' }}
        </button>
      </div>

      <div class="meta">
        <span>{{ sourceLabel(item.source) }}</span>
        <span v-if="item.category">{{ item.category }}</span>
        <span>{{ formatDate(item.publish_date) }}</span>
      </div>

      <p v-if="favoriteError" class="favorite-error">{{ favoriteError }}</p>

      <NewsAICard
        v-if="hasAi"
        :summary="item.ai_summary"
        :exam-points="item.ai_exam_points"
        :entities="item.ai_entities" />

      <div class="content" v-html="renderedContent"></div>

      <div v-if="displayImages.length && !hasInlineMarkers" class="images">
        <img
          v-for="(src, index) in displayImages"
          :key="src + '-' + index"
          :src="src"
          :alt="'新闻图片' + (index + 1)"
          loading="lazy" />
      </div>

      <a
        class="source-link"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer">
        查看原文 ↗
      </a>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  fetchNewsDetail,
  toggleNewsFavorite,
  type NewsItem
} from '@/modules/news/api';
import { dedupeNewsImages, renderNewsContent } from '@/utils/newsRender';
import NewsAICard from '@/components/news/NewsAICard.vue';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const error = ref('');
const favoriteError = ref('');
const item = ref<NewsItem | null>(null);

const displayImages = computed(() =>
  dedupeNewsImages(item.value?.images || [])
);
const hasInlineMarkers = computed(() => {
  const content = item.value?.content || '';
  return /\[\[IMG:\d+\]\]/.test(content);
});
const renderedContent = computed(() =>
  renderNewsContent(item.value?.content || '', item.value?.images || [])
);
const hasAi = computed(() =>
  Boolean(
    item.value?.ai_summary ||
    item.value?.ai_exam_points?.length ||
    item.value?.ai_entities?.length
  )
);

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
    tianjin: '天津市公安局',
    hebei: '河北省公安厅',
    shanghai: '上海市公安局',
    jiangsu: '江苏省公安厅',
    zhejiang: '浙江省公安厅',
    fujian: '福建省公安厅',
    hubei: '湖北省公安厅',
    hunan: '湖南省公安厅',
    cpd: '人民公安报'
  };
  return labels[source] || source || '未知来源';
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : '';
}

function goBack(): void {
  router.replace('/home');
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  favoriteError.value = '';
  try {
    item.value = await fetchNewsDetail(String(route.params.id));
  } catch (e) {
    error.value = e instanceof Error ? e.message : '新闻加载失败';
  } finally {
    loading.value = false;
  }
}

async function toggleFavorite(): Promise<void> {
  if (!item.value) return;
  favoriteError.value = '';
  const current = item.value;
  try {
    const result = await toggleNewsFavorite(current.id);
    current.is_favorited = result.favorited;
  } catch (e) {
    favoriteError.value =
      e instanceof Error ? e.message : '收藏失败，请稍后重试';
  }
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.news-detail-page {
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 18px 64px;
  min-height: 100vh;
  box-sizing: border-box;
  background: #fbfaf7;
  color: #1f2321;
}

.detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.back-btn {
  border: 0;
  background: transparent;
  color: #2f5d50;
  font-size: 22px;
  cursor: pointer;
  padding: 4px 6px;
}

.detail-head h1 {
  margin: 0;
  font-size: 20px;
}

.detail-card {
  padding: 24px;
  border: 1px solid #e6e1d8;
  border-radius: 14px;
  background: #fff;
}

.title-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.title-row h2 {
  flex: 1;
  margin: 0;
  font-size: 25px;
  line-height: 1.4;
}

.fav-btn {
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border: 1px solid #e6e1d8;
  border-radius: 50%;
  background: #fbfaf7;
  color: #8a908b;
  font-size: 18px;
  cursor: pointer;
}

.fav-btn.active {
  color: #c8763f;
  background: #fbf0e7;
  border-color: #e8c3a9;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  color: #8a908b;
  font-size: 13px;
}

.favorite-error {
  margin: 10px 0 0;
  color: #a33b2d;
  font-size: 13px;
}

.ai-panel {
  margin-top: 20px;
  padding: 16px 18px;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
  background: #faf8f3;
}

.ai-panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-panel__label {
  color: #2f5d50;
  font-size: 14px;
  font-weight: 700;
}

.ai-status {
  padding: 2px 7px;
  border-radius: 999px;
  background: #e8f1ec;
  color: #2f5d50;
  font-size: 11px;
}

.ai-block + .ai-block {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #eee9df;
}

.ai-block h3 {
  margin: 0 0 6px;
  color: #49524c;
  font-size: 13px;
  font-weight: 700;
}

.ai-block p,
.ai-block ul {
  margin: 0;
  color: #3f4742;
  font-size: 14px;
  line-height: 1.8;
}

.ai-block ul {
  padding-left: 20px;
}

.entity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entity-tag {
  padding: 3px 8px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e3ddd2;
  color: #535b55;
  font-size: 12px;
}

.entity-tag small {
  margin-right: 4px;
  color: #9aa09c;
  font-size: 10px;
  text-transform: uppercase;
}

.risk-block h3 {
  color: #a33b2d;
}

.risk-block li {
  color: #8e4b3a;
}

.content {
  margin-top: 22px;
  font-size: 16px;
  line-height: 1.9;
  overflow-wrap: anywhere;
}

.content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

.images {
  display: grid;
  gap: 12px;
  margin-top: 20px;
}

.images img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

.source-link {
  display: inline-block;
  margin-top: 24px;
  color: #2f5d50;
  font-size: 14px;
}

.state {
  padding: 48px 12px;
  text-align: center;
  color: #737a75;
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
  .news-detail-page {
    padding: 14px 12px 48px;
  }

  .detail-card {
    padding: 16px;
  }

  .title-row h2 {
    font-size: 20px;
  }
}
</style>
