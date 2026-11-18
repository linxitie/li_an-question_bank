<template>
  <teleport to="body">
    <div class="kgm-mask" @click.self="close">
      <section class="kgm-modal" role="dialog" aria-modal="true" aria-label="我的知识图谱">
        <header class="kgm-head">
          <div>
            <h3>我的知识图谱</h3>
            <p class="kgm-sub">
              悬停节点高亮关联；滚轮缩放、拖拽空白处平移；只反映你自己的学习轨迹。
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

/* ===== 2026-11-16：手机端弹窗改为「全屏 + 可滚动」=====
   旧版 .kgm-body 是 overflow:hidden 的 flex 容器，内容（画布+3 张侧卡+详情条）比 body 高时
   会被压缩/裁切，出现「做题习惯」文字压到画布提示语上的错位。这里把手机端 body 改成可滚动块级容器，
   并把弹窗改成整屏 sheet，任何机型/字体缩放都不会再重叠。 */
@media (max-width: 768px) {
  .kgm-mask {
    padding: 0;
    align-items: stretch;
  }
  .kgm-modal {
    width: 100%;
    height: 100vh;
    height: 100dvh;
    max-height: none;
    border-radius: 0;
  }
  /* 标题区竖排（窄屏下横排会把标题挤成一字一行），操作行单独一行 */
  .kgm-head {
    position: sticky;
    top: 0;
    z-index: 3;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    padding: 12px 14px 10px;
    background: #fff;
    box-shadow: 0 1px 0 #eef2f7;
  }
  .kgm-head > div:first-child {
    min-width: 0;
  }
  .kgm-head h3 {
    font-size: 17px;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .kgm-sub {
    font-size: 11px;
    line-height: 1.5;
    margin-top: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .kgm-actions {
    width: 100%;
    flex: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .kgm-btn {
    flex: 0 1 auto;
    padding: 8px 12px;
    font-size: 12.5px;
    line-height: 1.25;
    max-width: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .kgm-close {
    width: 34px;
    height: 34px;
    flex: none;
  }
  /* 关键：可滚动 + 块级，避免内容被压缩后与画布提示语重叠 */
  .kgm-body {
    flex: 1 1 auto;
    min-height: 0;
    display: block;
    overflow-x: hidden;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    /* 底部多留 96px：节点详情条是 sticky 的，留出滚动余量避免遮住最后一张卡 */
    padding: 10px 10px calc(96px + env(safe-area-inset-bottom, 0px));
  }
  /* 面板自身带「弹窗里撑满高度」的规则（.kgp height:100% / grid flex:1），
     在可滚动的手机弹窗里会把画布行压扁，导致 svg 溢出、提示语与侧卡重叠。
     这里把弹窗内的图谱强制改成「内容高度」，由 .kgm-body 统一滚动。 */
  .kgm-body :deep(.kgp) {
    height: auto;
    display: block;
    flex: none;
    min-height: 0;
  }
  .kgm-body :deep(.kgp-grid) {
    height: auto;
    flex: none;
  }
  .kgm-body :deep(.kgp-canvas-card) {
    min-height: auto;
  }
  .kgm-body :deep(.kgp-svg) {
    flex: none;
    height: 260px;
    min-height: 0;
  }
  .kgm-body :deep(.is-compact .kgp-svg) {
    flex: none;
    height: 240px;
    min-height: 0;
  }
  .kgm-body :deep(.kgp-side) {
    overflow: visible;
    min-height: 0;
  }
}
</style>
