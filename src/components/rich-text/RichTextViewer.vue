<script setup lang="ts">
import { computed } from 'vue';
// @ts-ignore TS7016: richText.js 为纯 JS 模块，按任务要求不额外提交 .d.ts
import { sanitizeRichText } from '@/utils/richText';

const props = withDefaults(
  defineProps<{
    content?: string;
  }>(),
  {
    content: ''
  }
);

/** 统一走 richText 清洗：安全链接 + 图片懒加载 + XSS 白名单 */
const html = computed(() => sanitizeRichText(props.content || ''));
</script>

<template>
  <div class="rich-text-viewer" v-html="html"></div>
</template>

<style scoped>
.rich-text-viewer {
  line-height: 1.7;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.rich-text-viewer :deep(img) {
  max-width: 100%;
  height: auto;
}

.rich-text-viewer :deep(a) {
  color: #1a73e8;
  text-decoration: underline;
  cursor: pointer;
}

.rich-text-viewer :deep(table) {
  max-width: 100%;
  border-collapse: collapse;
}

.rich-text-viewer :deep(td),
.rich-text-viewer :deep(th) {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
}

.rich-text-viewer :deep(pre) {
  overflow-x: auto;
}
</style>
