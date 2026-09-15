<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">招考信息</h1>
      <span class="spacer"></span>
    </header>

    <!-- 分类 Tab -->
    <div class="tabs">
      <div
        v-for="cat in categories"
        :key="cat"
        :class="['tab', { active: activeCat === cat }]"
        @click="activeCat = cat"
      >
        {{ cat }}
      </div>
    </div>

    <main class="list">
      <div
        v-for="item in currentItems"
        :key="item.id"
        class="card"
        @click="toggleDetail(item)"
      >
        <div class="r-title">{{ item.title }}</div>
        <div class="r-meta">
          <span class="status" :style="{ color: item.status_color }">{{ item.status_label || item.tag }}</span>
          <span v-if="item.region" class="region">{{ item.region }}</span>
          <span v-if="item.registration_end" class="date">截止 {{ item.registration_end }}</span>
        </div>
        <div v-if="expandedId === item.id" class="detail" @click.stop>
          <div class="detail-content" v-html="item.content_html || item.content || ''"></div>
          <div v-if="item.contact_info" class="contact">联系电话：{{ item.contact_info }}</div>
          <a v-if="item.url" :href="item.url" target="_blank" rel="noopener" class="origin-link">查看原文</a>
        </div>
      </div>
      <div v-if="!currentItems.length && !loading" class="empty">该分类暂无招考信息</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const categories = ref<string[]>([]);
const items = ref<Record<string, any[]>>({});
const activeCat = ref('');
const loading = ref(false);
const expandedId = ref<number | null>(null);

const currentItems = computed(() => items.value[activeCat.value] || []);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const toggleDetail = (item: any) => {
  expandedId.value = expandedId.value === item.id ? null : item.id;
};

const fetchRecruitment = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/recruitment?limit=20');
    const data = await res.json();
    if (res.ok && data.categories) {
      categories.value = data.categories;
      items.value = data.items || {};
      if (!activeCat.value && categories.value.length) activeCat.value = categories.value[0];
    }
  } catch (e) {
    console.error('获取招考信息失败:', e);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchRecruitment);
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}
.tabs {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
  overflow-x: auto;
  white-space: nowrap;
}
.tab {
  flex-shrink: 0;
  padding: 7px 14px;
  border-radius: 18px;
  font-size: 13px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.tab.active {
  background: #1a2b5f;
  color: #fff;
}
.list {
  flex: 1;
  padding: 12px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.r-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
.r-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.status {
  font-size: 12px;
  font-weight: 600;
}
.region,
.date {
  font-size: 12px;
  color: #8899aa;
}
.detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
.detail-content :deep(p) {
  font-size: 14px;
  line-height: 1.7;
  color: #1a2a3a;
  margin-bottom: 10px;
}
.contact {
  font-size: 13px;
  color: #5a6488;
  margin-top: 8px;
}
.origin-link {
  display: inline-block;
  margin-top: 10px;
  font-size: 13px;
  color: #1a2b5f;
  text-decoration: none;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
