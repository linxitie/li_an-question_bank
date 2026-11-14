<template>
  <div class="mobile-radar-page">
    <header class="topbar">
      <button class="back-btn" type="button" @click="goBack" aria-label="返回">
        ←
      </button>
      <h1>招考雷达</h1>
      <button class="filter-btn" type="button" @click="filterOpen = true">
        筛选
      </button>
    </header>

    <form class="search-row" @submit.prevent="search">
      <input
        v-model="keyword"
        type="search"
        placeholder="搜索岗位、单位、专业"
        aria-label="搜索岗位" />
      <button type="submit">搜索</button>
    </form>

    <div class="result-meta">
      <span>共 {{ total }} 个岗位</span>
      <span
        v-if="filters.province || filters.education || filters.major"
        class="active-filter">
        已筛选
        <button type="button" @click="resetFilters">重置</button>
      </span>
    </div>

    <div v-if="error" class="state error">{{ error }}</div>
    <div v-else-if="loading" class="state">岗位加载中...</div>
    <div v-else-if="!items.length" class="state">暂无匹配岗位</div>

    <main v-else class="job-list">
      <article
        v-for="item in items"
        :key="item.post_id"
        class="job-card"
        @click="openDetail(item)">
        <div class="job-card__top">
          <span
            class="condition-badge"
            :class="{ warning: !item.education_req }">
            {{ item.education_req || '学历未写明' }}
          </span>
          <span class="plan-count"
            >招 {{ item.plan_count || '未写明' }} 人</span
          >
        </div>
        <h2>{{ item.job_name }}</h2>
        <p class="employer">{{ item.employer }}</p>
        <p class="region">{{ item.province }}{{ item.city }}</p>
        <div class="chips">
          <span>专业：{{ item.major_req || '未写明' }}</span>
          <span>政治面貌：{{ item.political_req || '未写明' }}</span>
        </div>
        <p v-if="item.registration_end" class="deadline">
          报名截止：{{ item.registration_end }}
        </p>
        <p class="announcement">
          公告：{{ item.announcement_title || '未关联公告' }}
        </p>
      </article>
    </main>

    <div v-if="total > pageSize" class="pager">
      <button type="button" :disabled="page <= 1" @click="changePage(-1)">
        上一页
      </button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button
        type="button"
        :disabled="page >= Math.ceil(total / pageSize)"
        @click="changePage(1)">
        下一页
      </button>
    </div>

    <MobileTabBar active="recruitment" />

    <div v-if="filterOpen" class="mask" @click.self="filterOpen = false">
      <aside class="filter-drawer">
        <h2>筛选岗位</h2>
        <label
          >地区
          <select v-model="filters.province">
            <option value="">全部地区</option>
            <option v-for="p in provinces" :key="p" :value="p">{{ p }}</option>
          </select>
        </label>
        <label
          >学历
          <select v-model="filters.education">
            <option value="">全部学历</option>
            <option value="大专">大专</option>
            <option value="本科">本科</option>
            <option value="硕士">硕士</option>
            <option value="博士">博士</option>
          </select>
        </label>
        <label
          >专业关键词
          <input v-model="filters.major" placeholder="例如：法学" />
        </label>
        <div class="drawer-actions">
          <button type="button" @click="resetFilters">重置</button>
          <button type="button" class="primary" @click="applyFilters">
            应用筛选
          </button>
        </div>
      </aside>
    </div>

    <div v-if="detail" class="mask" @click.self="detail = null">
      <section class="detail-modal">
        <button class="close-btn" type="button" @click="detail = null">
          ×
        </button>
        <h2>{{ detail.job_name }}</h2>
        <p class="employer">{{ detail.employer }}</p>
        <dl class="facts">
          <div>
            <dt>地区</dt>
            <dd>{{ detail.province }}{{ detail.city }}</dd>
          </div>
          <div>
            <dt>学历</dt>
            <dd>{{ detail.education_req || '未写明' }}</dd>
          </div>
          <div>
            <dt>专业</dt>
            <dd>{{ detail.major_req || '未写明' }}</dd>
          </div>
          <div>
            <dt>政治面貌</dt>
            <dd>{{ detail.political_req || '未写明' }}</dd>
          </div>
          <div>
            <dt>招录人数</dt>
            <dd>{{ detail.plan_count || '未写明' }}</dd>
          </div>
          <div>
            <dt>报名截止</dt>
            <dd>{{ detail.registration_end || '未写明' }}</dd>
          </div>
        </dl>
        <h3>对应公告</h3>
        <p class="announcement">
          {{ detail.announcement_title || '未关联公告' }}
        </p>
        <a
          v-if="detail.official_url"
          :href="detail.official_url"
          target="_blank"
          rel="noopener">
          查看公告原文
        </a>
        <span v-else class="unavailable">原文链接暂不可用</span>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import MobileTabBar from '@/components/mobile/MobileTabBar.vue';
