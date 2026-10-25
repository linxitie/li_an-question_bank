<!-- 平板端论坛帖子详情页：独立整页，版式对齐 PC 详情卡 -->
<template>
  <div class="tablet-forum-detail">
    <header class="topbar">
      <button class="back-btn" type="button" @click="goBack">←</button>
      <h1 class="title">帖子详情</h1>
      <span class="topbar-spacer" />
    </header>

    <main class="content">
      <div v-if="loading" class="state-loading">加载中...</div>
      <div v-else-if="loadError" class="state-error">{{ loadError }}</div>
      <div v-else-if="!post" class="state-empty">帖子不存在或已被删除</div>
      <article v-else class="detail-card" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useCommunityStore } from '@/modules/community/store';

const route = useRoute();
const router = useRouter();
const store = useCommunityStore();

const postId = Number(route.params.id);
const post = computed(() => store.detail);
const loading = ref(true);
const loadError = ref('');

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/tablet/forum');
};

const load = async () => {
  loading.value = true;
  loadError.value = '';

  if (!Number.isFinite(postId) || postId <= 0) {
    loadError.value = '帖子不存在或已被删除';
    loading.value = false;
    return;
  }

  const detail = await store.loadPost(postId);
  if (!detail) loadError.value = '帖子不存在或已被删除';
  loading.value = false;
};

onMounted(load);
</script>

<style scoped>
.tablet-forum-detail {
  min-height: 100vh;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.topbar {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e8ecf1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: none;
  font-size: 20px;
  color: #1a2b5f;
  cursor: pointer;
  border-radius: 8px;
}

.back-btn:hover {
  background: #f0f4fa;
}

.title {
  font-size: 17px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}

.topbar-spacer {
  width: 40px;
}

.content {
  padding: 24px;
}

.detail-card {
  max-width: 920px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(26, 54, 93, 0.06);
}

.state-loading,
.state-error,
.state-empty {
  max-width: 920px;
  margin: 0 auto;
  padding: 48px 24px;
  text-align: center;
  color: #8899aa;
  font-size: 14px;
  background: #fff;
  border-radius: 12px;
}

.state-error {
  color: #c41e3a;
}
</style>
