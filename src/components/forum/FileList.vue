<template>
  <div v-if="files.length" class="file-list">
    <a
      v-for="file in files"
      :key="file.url"
      class="fl-item"
      :href="file.url"
      :download="canPreview(file.name) ? undefined : file.name"
      :target="canPreview(file.name) ? '_blank' : undefined"
      @click="onOpen($event, file)"
      rel="noopener"
    >
      <span class="fl-icon">{{ fileIcon(file.name) }}</span>
      <span class="fl-name">{{ file.name }}</span>
      <span class="fl-size">{{ formatFileSize(file.size) }}</span>
    </a>
  </div>
</template>

<script setup lang="ts">
import { fileIcon, formatFileSize } from './fileUtils';
import type { ForumImageAttachment } from './imageUtils';

defineProps<{ files: ForumImageAttachment[] }>();

// 2026-10-30：PDF / 图片 / 文本用浏览器内联打开；Office/压缩包仍走下载
const PREVIEW_EXT = ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.txt'];
const canPreview = (name: string) =>
  PREVIEW_EXT.some((ext) => (name || '').toLowerCase().endsWith(ext));

/** 可预览类型：显式新标签打开；被拦截时退回下载（?download=1 强制 attachment） */
const onOpen = (e: MouseEvent, file: ForumImageAttachment) => {
  if (!canPreview(file.name)) return; // office/压缩包：交给原生 download 属性
  e.preventDefault();
  const win = window.open(file.url, '_blank', 'noopener');
  if (!win) window.location.href = file.url + (file.url.includes('?') ? '&' : '?') + 'download=1';
};
</script>

<style scoped>
.file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.fl-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 260px;
  padding: 5px 9px;
  border-radius: 8px;
  background: #f2f5fa;
  color: #3b4a6b;
  font-size: 12px;
  text-decoration: none;
}
.fl-item:hover {
  background: #e8eef9;
}
.fl-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fl-size {
  color: #8a94ad;
  flex-shrink: 0;
}
</style>
