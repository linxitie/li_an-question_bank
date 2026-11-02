<template>
  <!-- 全图查看器：点击配图后铺满视口，支持缩放 / 左右切换 / Esc 关闭 -->
  <div v-if="open && images.length" class="lb-mask" @click.self="close">
    <header class="lb-head">
      <span class="lb-count">{{ index + 1 }} / {{ images.length }}</span>
      <div class="lb-tools">
        <button class="lb-tool" :disabled="scale <= 1" title="缩小" @click="zoom(-0.25)">－</button>
        <span class="lb-scale">{{ Math.round(scale * 100) }}%</span>
        <button class="lb-tool" :disabled="scale >= 3" title="放大" @click="zoom(0.25)">＋</button>
        <button class="lb-tool lb-reset" title="原始大小" @click="scale = 1">1:1</button>
        <button class="lb-tool lb-close" title="关闭（Esc）" @click="close">✕</button>
      </div>
    </header>

    <button
      v-if="images.length > 1"
      class="lb-nav lb-prev"
      aria-label="上一张"
      @click.stop="step(-1)"
    >‹</button>

    <div class="lb-stage" @click.self="close">
      <img
        class="lb-img"
        :src="images[index]"
        :alt="`配图 ${index + 1}`"
        :style="{ transform: `scale(${scale})` }"
        @click.stop
      />
    </div>

    <button
      v-if="images.length > 1"
      class="lb-nav lb-next"
      aria-label="下一张"
      @click.stop="step(1)"
    >›</button>

    <p class="lb-tip">{{ tip }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    open?: boolean;
    images?: string[];
    startIndex?: number;
  }>(),
  { open: false, images: () => [], startIndex: 0 }
);

const emit = defineEmits<{ (e: 'close'): void }>();

const index = ref(0);
const scale = ref(1);

/** 触屏与桌面给不同的操作提示（手机没有滚轮/Esc） */
const tip = computed(() => {
  const coarse =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(pointer: coarse)').matches;
  return coarse
    ? '左右按钮切换 · ＋ － 缩放 · 点右上角 ✕ 关闭'
    : '滚轮或按钮缩放 · 左右切换 · Esc 关闭';
});

const close = () => emit('close');
const step = (delta: number) => {
  const n = props.images.length;
  if (!n) return;
  index.value = (index.value + delta + n) % n;
  scale.value = 1;
};
const zoom = (delta: number) => {
  scale.value = Math.min(3, Math.max(1, Number((scale.value + delta).toFixed(2))));
};

const onWheel = (e: WheelEvent) => {
  e.preventDefault();
  zoom(e.deltaY > 0 ? -0.25 : 0.25);
};

const onKey = (e: KeyboardEvent) => {
  if (!props.open) return;
  if (e.key === 'Escape') close();
  else if (e.key === 'ArrowLeft') step(-1);
  else if (e.key === 'ArrowRight') step(1);
  else if (e.key === '+' || e.key === '=') zoom(0.25);
  else if (e.key === '-') zoom(-0.25);
};

watch(
  () => props.open,
  (v) => {
    if (v) {
      index.value = Math.min(Math.max(0, props.startIndex), Math.max(0, props.images.length - 1));
      scale.value = 1;
      document.addEventListener('keydown', onKey);
      document.addEventListener('wheel', onWheel, { passive: false });
      document.body.style.overflow = 'hidden';
    } else {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('wheel', onWheel);
      document.body.style.overflow = '';
    }
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey);
  document.removeEventListener('wheel', onWheel);
  document.body.style.overflow = '';
});
</script>

<style scoped>
.lb-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(8, 12, 20, 0.88);
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(2px);
}
.lb-head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  color: #dbe4f3;
}
.lb-count {
  font-size: 13px;
  letter-spacing: 1px;
}
.lb-tools {
  display: flex;
  align-items: center;
  gap: 6px;
}
.lb-tool {
  min-width: 34px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  color: #e8eefb;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.lb-tool:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.18);
}
.lb-tool:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.lb-scale {
  min-width: 48px;
  text-align: center;
  font-size: 12px;
  color: #b7c4da;
}
.lb-close {
  margin-left: 6px;
}
.lb-stage {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 56px 12px;
}
.lb-img {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 8px;
  background: #0f1622;
  transition: transform 0.16s ease;
  transform-origin: center center;
}
.lb-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 64px;
  border: none;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
}
.lb-nav:hover {
  background: rgba(255, 255, 255, 0.22);
}
.lb-prev {
  left: 10px;
}
.lb-next {
  right: 10px;
}
.lb-tip {
  flex: none;
  margin: 0;
  padding: 10px 0 16px;
  text-align: center;
  font-size: 12px;
  color: #93a2ba;
}
</style>
