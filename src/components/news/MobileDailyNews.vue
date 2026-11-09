<template>
  <section class="mobile-news-panel">
    <header class="mobile-news-panel__head">
      <div>
        <span class="eyebrow">每日新闻</span>
        <p>权威时政 · 公安要闻</p>
      </div>
      <router-link to="/mobile/news" class="more-link">更多 →</router-link>
    </header>

    <div v-if="loading" class="state">加载中...</div>
    <div v-else-if="!items.length" class="state">暂无新闻</div>
    <div v-else class="mobile-news-list">
      <article
        v-for="item in items"
        :key="item.id"
        class="mobile-news-item"
        @click="openNews(item)">
        <h3>{{ item.title }}</h3>
        <p v-if="item.ai_summary || item.summary" class="summary">
          {{ item.ai_summary || item.summary }}
        </p>
        <footer>
          <span>{{ item.category || '新闻' }}</span>
          <span>{{ formatDate(item.publish_date) }}</span>
        </footer>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

interface MobileNewsItem {
  id: number;
  title: string;
  summary?: string;
  ai_summary?: string;
  category?: string;
  publish_date?: string;
}

const router = useRouter();
const items = ref<MobileNewsItem[]>([]);
const loading = ref(false);

function formatDate(value?: string): string {
  return value ? value.slice(0, 10) : '';
}

function openNews(item: MobileNewsItem): void {
  router.push(`/mobile/news/${item.id}`);
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    const response = await fetch('/api/news?limit=5');
    if (!response.ok) throw new Error('获取新闻失败');
    const data = await response.json();
    items.value = data.items || [];
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.mobile-news-panel {
  margin: 16px 16px 0;
}

.mobile-news-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
}

.eyebrow {
  color: #1a365d;
  font-size: 17px;
  font-weight: 700;
}

.mobile-news-panel__head p {
  margin: 3px 0 0;
  color: #9aa3ad;
  font-size: 11px;
}

.more-link {
  padding-top: 3px;
  color: #2f5d50;
  font-size: 12px;
  text-decoration: none;
}

.mobile-news-list {
  display: grid;
  gap: 9px;
}

.mobile-news-item {
  padding: 14px 15px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(16, 42, 71, 0.04);
}

.mobile-news-item h3 {
  margin: 0;
  color: #1f2d3d;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
}

.summary {
  display: -webkit-box;
  margin: 7px 0 0;
  overflow: hidden;
  color: #7a8794;
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.mobile-news-item footer {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  color: #9aa3ad;
  font-size: 11px;
}

.mobile-news-item footer span:first-child {
  padding: 2px 7px;
  border-radius: 999px;
  background: #eef3f8;
  color: #53657a;
}

.state {
  padding: 24px 0;
  color: #9aa3ad;
  font-size: 13px;
  text-align: center;
}
</style>
