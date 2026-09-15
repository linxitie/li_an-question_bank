<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">错题集</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div
        v-for="item in items"
        :key="item.wrong_id"
        class="card"
        @click="toggleDetail(item)"
      >
        <div class="q-title">{{ item.question_content }}</div>
        <div class="q-meta">
          <span class="tag">{{ item.subject_name || '未分类' }}</span>
          <span class="tag">{{ item.question_type_detail || '' }}</span>
          <span class="err">错 {{ item.error_count }} 次</span>
        </div>
        <div v-if="expandedId === item.wrong_id" class="detail" @click.stop>
          <div class="detail-row"><b>答案：</b>{{ item.answer || '无' }}</div>
          <div class="detail-row" v-if="item.answer_analysis"><b>解析：</b>{{ item.answer_analysis }}</div>
          <button class="remove-btn" @click="removeWrong(item.wrong_id)">移出错题</button>
        </div>
      </div>
      <div v-if="!items.length && !loading" class="empty">暂无错题，继续加油！</div>
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
const expandedId = ref<number | null>(null);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const toggleDetail = (item: any) => {
  expandedId.value = expandedId.value === item.wrong_id ? null : item.wrong_id;
};

const fetchWrong = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/wrong-questions?page=1&page_size=50');
    const data = await res.json();
    if (res.ok && data.items) items.value = data.items;
  } catch (e) {
    console.error('获取错题失败:', e);
  } finally {
    loading.value = false;
  }
};

const removeWrong = async (wrongId: number) => {
  try {
    await (window as any).__VTJ_AUTH__.apiFetch('/api/wrong-questions/' + wrongId, { method: 'DELETE' });
    items.value = items.value.filter((i) => i.wrong_id !== wrongId);
    expandedId.value = null;
  } catch (e) {
    console.error('移出错题失败:', e);
  }
};

onMounted(fetchWrong);
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
.q-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
.q-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.tag {
  font-size: 12px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 3px 8px;
  border-radius: 6px;
}
.err {
  font-size: 12px;
  color: #c41e3a;
}
.detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
.detail-row {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.6;
  margin-bottom: 6px;
}
.detail-row b {
  color: #1a2b5f;
}
.remove-btn {
  margin-top: 8px;
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
