<template>
  <section class="daily-news-panel">
    <div class="daily-news-panel__header">
      <div class="title-block">
        <h3>每日新闻</h3>
        <p>权威时政 · 公安要闻 · 法治动态</p>
      </div>
      <button class="more-btn" type="button" @click="goMore">
        更多 <span aria-hidden="true">›</span>
      </button>
    </div>

    <div class="search-row">
      <input
        v-model="keyword"
        type="search"
        placeholder="搜索标题、关键词..."
        aria-label="搜索新闻"
        @keyup.enter="loadNews" />
      <button type="button" class="search-btn" @click="loadNews">搜索</button>
    </div>

    <div class="tabs" role="tablist" aria-label="新闻分类">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.key"
        :class="['tab', { active: activeTab === tab.key }]"
        @click="selectTab(tab.key)">
        {{ tab.label }}
      </button>
    </div>

    <div class="summary-row">
      <span>{{ loading ? '加载中...' : `共 ${total} 条` }}</span>
      <button
        v-if="keyword"
        type="button"
        class="clear-btn"
        @click="clearSearch">
        清除搜索
      </button>
    </div>

    <div v-if="error" class="state error">
      <span>{{ error }}</span>
      <button type="button" @click="loadNews">重试</button>
    </div>
    <div v-else-if="loading" class="state">新闻加载中...</div>
    <div v-else-if="!items.length" class="state">暂无匹配新闻</div>

    <div v-else class="news-list">
      <article
        v-for="item in items"
        :key="item.id"
        class="news-row"
        tabindex="0"
        @click="openNews(item)"
        @keydown.enter="openNews(item)">
        <div class="news-row__main">
          <h4>{{ item.title }}</h4>
          <div class="news-row__meta">
            <span v-if="item.category">{{ item.category }}</span>
            <span v-if="item.publish_date">{{
              formatDate(item.publish_date)
            }}</span>
          </div>
        </div>
        <div class="news-row__side">
          <span class="source-badge">{{ sourceLabel(item.source) }}</span>
          <span class="row-arrow" aria-hidden="true">›</span>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { fetchNewsList, type NewsItem } from '@/modules/news/api';

interface CategoryTab {
  key: string;
  label: string;
  category: string;
  keyword: string;
}

const tabs: CategoryTab[] = [
  { key: 'all', label: '全部', category: '', keyword: '' },
  { key: 'policy', label: '政策', category: 'policy_news', keyword: '' },
  { key: 'police', label: '公安新闻', category: 'police_news', keyword: '' },
  { key: 'grassroots', label: '基层新闻', category: '', keyword: '基层' },
  { key: 'meetings', label: '重大会议', category: '', keyword: '会议' }
];

const router = useRouter();
const activeTab = ref('all');
const keyword = ref('');
const items = ref<NewsItem[]>([]);
const total = ref(0);
const loading = ref(false);
const error = ref('');
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const activeTabConfig = computed(
  () => tabs.find((tab) => tab.key === activeTab.value) || tabs[0]
);

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    xinhua: '新华网',
    people: '人民网',
    mps: '公安部',
    cpd: '中国警察网',
    chinapeace: '中国长安网',
    nia: '国家移民管理局',
    legaldaily: '法治日报',
    cpta: '人事考试网',
    ppsuc: '公安大学',
    cipuc: '刑警学院',
    moj: '司法部',
    nncc: '中国禁毒网',
    spp: '最高检',
    jcy: '中国检察网',
    npc: '中国人大网',
    chinalaw: '中国法学会',
    chinacourt: '中国法院网',
    court: '最高人民法院',
    piyao: '辟谣平台',
    gov: '中国政府网',
    chinafxj: '中国反邪教网',
    beijing: '北京公安',
    tianjin: '天津公安',
    hebei: '河北公安',
    shanxi: '山西公安',
    neimenggu: '内蒙古公安',
    liaoning: '辽宁公安',
    jilin: '吉林公安',
    heilongjiang: '黑龙江公安',
    shanghai: '上海公安',
    jiangsu: '江苏公安',
    zhejiang: '浙江公安',
    anhui: '安徽公安',
    fujian: '福建公安',
    jiangxi: '江西公安',
    shandong: '山东公安',
    henan: '河南公安',
    hubei: '湖北公安',
    hunan: '湖南公安',
    guangdong: '广东公安',
    guangxi: '广西公安',
    hainan: '海南公安',
    chongqing: '重庆公安',
    sichuan: '四川公安',
    guizhou: '贵州公安',
    yunnan: '云南公安',
    xizang: '西藏公安',
    shaanxi: '陕西公安',
    gansu: '甘肃公安',
    qinghai: '青海公安',
    ningxia: '宁夏公安',
    xinjiang: '新疆公安'
  };
  return labels[source] || source || '新闻来源';
}

