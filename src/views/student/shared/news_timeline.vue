<template>
  <div class="news-timeline-page">
    <header class="page-head">
      <button class="back-btn" type="button" aria-label="返回" @click="goBack">
        ←
      </button>
      <div>
        <h1>新闻时间线</h1>
        <p class="subtitle">已发布新闻 · 按日聚合 · 日报速览</p>
      </div>
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
            @change="loadDigest" />
          <button type="button" @click="loadDigest">查询</button>
        </div>

        <div v-if="digest" class="digest-summary">
          <strong>{{ digest.date }}</strong>
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
          <h3>{{ item.title }}</h3>
          <p v-if="item.ai_summary" class="summary">{{ item.ai_summary }}</p>
          <div class="meta">
            <span>{{ sourceLabel(item.source) }}</span>
            <span v-if="item.category">{{ item.category }}</span>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchNewsDigest,
  fetchNewsTimeline,
  type NewsDigestResult,
  type NewsTimelineGroup,
  type NewsTimelineItem
} from '@/modules/news/api';

const router = useRouter();
const tab = ref<'timeline' | 'digest'>('timeline');
const loading = ref(false);
const error = ref('');
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
  router.back();
}

function openSource(item: NewsTimelineItem): void {
  if (item.url) {
    window.open(item.url, '_blank', 'noopener,noreferrer');
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

async function loadDigest(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    digest.value = await fetchNewsDigest(day.value, 30);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '日报加载失败';
  } finally {
    loading.value = false;
  }
}

function switchTab(next: 'timeline' | 'digest'): void {
  tab.value = next;
  if (next === 'timeline') {
    void loadTimeline();
  } else {
    void loadDigest();
  }
}

function retry(): void {
  if (tab.value === 'timeline') {
    void loadTimeline();
  } else {
    void loadDigest();
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
  padding: 14px 16px;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
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
  justify-content: space-between;
  color: #505852;
  font-size: 14px;
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
</style>
