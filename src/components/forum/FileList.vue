<template>
  <div v-if="files.length" class="file-list">
    <a
      v-for="file in files"
      :key="file.url"
      class="fl-item"
      :href="file.url"
      :download="file.name"
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
