<template>
  <div class="file-uploader">
    <div v-for="(att, index) in modelValue" :key="att.url" class="fu-item">
      <img v-if="isImageUrl(att.url)" :src="att.url" :alt="att.name" class="fu-thumb" />
      <span v-else class="fu-doc">{{ fileIcon(att.name) }} {{ att.name }}</span>
      <button type="button" class="fu-remove" title="移除" @click="remove(index)">×</button>
    </div>

    <label class="fu-add" :class="{ 'is-disabled': disabled || uploading }">
      <input
        type="file"
        :accept="accept"
        multiple
        :disabled="disabled || uploading"
        @change="onChange"
      />
      <span v-if="!uploading">+ 图片 / 文件</span>
      <span v-else>上传中…</span>
    </label>

    <p v-if="error" class="fu-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import { isImageUrl, MAX_IMAGE_SIZE, uploadForumImage, type ForumImageAttachment } from './imageUtils';
import { isDocFile, isImageFile, MAX_DOC_SIZE, fileIcon, uploadForumFile } from './fileUtils';

const props = withDefaults(
  defineProps<{
    modelValue: ForumImageAttachment[];
    maxDocs?: number;
    disabled?: boolean;
  }>(),
  { maxDocs: 0, disabled: false }
);

const emit = defineEmits<{
  (event: 'update:modelValue', value: ForumImageAttachment[]): void;
}>();

const uploading = ref(false);
const error = ref('');

const accept = computed(() =>
  [
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.zip', '.rar', '.7z'
  ].join(',')
);

const remove = (index: number) => {
  const next = [...props.modelValue];
  next.splice(index, 1);
  emit('update:modelValue', next);
};

const onChange = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = '';
  if (!files.length) return;

  error.value = '';
  if (props.maxDocs > 0) {
    const docCount = props.modelValue.filter((a) => !isImageUrl(a.url)).length;
    const incomingDocs = files.filter((f) => isDocFile(f.name)).length;
    if (docCount + incomingDocs > props.maxDocs) {
      error.value = `文档最多 ${props.maxDocs} 个`;
      return;
    }
  }
  for (const file of files) {
    if (isImageFile(file.name) && file.size > MAX_IMAGE_SIZE) {
      error.value = `${file.name} 超过 5MB`;
      return;
    }
    if (isDocFile(file.name) && file.size > MAX_DOC_SIZE) {
      error.value = `${file.name} 超过 20MB`;
      return;
    }
    if (!isImageFile(file.name) && !isDocFile(file.name)) {
      error.value = `${file.name} 格式不支持`;
      return;
    }
  }

  uploading.value = true;
  try {
    const uploaded: ForumImageAttachment[] = [];
    for (const file of files) {
      uploaded.push(
        isImageFile(file.name)
          ? await uploadForumImage(file)
          : await uploadForumFile(file)
      );
    }
    emit('update:modelValue', [...props.modelValue, ...uploaded]);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || '上传失败';
  } finally {
    uploading.value = false;
  }
};
</script>

<style scoped>
.file-uploader {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.fu-item {
  position: relative;
  border-radius: 10px;
  background: #f2f5fa;
  overflow: hidden;
}
.fu-thumb {
  width: 76px;
  height: 76px;
  object-fit: cover;
  display: block;
}
.fu-doc {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 180px;
  padding: 8px 10px;
  font-size: 12px;
  color: #3b4a6b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fu-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  cursor: pointer;
  line-height: 1;
}
.fu-add {
  width: 76px;
  height: 76px;
  border: 1px dashed #c9d3e4;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7896;
  font-size: 12px;
  text-align: center;
  cursor: pointer;
  background: #f8fafd;
}
.fu-add.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.fu-add input {
  display: none;
}
.fu-error {
  width: 100%;
  margin: 0;
  color: #c41e3a;
  font-size: 12px;
}
</style>
