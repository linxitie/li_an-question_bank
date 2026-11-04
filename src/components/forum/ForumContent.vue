<template>
  <span class="forum-content">
    <template v-for="(segment, index) in segments" :key="index">
      <img
        v-if="segment.url"
        :src="segment.url"
        class="forum-content-sticker"
        alt="表情包"
      />
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
}

const STICKER_PATTERN = /\[\[sticker:([^\]]+)\]\]/g;

const segments = computed<Segment[]>(() => {
  const text = props.content ?? '';
  const result: Segment[] = [];
  let cursor = 0;

  for (const match of text.matchAll(STICKER_PATTERN)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      result.push({ text: text.slice(cursor, index) });
    }
    result.push({ url: match[1] });
    cursor = index + match[0].length;
  }

  if (cursor < text.length) {
    result.push({ text: text.slice(cursor) });
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