function formatDate(value: string): string {
  return value.slice(0, 10);
}

async function loadNews(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const tab = activeTabConfig.value;
    const result = await fetchNewsList({
      category: tab.category || undefined,
      keyword: keyword.value.trim() || tab.keyword || undefined,
      limit: 50
    });
    items.value = result.items || [];
    total.value = result.total ?? items.value.length;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '新闻加载失败';
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function selectTab(key: string): void {
  activeTab.value = key;
  void loadNews();
}

function clearSearch(): void {
  keyword.value = '';
  void loadNews();
}

function openNews(item: NewsItem): void {
  router.push(`/news/${item.id}`);
}

function goMore(): void {
  router.push('/news');
}

watch(keyword, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    void loadNews();
  }, 300);
});

onMounted(() => {
  void loadNews();
});

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer);
});
</script>

<style scoped>
.daily-news-panel {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f2f5;
}

.daily-news-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.title-block h3 {
  margin: 0;
  color: #1a2b5f;
  font-size: 20px;
  font-weight: 700;
}

.title-block p {
  margin: 4px 0 0;
  color: #9aa09c;
  font-size: 12px;
}

.more-btn {
  border: 1px solid #d9d3c8;
  border-radius: 7px;
  background: #fff;
  color: #2f5d50;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.search-row input {
  flex: 1;
  min-width: 0;
  border: 1px solid #d9d3c8;
  border-radius: 7px;
  padding: 8px 10px;
  font-size: 13px;
  outline: none;
}

.search-row input:focus {
  border-color: #2f5d50;
}

.search-btn {
  border: 1px solid #2f5d50;
  border-radius: 7px;
  background: #2f5d50;
  color: #fff;
  padding: 0 12px;
  font-size: 13px;
  cursor: pointer;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.tab {
  border: 1px solid #d9d3c8;
  border-radius: 999px;
  background: #fff;
  color: #65706a;
  padding: 4px 9px;
  font-size: 12px;
  cursor: pointer;
}

.tab.active {
  border-color: #2f5d50;
  background: #2f5d50;
  color: #fff;
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 2px 6px;
  color: #9aa09c;
  font-size: 12px;
}

.clear-btn {
  border: 0;
  background: transparent;
  color: #c8763f;
  font-size: 12px;
  cursor: pointer;
}

.news-list {
  border-top: 1px solid #f0f2f5;
}

.news-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 2px;
  border-bottom: 1px solid #f0f2f5;
  cursor: pointer;
}

.news-row:hover,
.news-row:focus {
  background: #faf8f3;
  outline: none;
}

.news-row__main {
  flex: 1;
  min-width: 0;
}

.news-row__main h4 {
  margin: 0;
  color: #1f2321;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
}

.news-row__meta {
  display: flex;
  gap: 10px;
  margin-top: 3px;
  color: #9aa09c;
  font-size: 11px;
}

.news-row__side {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.source-badge {
  border-radius: 6px;
  background: #f2f4f7;
  color: #6b7280;
  padding: 4px 7px;
  font-size: 12px;
  white-space: nowrap;
}

.row-arrow {
  color: #b8bdb9;
  font-size: 20px;
}

.state {
  padding: 24px 8px;
  border-top: 1px solid #f0f2f5;
  color: #9aa09c;
  text-align: center;
  font-size: 13px;
}

.state.error {
  color: #a33b2d;
}

.state.error button {
  margin-left: 8px;
  border: 1px solid #d9d3c8;
  border-radius: 6px;
  background: #fff;
  color: #a33b2d;
  padding: 4px 8px;
  cursor: pointer;
}

@media (max-width: 600px) {
  .daily-news-panel__header {
    gap: 8px;
  }

  .news-row__side {
    gap: 3px;
  }

  .row-arrow {
    display: none;
  }
}
</style>
