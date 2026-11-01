<template>
  <!-- 精选星标：金色五角星。徽章卡左上角 / 详情弹层右侧共用同一个图形。 -->
  <svg
    class="pin-star"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    :aria-label="label"
    role="img"
  >
    <defs>
      <linearGradient :id="gradId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#FFE07A" />
        <stop offset="52%" stop-color="#F7B733" />
        <stop offset="100%" stop-color="#E0930B" />
      </linearGradient>
    </defs>
    <path
      d="M12 1.9l3.02 6.12 6.76.98-4.89 4.77 1.16 6.73L12 17.32l-6.05 3.18 1.16-6.73L2.22 9l6.76-.98z"
      :fill="`url(#${gradId})`"
      stroke="#D98A06"
      stroke-width="0.8"
      stroke-linejoin="round"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue';

const props = withDefaults(
  defineProps<{
    size?: number;
    label?: string;
  }>(),
  { size: 22, label: '精选' }
);

// 同一页面会同时出现多个星标，渐变 id 必须唯一（useId 为 Vue 3.5 内置）
const rawId = useId();
const gradId = computed(() => `pinStarGold-${rawId.replace(/[^\w-]/g, '')}`);
</script>

<style scoped>
.pin-star {
  display: block;
  flex: none;
  filter: drop-shadow(0 1px 2px rgba(160, 108, 0, 0.28));
}
</style>
