<template>
  <span class="forum-content">
    <template v-for="(segment, index) in segments" :key="index">
      <img
        v-if="segment.url"
        :src="segment.url"
        class="forum-content-sticker"
        alt="表情包"
      />
      <strong v-else-if="segment.bold">{{ segment.text }}</strong>
      <em v-else-if="segment.italic">{{ segment.text }}</em>
      <u v-else-if="segment.underline">{{ segment.text }}</u>
      <span v-else>{{ segment.text }}</span>
    </template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ content: string }>();

interface Segment {
  text?: string;
  url?: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
}

const STICKER_PATTERN = /\[\[sticker:([^\]]+)\]\]/g;

/**
 * 行内格式：**加粗**、*斜体*、__下划线__。
 *
 * 刻意不用 v-html：内容仍以文本节点渲染，避免把用户输入当 HTML 执行
 * （`test_create_post_keeps_xss_as_plain_text` 已明确要求 XSS 保持纯文本）。
 * 未闭合的标记原样输出，不会“吃掉”正文。
 */
const INLINE_PATTERN = /\*\*([^*]+?)\*\*|__([^_]+?)__|\*([^*\n]+?)\*/g;

function parseInline(text: string): Segment[] {
  const result: Segment[] = [];
  let cursor = 0;

  for (const match of text.matchAll(INLINE_PATTERN)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      result.push({ text: text.slice(cursor, index) });
    }
    if (match[1] !== undefined) result.push({ text: match[1], bold: true });
    else if (match[2] !== undefined) result.push({ text: match[2], underline: true });
    else if (match[3] !== undefined) result.push({ text: match[3], italic: true });
    cursor = index + match[0].length;
  }

  if (cursor < text.length) {
    result.push({ text: text.slice(cursor) });
  }
  return result;
}

const segments = computed<Segment[]>(() => {
  const text = props.content ?? '';
  const result: Segment[] = [];
  let cursor = 0;

  for (const match of text.matchAll(STICKER_PATTERN)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      result.push(...parseInline(text.slice(cursor, index)));
    }
    result.push({ url: match[1] });
    cursor = index + match[0].length;
  }

  if (cursor < text.length) {
    result.push(...parseInline(text.slice(cursor)));
  }
  return result;
});
</script>

<style scoped>
.forum-content {
  white-space: pre-wrap;
  word-break: break-word;
}
.forum-content-sticker {
  display: inline-block;
  width: 96px;
  height: 96px;
  object-fit: contain;
  vertical-align: middle;
  margin: 2px 4px;
}
</style>
