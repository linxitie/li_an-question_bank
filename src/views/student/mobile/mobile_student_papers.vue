<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">历年试卷</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div v-for="p in papers" :key="p.paper_id" class="card" @click="startPaper(p)">
        <div class="p-name">{{ p.paper_name }}</div>
        <div class="p-meta">
          <span class="tag">{{ subjectName(p.subject_id) }}</span>
          <span class="tag">{{ p.question_count }} 题</span>
          <span class="tag">{{ p.duration }} 分钟</span>
          <span class="tag">{{ examTypeName(p.exam_type) }}</span>
        </div>
      </div>
      <div v-if="!papers.length && !loading" class="empty">暂无已发布试卷</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { usePapersStore } from '@/modules/papers/store';

const router = useRouter();
const papersStore = usePapersStore();
const papers = computed(() => papersStore.items);
const loading = computed(() => papersStore.loading);
let unbindRefresh: (() => void) | null = null;

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const subjectName = (id: number) => {
  return { 1: '行测', 2: '申论', 3: '公专' }[id] || '通用';
};

const examTypeName = (t?: string | null) => {
  // p.exam_type 来自后端，可能缺省；显式声明映射表避免用 undefined 索引对象
  const map: Record<string, string> = { SIMULATION: '模拟卷', PRACTICE: '练习卷', FORMAL: '真题卷' };
  return (t && map[t]) || '试卷';
};

const fetchPapers = async () => {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) return;
  await papersStore.load({ pageSize: 50 });
};

const startPaper = (p: any) => {
  // 移动端答题页尚未开放，先跳 PC 端答题（后续接移动端答题页）
  router.push('/answer?paper_id=' + p.paper_id);
};

onMounted(async () => {
  await fetchPapers();
  unbindRefresh = papersStore.bindRefresh();
});

onUnmounted(() => {
  if (unbindRefresh) unbindRefresh();
});
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
  cursor: pointer;
}
.p-name {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
.p-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.tag {
  font-size: 12px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 3px 8px;
  border-radius: 6px;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
