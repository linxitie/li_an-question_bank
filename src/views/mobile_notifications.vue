<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">通知</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div v-for="m in messages" :key="m.id" class="card">
        <div class="msg-title">{{ m.title }}</div>
        <div class="msg-content">{{ m.content }}</div>
        <div class="msg-time">{{ m.createdAt || '' }}</div>
      </div>
      <div v-if="!messages.length && !loading" class="empty">暂无通知</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const messages = ref<any[]>([]);
const loading = ref(false);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const fetchMessages = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/stats/messages');
    const data = await res.json();
    if (res.ok) messages.value = Array.isArray(data) ? data : (data.items || []);
  } catch (e) {
    console.error('获取通知失败:', e);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchMessages);
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
.msg-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 6px;
}
.msg-content {
  font-size: 14px;
  color: #5a6488;
  line-height: 1.6;
  margin-bottom: 6px;
}
.msg-time {
  font-size: 11px;
  color: #8899aa;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
