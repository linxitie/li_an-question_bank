<template>
  <div class="image-grid" :class="`mode-${mode}`">
    <button
      v-for="(image, index) in visibleImages"
      :key="`${image}-${index}`"
      type="button"
      class="ig-cell"
      @click="onCellClick(index)"
    >
      <img :src="image" alt="图片" loading="lazy" />
      <span v-if="isCollapsed && index === visibleImages.length - 1 && hiddenCount" class="ig-badge">
        共 {{ images.length }} 张
      </span>
      <span
        v-else-if="!isCollapsed && !showAll && index === visibleImages.length - 1 && hiddenCount"
        class="ig-badge"
      >
        +{{ hiddenCount }}
      </span>
    </button>

    <Teleport to="body">
      <div v-if="lightboxIndex !== null" class="ig-lightbox" @click.self="lightboxIndex = null">
        <button type="button" class="ig-close" @click="lightboxIndex = null">×</button>
        <img :src="images[lightboxIndex]" alt="查看大图" />
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import { previewImages, shouldCollapse } from './imageUtils';

const props = withDefaults(
  defineProps<{
    images: string[];
    mode?: 'post' | 'comment';
    collapseAt?: number;
    previewMax?: number;
  }>(),
  { mode: 'post', collapseAt: 3, previewMax: 9 }
);

const expanded = ref(false);
const showAll = ref(false);
const lightboxIndex = ref<number | null>(null);

const isCollapsed = computed(
  () => props.mode === 'comment' && !expanded.value && shouldCollapse(props.images.length, props.collapseAt)
);

const visibleImages = computed(() => {
  if (isCollapsed.value) return props.images.slice(0, 1);
  if (props.mode === 'comment') return props.images;
  return previewImages(props.images, showAll.value ? props.images.length : props.previewMax)
    .visible;
});

const hiddenCount = computed(() => {
  if (isCollapsed.value) return Math.max(0, props.images.length - 1);
  if (props.mode === 'comment') return 0;
  return showAll.value ? 0 : previewImages(props.images, props.previewMax).more;
});

const onCellClick = (index: number) => {
  if (isCollapsed.value) {
    expanded.value = true;
    return;
  }
  if (!showAll.value && hiddenCount.value > 0 && index === visibleImages.value.length - 1) {
    showAll.value = true;
    return;
  }
  lightboxIndex.value = index;
};
</script>

<style scoped>
.image-grid {
  display: grid;
  gap: 6px;
  margin-top: 8px;
}
.image-grid.mode-post {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.image-grid.mode-comment {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  max-width: 360px;
}
.ig-cell {
  position: relative;
  padding: 0;
  border: none;
  border-radius: 8px;
  overflow: hidden;
  background: #f2f5fa;
  cursor: pointer;
  aspect-ratio: 1 / 1;
}
.ig-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.mode-comment .ig-cell {
  aspect-ratio: 4 / 3;
}
.ig-badge {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  font-size: 13px;
}
.ig-lightbox {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(8, 12, 24, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.ig-lightbox img {
  max-width: 92vw;
  max-height: 88vh;
  object-fit: contain;
  border-radius: 8px;
}
.ig-close {
  position: absolute;
  top: 16px;
  right: 20px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  font-size: 22px;
  cursor: pointer;
}
</style>
