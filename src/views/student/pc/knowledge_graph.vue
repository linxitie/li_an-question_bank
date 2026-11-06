<template>
  <div class="kg-page">
    <header class="kg-head">
      <div>
        <h1>我的知识图谱</h1>
        <p class="kg-sub">
          节点大小 = 生长热度，颜色 = 掌握度（红→绿）；连线粗细 = 边权重。图谱只反映你自己的学习轨迹。
        </p>
      </div>
      <div class="kg-actions">
        <button class="kg-btn" :disabled="generating" @click="generateTasks">
          {{ generating ? '生成中…' : '生成本周个性化任务' }}
        </button>
        <button class="kg-btn" @click="panelRef?.loadAll()">刷新</button>
      </div>
    </header>

    <KnowledgeGraphPanel ref="panelRef" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import KnowledgeGraphPanel from '@/components/kg/KnowledgeGraphPanel.vue';

const panelRef = ref<InstanceType<typeof KnowledgeGraphPanel> | null>(null);
const generating = ref(false);

function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
}

async function generateTasks(): Promise<void> {
  generating.value = true;
  try {
    const res = await apiFetch('/api/knowledge/kg/generate?n=2', { method: 'POST' });
    const body = await res.json();
    ElMessage.success(`已生成 ${body.created ?? 0} 个个性化任务`);
    await panelRef.value?.loadAll();
  } catch (e: any) {
    ElMessage.error(e?.message || '生成失败');
  } finally {
    generating.value = false;
  }
}
</script>

<style scoped>
.kg-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  font-family: 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
  color: #1a1a1a;
}
.kg-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.kg-head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
}
.kg-sub {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}
.kg-actions {
  display: flex;
  gap: 8px;
}
.kg-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.kg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
