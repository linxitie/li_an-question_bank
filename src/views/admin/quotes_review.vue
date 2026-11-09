<template>
  <div class="admin-quotes-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">内容运营</p>
        <h1>金句审核</h1>
        <p class="subtitle">审核金句质量、查看来源和标签。</p>
      </div>
      <div class="stats">
        <span>总数 {{ stats.total }}</span>
        <span>待审 {{ stats.pending }}</span>
        <span>来源 {{ stats.sources }}</span>
        <span>标签 {{ stats.tags }}</span>
      </div>
    </header>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key }"
        @click="selectTab(tab.key)">
        {{ tab.label }}
      </button>
    </div>

    <div
      v-if="activeTab === 'sources' || activeTab === 'tags'"
      class="meta-panel">
      <h2>{{ activeTab === 'sources' ? '来源分布' : '标签分布' }}</h2>
      <div class="meta-list">
        <div
          v-for="item in metaItems"
          :key="item.name || item.source"
          class="meta-row">
          <span>{{ item.name || item.source }}</span>
          <strong>{{ item.count }}</strong>
        </div>
      </div>
    </div>

    <template v-else>
      <div class="search-row">
        <input
          v-model="keyword"
          type="search"
          placeholder="搜索内容 / 作者 / 来源"
          @keyup.enter="load" />
        <button type="button" @click="load">搜索</button>
      </div>

      <div v-if="error" class="state error">{{ error }}</div>
      <div v-else-if="loading" class="state">加载中...</div>
      <div v-else-if="!items.length" class="state">暂无金句</div>

      <div v-else class="quote-list">
        <article v-for="item in items" :key="item.quote_id" class="quote-card">
          <div class="quote-card__meta">
            <code>#{{ item.quote_id }}</code>
            <span>{{ item.category }}</span>
            <span>{{ item.author || '无作者' }}</span>
            <span>{{ item.source || '无出处' }}</span>
          </div>
          <blockquote>{{ item.content }}</blockquote>
          <p v-if="item.ai_quality_reason" class="reason">
            {{ item.ai_quality_reason }}
          </p>
          <div class="quote-card__actions">
            <input
              v-model="reasons[item.quote_id]"
              placeholder="审核备注（可选）" />
            <button
              type="button"
              class="approve"
              @click="review(item, 'approve')">
              通过
            </button>
            <button
              type="button"
              class="reject"
              @click="review(item, 'reject')">
              拒绝
            </button>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { apiClient } from '@/services/api/client';

interface QuoteItem {
  quote_id: number;
  content: string;
  source: string;
  author: string;
  category: string;
  ai_quality_reason: string;
}

const tabs = [
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' },
  { key: 'sources', label: '来源' },
  { key: 'tags', label: '标签' }
];
const activeTab = ref('pending');
const keyword = ref('');
const items = ref<QuoteItem[]>([]);
const metaItems = ref<any[]>([]);
const reasons = reactive<Record<number, string>>({});
const stats = reactive({ total: 0, pending: 0, sources: 0, tags: 0 });
const loading = ref(false);
const error = ref('');

async function request<T>(url: string, params?: Record<string, unknown>) {
  const response = await apiClient.request<T>({
    url,
    method: 'GET',
    params,
    baseURL: ''
  });
  return response.data;
}

async function loadStats(): Promise<void> {
  try {
    Object.assign(stats, await request('/api/admin/quotes/stats'));
  } catch {
    // 统计失败不影响列表
  }
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    if (activeTab.value === 'sources') {
      const data = await request<{ items: any[] }>('/api/admin/quotes/sources');
      metaItems.value = data.items || [];
    } else if (activeTab.value === 'tags') {
      const data = await request<{ items: any[] }>('/api/admin/quotes/tags');
      metaItems.value = data.items || [];
    } else {
      const data = await request<{ items: QuoteItem[] }>(
        '/api/admin/quotes/review',
        {
          status: activeTab.value,
          keyword: keyword.value.trim(),
          page: 1,
          page_size: 50
        }
      );
      items.value = data.items || [];
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败';
  } finally {
    loading.value = false;
  }
}

function selectTab(tab: string): void {
  activeTab.value = tab;
  void load();
}

async function review(
  item: QuoteItem,
  action: 'approve' | 'reject'
): Promise<void> {
  try {
    await apiClient.request({
      url: `/api/admin/quotes/${item.quote_id}/review`,
      method: 'POST',
      data: { action, reason: reasons[item.quote_id] || '' },
      baseURL: ''
    });
    items.value = items.value.filter((row) => row.quote_id !== item.quote_id);
    await loadStats();
  } catch (e) {
    error.value = e instanceof Error ? e.message : '审核失败';
  }
}

onMounted(() => {
  void loadStats();
  void load();
});
</script>

<style scoped>
.admin-quotes-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px;
  color: #1f2d3d;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid #ebeef5;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(16, 42, 71, 0.05);
}

.eyebrow {
  margin: 0;
  color: #2f5d50;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

h1 {
  margin: 5px 0;
  color: #163a5f;
  font-size: 28px;
}

.subtitle {
  margin: 0;
  color: #8492a6;
  font-size: 13px;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.stats span {
  padding: 5px 9px;
  border-radius: 999px;
  background: #f0f4f8;
  color: #53657a;
  font-size: 12px;
}

.tabs {
  display: flex;
  gap: 6px;
  margin: 20px 0;
}

.tabs button {
  padding: 8px 14px;
  border: 1px solid #ebeef5;
  border-radius: 999px;
  background: #fff;
  color: #627184;
  font-size: 13px;
  cursor: pointer;
}

.tabs button.active {
  border-color: #2f5d50;
  background: #2f5d50;
  color: #fff;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.search-row input,
.quote-card__actions input {
  flex: 1;
  padding: 9px 11px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  outline: none;
}

.search-row button,
.quote-card__actions button {
  padding: 0 15px;
  border: 0;
  border-radius: 8px;
  background: #2f5d50;
  color: #fff;
  cursor: pointer;
}

.quote-list {
  display: grid;
  gap: 12px;
}

.quote-card {
  padding: 17px 19px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(16, 42, 71, 0.04);
}

.quote-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  color: #8492a6;
  font-size: 12px;
}

.quote-card__meta code {
  color: #2f5d50;
}

.quote-card blockquote {
  margin: 11px 0;
  color: #1f2d3d;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.7;
}

.reason {
  margin: 0 0 10px;
  color: #a33b2d;
  font-size: 12px;
}

.quote-card__actions {
  display: flex;
  gap: 7px;
}

.quote-card__actions .approve {
  background: #2f5d50;
}

.quote-card__actions .reject {
  background: #b85445;
}

.state {
  padding: 40px;
  color: #8492a6;
  text-align: center;
}

.state.error {
  color: #a33b2d;
}

.meta-panel {
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  background: #fff;
}

.meta-panel h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.meta-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 7px;
  background: #f7f9fc;
  font-size: 13px;
}

@media (max-width: 700px) {
  .admin-quotes-page {
    padding: 14px;
  }

  .page-head {
    display: block;
  }

  .stats {
    justify-content: flex-start;
    margin-top: 12px;
  }

  .meta-list {
    grid-template-columns: 1fr;
  }

  .quote-card__actions {
    flex-wrap: wrap;
  }
}
</style>
