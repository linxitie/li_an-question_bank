<template>
  <!-- 富文本（contentFormat=HTML）：后端已 bleach 消毒，这里再兜一层前端校验后渲染 -->
  <div v-if="isHtml" class="forum-content forum-content-html" v-html="safeHtml"></div>

  <!-- 纯文本 / 历史数据：保持原有分段渲染（表情包 + 行内标记），行为不变 -->
  <span v-else-if="looksLikeHtmlDoc" class="forum-content">{{ plainSafeText }}</span>
  <span v-else class="forum-content">
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

const props = withDefaults(
  defineProps<{
    content: string;
    /** TEXT：纯文本 + [[sticker:]] + 行内标记；HTML：富文本（2026-11-03） */
    format?: string;
  }>(),
  { format: 'TEXT' }
);

const isHtml = computed(() => props.format === 'HTML');

/**
 * format=TEXT 但内容其实是 HTML 的历史脏数据兜底（2026-11-04 v5）。
 *
 * 背景：早期帖子正文里有 `<h1><span style="font-size:14px">` 这类标签，但
 * `content_format` 落的是 TEXT，按纯文本渲染就会把标签原样显示成字面量。
 * 这里**只转义、不渲染**：既不显示标签，也不会执行未知 HTML。
 */
const looksLikeHtmlDoc = computed(() =>
  /^\s*<(p|div|h[1-6]|span|font|table|ul|ol|blockquote|br)\b/i.test(String(props.content || ''))
);
const plainSafeText = computed(() =>
  String(props.content || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')
);

/**
 * 渲染前的最后一道防线。
 *
 * 真正的消毒在后端 `sanitize_rich_text`（bleach 白名单 + 受限 style 值校验）已经做过；
 * 这里再拦一次「明显的危险构造」，防止某条历史/异常数据绕过写路径直接进库后被渲染执行。
 * 命中危险构造时**整段降级为纯文本**，而不是试图修补 HTML —— 修补容易漏。
 */
const safeHtml = computed(() => {
  const html = String(props.content || '');
  if (!html) return '';
  const dangerous =
    /<\s*script\b/i.test(html) ||
    /<\s*style\b/i.test(html) ||
    /<\s*iframe\b/i.test(html) ||
    /\son[a-z]+\s*=/i.test(html) ||
    /javascript\s*:/i.test(html);
  if (dangerous) {
    // 降级：把尖括号转义成可见文本，绝不会被当成标签执行
    return html.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  return html;
});

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
 * 未闭合的标记原样输出，不会「吃掉」正文。
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
/* 富文本正文：块级排版，回收段落默认外边距避免行距过大 */
.forum-content-html {
  white-space: normal;
  display: block;
  line-height: 1.75;
}
.forum-content-html :deep(p) {
  margin: 0 0 0.5em;
}
.forum-content-html :deep(p:last-child) {
  margin-bottom: 0;
}
.forum-content-html :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
}
/* 表情包内嵌在 HTML 正文里时的尺寸（v5：移动端发帖改为富文本后使用） */
.forum-content-html :deep(img.forum-sticker) {
  display: inline-block;
  width: 96px;
  height: 96px;
  object-fit: contain;
  vertical-align: middle;
  margin: 2px 4px;
}
.forum-content-html :deep(table) {
  width: 100%;
  border-collapse: collapse;
}
.forum-content-html :deep(th),
.forum-content-html :deep(td) {
  border: 1px solid #e6ebf3;
  padding: 6px 8px;
}
.forum-content-html :deep(blockquote) {
  margin: 0.5em 0;
  padding: 6px 12px;
  border-left: 3px solid #c9d6e4;
  color: #5b6b84;
  background: #f8fafd;
}
</style>
