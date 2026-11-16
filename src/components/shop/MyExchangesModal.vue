<template>
  <teleport to="body">
    <div class="mex-mask" @click.self="close">
      <section class="mex-modal" role="dialog" aria-modal="true" aria-label="我的兑换">
        <header class="mex-modal-head">
          <h3>我的兑换</h3>
          <p class="mex-modal-sub">虚拟卡类当场发卡密；实物/需开通的显示「待发货/待开通」。</p>
          <button class="mex-close" aria-label="关闭" @click="close">×</button>
        </header>

        <div class="mex-modal-body">
          <MyExchangesPanel compact />
        </div>
      </section>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue';
import MyExchangesPanel from './MyExchangesPanel.vue';

const emit = defineEmits<{ (e: 'close'): void }>();

function close(): void {
  emit('close');
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') close();
}

onMounted(() => {
  document.addEventListener('keydown', onKey);
  // 打开时锁滚动，关闭还原；记下原值避免影响其它弹窗
  const prev = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  (window as any).__mexPrevOverflow = prev;
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey);
  document.body.style.overflow = (window as any).__mexPrevOverflow || '';
});
</script>

<style scoped>
.mex-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.mex-modal {
  width: min(720px, 100%);
  max-height: min(80vh, 760px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
  overflow: hidden;
  animation: mex-pop 180ms ease-out;
}

@keyframes mex-pop {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.mex-modal-head {
  position: relative;
  padding: 18px 20px 12px;
  border-bottom: 1px solid #eef2f7;
}
.mex-modal-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}
.mex-modal-sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}
.mex-close {
  position: absolute;
  top: 12px;
  right: 12px;
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
.mex-close:hover {
  background: #e5e7eb;
}

.mex-modal-body {
  padding: 14px 20px 18px;
  overflow-y: auto;
}

@media (max-width: 640px) {
  .mex-mask {
    padding: 0;
    align-items: flex-end;
  }
  .mex-modal {
    width: 100%;
    max-height: 88vh;
    border-radius: 16px 16px 0 0;
  }
}
</style>
