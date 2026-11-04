<template>
  <div v-if="files.length" class="file-list">
    <a
      v-for="file in files"
      :key="file.url"
      class="fl-item"
      href="javascript:void(0)"
      rel="noopener"
      @click="onDownload($event, file)"
    >
      <span class="fl-icon">{{ fileIcon(file.name) }}</span>
      <span class="fl-name">{{ file.name }}</span>
      <span class="fl-size">{{ formatFileSize(file.size) }}</span>
    </a>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { fileIcon, formatFileSize } from './fileUtils';
import type { ForumImageAttachment } from './imageUtils';

defineProps<{ files: ForumImageAttachment[] }>();

/**
 * 2026-10-30（用户决定）：点击附件直接用浏览器下载。
 *
 * 为什么用 fetch + blob 而不是 location.href：
 * - location.href 会把整个 SPA 导航到 /media/...，一旦代理/响应异常就表现为"页面刷新"；
 * - blob + <a download> 完全留在当前页，只触发下载，不会刷新页面。
 * 失败时退回直接导航，保证仍能拿到文件。
 */
const onDownload = async (e: MouseEvent, file: ForumImageAttachment) => {
  e.preventDefault();
  const sep = file.url.includes('?') ? '&' : '?';
  // 2026-10-31：/media 依赖 vite 代理，统一改走已代理的 /api/media
  const raw = file.url.startsWith('/media/')
    ? '/api/media/' + file.url.slice('/media/'.length)
    : file.url;
  // 2026-11-01：加时间戳 + no-store，绕开浏览器缓存。
  // 服务端对媒体返回 Cache-Control: immutable(1年)，之前代理异常时缓存进去的
  // index.html 会被长期复用，导致"服务端已修好、浏览器还下错文件"。
  const url = raw + sep + 'download=1' + '&_t=' + Date.now();
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    // 若拿到的是 HTML（代理未生效时 Vite 返回 index.html），直接判失败，
    // 避免把网页存成 .docx/.pdf 导致"打不开/正在加载资源"。
    const head = await blob.slice(0, 15).text();
    if (head.trimStart().startsWith('<')) {
      throw new Error('服务器返回了网页而不是文件（媒体代理未生效）');
    }
    // 大小校验：与记录不一致说明拿到的是错误内容（例如被缓存的旧响应）
    const expect = Number(file.size || 0);
    if (expect > 0 && blob.size !== expect) {
      throw new Error(`文件大小不符（期望 ${expect} 字节，实际 ${blob.size} 字节）`);
    }
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = file.name || 'download';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 4000);
  } catch (err: any) {
    ElMessage.error('下载失败：' + (err?.message || '未知错误'));
    window.location.href = raw + sep + 'download=1' + '&_t=' + Date.now();
  }
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
  cursor: pointer;
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