import { apiClient } from '@/services/api/client';

interface JobItem {
  post_id: number;
  job_name: string;
  employer: string;
  province: string;
  city: string;
  education_req: string;
  major_req: string;
  political_req: string;
  plan_count: number;
  registration_end: string;
  official_url: string;
  announcement_title: string;
}

const router = useRouter();
const items = ref<JobItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const error = ref('');
const filterOpen = ref(false);
const detail = ref<JobItem | null>(null);
const keyword = ref('');
const filters = reactive({ province: '', education: '', major: '' });
const provinces = [
  '北京',
  '天津',
  '河北',
  '山西',
  '内蒙古',
  '辽宁',
  '吉林',
  '黑龙江',
  '上海',
  '江苏',
  '浙江',
  '安徽',
  '福建',
  '江西',
  '山东',
  '河南',
  '湖北',
  '湖南',
  '广东',
  '广西',
  '海南',
  '重庆',
  '四川',
  '贵州',
  '云南',
  '西藏',
  '陕西',
  '甘肃',
  '青海',
  '宁夏',
  '新疆'
];

function goBack(): void {
  router.push('/mobile/home');
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const response = await apiClient.request<any>({
      url: '/api/recruitment/radar',
      method: 'GET',
      baseURL: '',
      params: {
        keyword: keyword.value.trim() || undefined,
        province: filters.province || undefined,
        education: filters.education || undefined,
        major: filters.major || undefined,
        page: page.value,
        page_size: pageSize
      }
    });
    items.value = response.data.items || [];
    total.value = response.data.total || 0;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '岗位加载失败';
  } finally {
    loading.value = false;
  }
}

function search(): void {
  page.value = 1;
  void load();
}

function applyFilters(): void {
  filterOpen.value = false;
  page.value = 1;
  void load();
}

function resetFilters(): void {
  filters.province = '';
  filters.education = '';
  filters.major = '';
  filterOpen.value = false;
  page.value = 1;
  void load();
}

function changePage(delta: number): void {
  page.value = Math.max(1, page.value + delta);
  void load();
}

