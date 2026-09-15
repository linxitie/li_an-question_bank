<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">收藏</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div v-for="item in items" :key="item.fav_id" class="card">
        <div class="q-title">{{ item.question_content }}</div>
        <div class="q-answer" v-if="item.answer">答案：{{ item.answer }}</div>
        <button class="unfav-btn" @click="removeFav(item)">取消收藏</button>
      </div>
      <div v-if="!items.length && !loading" class="empty">暂无收藏</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const items = ref<any[]>([]);
const loading = ref(false);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const fetchFavorites = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/questions/favorites?page=1&page_size=50');
    const data = await res.json();
    if (res.ok && data.items) items.value = data.items;
  } catch (e) {
    console.error('获取收藏失败:', e);
  } finally {
    loading.value = false;
  }
};

const removeFav = async (item: any) => {
  try {
    // 收藏接口为 toggle：再次调用即取消收藏
    await (window as any).__VTJ_AUTH__.apiFetch('/api/questions/' + item.question_id + '/favorite', { method: 'POST' });
    items.value = items.value.filter((i) => i.fav_id !== item.fav_id);
  } catch (e) {
    console.error('取消收藏失败:', e);
  }
};

onMounted(fetchFavorites);
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
  position: sticky;
  top: 0;
  z-index: 10;
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
}
.q-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
.q-answer {
  font-size: 13px;
  color: #5a6488;
  margin-bottom: 8px;
}
.unfav-btn {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid #ffccc7;
  background: #fff2f0;
  color: #c41e3a;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
