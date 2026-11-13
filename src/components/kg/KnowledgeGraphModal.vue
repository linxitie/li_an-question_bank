<template>
  <teleport to="body">
    <div class="kgm-mask" @click.self="close">
      <section class="kgm-modal" role="dialog" aria-modal="true" aria-label="我的知识图谱">
        <header class="kgm-head">
          <div>
            <h3>我的知识图谱</h3>
            <p class="kgm-sub">
              节点大小 = 生长热度，颜色区分知识点；只反映你自己的学习轨迹。
            </p>
          </div>
          <div class="kgm-actions">
            <button class="kgm-btn" :disabled="generating" @click="generate">
              {{ generating ? '生成中…' : '生成本周个性化任务' }}
            </button>
            <button class="kgm-close" aria-label="关闭" @click="close">×</button>
          </div>
        </header>

        <div class="kgm-body">
          <KnowledgeGraphPanel ref="panelRef" compact />
        </div>
      </section>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import KnowledgeGraphPanel from './KnowledgeGraphPanel.vue';

const emit = defineEmits<{ (e: 'close'): void }>();
const panelRef = ref<InstanceType<typeof KnowledgeGraphPanel> | null>(null);
const generating = ref(false);

function close(): void {
  emit('close');
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') close();
}

async function generate(): Promise<void> {
  generating.value = true;
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const res =
      auth && typeof auth.apiFetch === 'function'
        ? await auth.apiFetch('/api/knowledge/kg/generate?n=2', { method: 'POST' })
        : await fetch('/api/knowledge/kg/generate?n=2', { method: 'POST', credentials: 'include' });
    const body = await res.json();
    ElMessage.success(`已生成 ${body.created ?? 0} 个个性化任务`);
    await panelRef.value?.loadAll();
  } catch (e: any) {
    ElMessage.error(e?.message || '生成失败');
  } finally {
    generating.value = false;
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKey);
  const prev = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  (window as any).__kgmPrevOverflow = prev;
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey);
  document.body.style.overflow = (window as any).__kgmPrevOverflow || '';
});
</script>

<style scoped>
.kgm-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.kgm-modal {
  width: min(1080px, 100%);
  height: min(88vh, 820px);
  display: flex;
  flex-direction: column;
  background: #f9fafc;
  border-radius: 16px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
  overflow: hidden;
  animation: kgm-pop 180ms ease-out;
}
@keyframes kgm-pop {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.kgm-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px 12px;
  background: #fff;
  border-bottom: 1px solid #eef2f7;
}
.kgm-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}
.kgm-sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}
.kgm-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.kgm-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 10px;
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.kgm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.kgm-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}
.kgm-close:hover {
  background: #e5e7eb;
}
.kgm-body {
  padding: 14px 18px 18px;
  overflow-y: auto;
}
@media (max-width: 640px) {
  .kgm-mask {
    padding: 0;
    align-items: flex-end;
  }
  .kgm-modal {
    width: 100%;
    max-height: 92vh;
    border-radius: 16px 16px 0 0;
  }
}
/* 2026-11-09：手机端图谱弹窗全屏化，避免拥挤 */
@media (max-width: 768px) {
  .kgm-mask { padding: 8px; align-items: stretch; }
  .kgm-modal { width: 100%; height: calc(100vh - 16px); max-height: 100%; border-radius: 12px; }
  .kgm-head { flex-direction: column; gap: 8px; padding: 12px 14px 10px; }
  .kgm-head h3 { font-size: 16px; }
  .kgm-sub { font-size: 11px; }
  .kgm-actions { width: 100%; justify-content: space-between; }
  .kgm-body { padding: 8px; }
}
/* 2026-11-09：内容区不滚动，图谱撑满，详情条贴弹窗底部 */
.kgm-body { flex: 1; min-height: 0; overflow: hidden; display: flex; }
.kgm-body :deep(.kgp) { flex: 1; min-height: 0; }
</style>