function openDetail(item: JobItem): void {
  detail.value = item;
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.mobile-radar-page {
  min-height: 100vh;
  padding-bottom: 76px;
  background: #f5f7fa;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 48px;
  padding: 0 12px;
  background: #fff;
  border-bottom: 1px solid #e8ecf1;
}
.topbar h1 {
  flex: 1;
  margin: 0;
  color: #1a2b5f;
  font-size: 17px;
  text-align: center;
}
.back-btn,
.filter-btn {
  border: 0;
  background: transparent;
  color: #1a2b5f;
  font-size: 14px;
  cursor: pointer;
}
.back-btn {
  font-size: 22px;
  padding: 4px 8px;
}
.search-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px 0;
}
.search-row input {
  flex: 1;
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid #d6dfea;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
}
.search-row button,
.pager button {
  border: 1px solid #1a2b5f;
  border-radius: 8px;
  background: #1a2b5f;
  color: #fff;
  padding: 0 12px;
  font-size: 12px;
  cursor: pointer;
}
.result-meta {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  color: #8894a3;
  font-size: 12px;
}
.active-filter button {
  border: 0;
  background: transparent;
  color: #2f5d50;
  cursor: pointer;
}
.job-list {
  display: grid;
  gap: 10px;
  padding: 0 12px 12px;
}
.job-card {
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(26, 42, 70, 0.04);
  cursor: pointer;
}
.job-card__top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}
.condition-badge {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef6f1;
  color: #2f5d50;
  font-size: 11px;
}
.condition-badge.warning {
  background: #fff4df;
  color: #946b22;
}
.plan-count {
  color: #8894a3;
  font-size: 11px;
}
.job-card h2 {
  margin: 9px 0 4px;
  color: #1a2b5f;
  font-size: 17px;
  line-height: 1.4;
}
.employer {
  margin: 0;
  color: #59635c;
  font-size: 12px;
}
.region {
  margin: 5px 0 0;
  color: #8894a3;
  font-size: 12px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
}
.chips span {
  padding: 3px 7px;
  border-radius: 6px;
  background: #f0f4f8;
  color: #53657a;
  font-size: 11px;
}
.deadline {
  margin: 9px 0 0;
  color: #a36a28;
  font-size: 12px;
}
.announcement {
  margin: 9px 0 0;
  color: #8894a3;
  font-size: 11px;
  line-height: 1.5;
}
.pager {
  display: flex;
  justify-content: center;
  gap: 12px;
  align-items: center;
  margin: 8px 0 16px;
  color: #8894a3;
  font-size: 12px;
}
.pager button {
  padding: 6px 10px;
}
.pager button:disabled {
  opacity: 0.4;
  cursor: default;
}
.state {
  padding: 50px 20px;
  text-align: center;
  color: #8894a3;
  font-size: 13px;
}
.state.error {
  color: #a33b2d;
}
.mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(16, 42, 71, 0.3);
  display: flex;
  justify-content: center;
  align-items: flex-end;
}
.filter-drawer {
  width: 100%;
  max-height: 80vh;
  overflow: auto;
  padding: 20px 16px 28px;
  border-radius: 18px 18px 0 0;
  background: #fff;
}
.filter-drawer h2,
.detail-modal h2 {
  margin: 0 0 14px;
  color: #1a2b5f;
}
.filter-drawer label {
  display: block;
  margin: 12px 0;
  color: #59635c;
  font-size: 12px;
}
.filter-drawer select,
.filter-drawer input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin-top: 6px;
  padding: 9px;
  border: 1px solid #d6dfea;
  border-radius: 8px;
  background: #fff;
}
.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}
.drawer-actions button {
  padding: 8px 12px;
  border: 1px solid #d6dfea;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}
.drawer-actions .primary {
  border-color: #1a2b5f;
  background: #1a2b5f;
  color: #fff;
}
.detail-modal {
  width: 100%;
  max-height: 88vh;
  overflow: auto;
  padding: 22px 16px 28px;
  border-radius: 18px 18px 0 0;
  background: #fff;
  position: relative;
}
.close-btn {
  position: absolute;
  top: 8px;
  right: 14px;
  border: 0;
  background: transparent;
  color: #8492a6;
  font-size: 24px;
  cursor: pointer;
}
.facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 16px 0;
}
.facts div {
  padding: 8px;
  border-radius: 8px;
  background: #f7faf8;
}
.facts dt {
  color: #8894a3;
  font-size: 11px;
}
.facts dd {
  margin: 4px 0 0;
  color: #3c4a42;
  font-size: 12px;
}
.detail-modal h3 {
  margin: 16px 0 6px;
  color: #59635c;
  font-size: 13px;
}
.unavailable {
  color: #9aa3ad;
  font-size: 11px;
}
@media (min-width: 720px) {
  .mobile-radar-page {
    max-width: 760px;
    margin: 0 auto;
  }
}
</style>
