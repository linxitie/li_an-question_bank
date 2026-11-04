<template>
  <Transition name="btt-fade">
    <button
      v-if="visible"
      class="back-to-top"
      type="button"
      aria-label="回到顶部"
      title="回到顶部"
      @click="scrollToTop">
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path
          d="M12 5l-7 7h4v7h6v-7h4l-7-7z"
          fill="currentColor" />
      </svg>
    </button>
  </Transition>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

/**
 * 全局「回到顶部」按钮。
 *
 * 为什么放在 App.vue 而不是各页面里：
 * 学生端 PC 论坛是 VTJ raw 页（R3 禁止 AI 改 template），
 * 做成全局组件后三端都能用，且不触碰任何 .vtj 模板。
 */
const route = useRoute();
const visible = ref(false);

const FORUM_ROUTE_PATTERNS = [
  /^\/forum$/,
  /^\/teacher\/forum$/,
  /^\/mobile\/forum/,
  /^\/tablet\/forum/
];

const isForumPage = (path: string) => FORUM_ROUTE_PATTERNS.some((re) => re.test(path));

/** 学生端 PC 论坛把自己的主区做成了滚动容器，其余页面仍是 window 滚动 */
const getScrollRoot = (): HTMLElement | null => {
  const main = document.querySelector('.forum-main') as HTMLElement | null;
  if (main && main.scrollHeight > main.clientHeight + 4) return main;
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

onMounted(() => {
  // capture: true 才能捕获内部滚动容器的 scroll 事件
  window.addEventListener('scroll', update, { passive: true, capture: true });
  update();
});

onUnmounted(() => {
  window.removeEventListener('scroll', update, { capture: true } as EventListenerOptions);
});

watch(() => route.path, () => {
  update();
});
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
  cursor: pointer;
  /* 低于弹窗遮罩（2000/2100），避免盖住详情弹窗 */
  z-index: 1500;
  box-shadow: 0 6px 18px rgba(26, 54, 93, 0.28);
}

.back-to-top:hover {
  background: #24476f;
}

.btt-fade-enter-active,
.btt-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.btt-fade-enter-from,
.btt-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
