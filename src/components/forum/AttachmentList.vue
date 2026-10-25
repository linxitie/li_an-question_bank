<template>
  <div class="attachment-list">
    <ImageGrid v-if="images.length" :images="images" :mode="mode" />
    <FileList v-if="files.length" :files="files" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import FileList from './FileList.vue';
import ImageGrid from './ImageGrid.vue';
import { splitAttachments } from './fileUtils';
import type { ForumImageAttachment } from './imageUtils';

const props = withDefaults(
  defineProps<{
    attachments?: ForumImageAttachment[];
    mode?: 'post' | 'comment';
  }>(),
  { attachments: () => [], mode: 'post' }
);

const images = computed(() => splitAttachments(props.attachments).images);
const files = computed(() => splitAttachments(props.attachments).files);
</script>

<style scoped>
.attachment-list {
  display: contents;
}
</style>
