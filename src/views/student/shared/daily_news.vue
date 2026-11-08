<template>
  <div class="daily-news">
    <header class="daily-news__header">
      <div class="daily-news__title-row">
        <div>
          <h1>每日新闻</h1>
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

      <nav class="tabs" aria-label="新闻分类">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="['tab', { active: activeTab === tab.key }]"
          @click="selectTab(tab.key)">
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <div class="summary-row">
      <span>{{ loading ? '加载中...' : `共 ${total} 条相关新闻` }}</span>
      <button
        v-if="keyword"
        type="button"
        class="clear-btn"
        @click="clearSearch">
        清除搜索
      </button>
    </div>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="loadNews">重试</button>
    </div>

    <div v-else-if="loading" class="state">正在加载新闻...</div>

    <div v-else-if="!items.length" class="state">
      没有找到匹配的新闻，换个关键词试试。
    </div>

    <section v-else class="news-list" aria-label="新闻列表">
      <article
        v-for="item in items"
        :key="item.id"
        class="news-row"
        tabindex="0"
        @click="openDetail(item)"
        @keydown.enter="openDetail(item)">
        <div class="news-row__main">
          <h3>{{ item.title }}</h3>
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
    </section>
  </div>
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

function openDetail(item: NewsItem): void {
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
.daily-news {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 18px 48px;
  box-sizing: border-box;
  color: #1f2321;
  background: #fbfaf7;
}

.daily-news__header {
  padding: 20px 22px;
  border: 1px solid #e6e1d8;
  border-radius: 14px;
  background: #fff;
}

.daily-news__title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.daily-news__title-row h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.3;
}

.daily-news__title-row p {
  margin: 7px 0 0;
  color: #8a908b;
  font-size: 13px;
}

.more-btn,
.search-btn,
.clear-btn,
.tab {
  border: 1px solid #d9d3c8;
  border-radius: 8px;
  background: #fff;
  color: #2f5d50;
  cursor: pointer;
  font-size: 13px;
}

.more-btn {
  white-space: nowrap;
  padding: 8px 12px;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-top: 18px;
}

.search-row input {
  flex: 1;
  min-width: 0;
  border: 1px solid #d9d3c8;
  border-radius: 8px;
  padding: 9px 11px;
  font-size: 14px;
  outline: none;
}

.search-row input:focus {
  border-color: #2f5d50;
  box-shadow: 0 0 0 2px rgba(47, 93, 80, 0.1);
}

.search-btn {
  padding: 0 16px;
  background: #2f5d50;
  color: #fff;
  border-color: #2f5d50;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 14px;
}

.tab {
  padding: 6px 12px;
  color: #65706a;
}

.tab.active {
  background: #2f5d50;
  border-color: #2f5d50;
  color: #fff;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 4px 9px;
  color: #8a908b;
  font-size: 13px;
}

.clear-btn {
  border: 0;
  background: transparent;
  color: #c8763f;
  padding: 2px 0;
}

.news-list {
  overflow: hidden;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
  background: #fff;
}

.news-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid #f0ede6;
  cursor: pointer;
  transition: background 0.15s ease;
}

.news-row:last-child {
  border-bottom: 0;
}

.news-row:hover,
.news-row:focus {
  background: #f7f4ed;
  outline: none;
}

.news-row__main {
  flex: 1;
  min-width: 0;
}

.news-row__main h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.55;
}

.news-row__meta {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  color: #9aa09c;
  font-size: 12px;
}

.news-row__side {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.source-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eef3f0;
  color: #2f5d50;
  font-size: 12px;
  white-space: nowrap;
}

.row-arrow {
  color: #b8bdb9;
  font-size: 22px;
  line-height: 1;
}

.state {
  padding: 48px 12px;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
  background: #fff;
  text-align: center;
  color: #737a75;
}

.state.error {
  color: #a33b2d;
}

.state.error button {
  margin-top: 10px;
  border: 1px solid #c8763f;
  border-radius: 8px;
  background: #fff;
  color: #a0522d;
  padding: 7px 14px;
  cursor: pointer;
}

@media (max-width: 640px) {
  .daily-news {
    padding: 12px 10px 32px;
  }

  .daily-news__header {
    padding: 16px;
  }

  .news-row {
    padding: 14px;
  }

  .news-row__side {
    gap: 4px;
  }

  .row-arrow {
    display: none;
  }
}
</style>
