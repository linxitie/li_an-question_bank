<template>
  <Transition name="btt-fade">
    <button
      v-if="visible"
      class="back-to-top"
      :style="posStyle"
      type="button"
      aria-label="回到顶部"
      title="回到顶部（可拖动）"
      @pointerdown="onPointerDown"
      @click="onClick">
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path d="M12 5l-7 7h4v7h6v-7h4l-7-7z" fill="currentColor" />
      </svg>
    </button>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

/**
 * 全局「回到顶部」按钮（2026-11-07：改为可拖动，避免遮挡页面功能）。
 * 位置存 localStorage，三端共用。
 */
const route = useRoute();
const visible = ref(false);
const STORAGE_KEY = 'btt-position-v1';
const MIN_VISIBLE = 8;

const pos = reactive<{ right: number; bottom: number }>({ right: 24, bottom: 24 });
const drag = reactive({ active: false, moved: false, startX: 0, startY: 0, startRight: 0, startBottom: 0 });

const posStyle = computed(() => ({
  right: `${pos.right}px`,
  bottom: `${pos.bottom}px`
}));

const FORUM_ROUTE_PATTERNS = [
  /^\/forum$/,
  /^\/teacher\/forum$/,
  /^\/mobile\/forum/,
  /^\/tablet\/forum/
];
const isForumPage = (path: string) => FORUM_ROUTE_PATTERNS.some((re) => re.test(path));

const SCROLL_ROOTS = ['.forum-main', '.tf-page', '.tablet-forum-page', '.main-content'];
const getScrollRoot = (): HTMLElement | null => {
  for (const sel of SCROLL_ROOTS) {
    const el = document.querySelector(sel) as HTMLElement | null;
    if (el && el.scrollHeight > el.clientHeight + 4) return el;
  }
  return null;
};

const getScrollTop = () => {
  const root = getScrollRoot();
  return root ? root.scrollTop : window.scrollY;
};

const update = () => {
  visible.value = isForumPage(route.path) && getScrollTop() > 400;
};

const scrollToTop = () => {
  const root = getScrollRoot();
  if (root) root.scrollTo({ top: 0, behavior: 'smooth' });
  else window.scrollTo({ top: 0, behavior: 'smooth' });
};

function clampPosition() {
  const maxRight = Math.max(MIN_VISIBLE, window.innerWidth - 60);
  const maxBottom = Math.max(MIN_VISIBLE, window.innerHeight - 60);
  pos.right = Math.min(Math.max(pos.right, MIN_VISIBLE), maxRight);
  pos.bottom = Math.min(Math.max(pos.bottom, MIN_VISIBLE), maxBottom);
}

function savePosition() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ right: pos.right, bottom: pos.bottom }));
  } catch {
    /* 忽略 */
  }
}

function restorePosition() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (typeof data.right === 'number' && typeof data.bottom === 'number') {
      pos.right = data.right;
      pos.bottom = data.bottom;
      clampPosition();
    }
  } catch {
    /* 忽略 */
  }
}

function onPointerDown(e: PointerEvent) {
  drag.active = true;
  drag.moved = false;
  drag.startX = e.clientX;
  drag.startY = e.clientY;
  drag.startRight = pos.right;
  drag.startBottom = pos.bottom;
  (e.target as HTMLElement | null)?.setPointerCapture?.(e.pointerId);
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
}

function onPointerMove(e: PointerEvent) {
  if (!drag.active) return;
  const dx = e.clientX - drag.startX;
  const dy = e.clientY - drag.startY;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;
  pos.right = drag.startRight - dx;
  pos.bottom = drag.startBottom - dy;
  clampPosition();
}

function onPointerUp() {
  drag.active = false;
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
  if (drag.moved) savePosition();
}

function onClick() {
  if (drag.moved) {
    drag.moved = false;
    return;
  }
  scrollToTop();
}

onMounted(() => {
  restorePosition();
  window.addEventListener('scroll', update, { passive: true, capture: true });
  window.addEventListener('resize', clampPosition);
  update();
});

onUnmounted(() => {
  window.removeEventListener('scroll', update, { capture: true } as EventListenerOptions);
  window.removeEventListener('resize', clampPosition);
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
});

watch(
  () => route.path,
  () => {
    update();
  }
);
</script>

<style scoped>
.back-to-top {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: #1a365d;
  color: #fff;
  cursor: grab;
  touch-action: none;
  user-select: none;
  z-index: 1500;
  box-shadow: 0 6px 18px rgba(26, 54, 93, 0.28);
}
.back-to-top:active { cursor: grabbing; }
.back-to-top:hover { background: #24476f; }
.btt-fade-enter-active,
.btt-fade-leave-active { transition: opacity 0.2s ease; }
.btt-fade-enter-from,
.btt-fade-leave-to { opacity: 0; }
</style>
