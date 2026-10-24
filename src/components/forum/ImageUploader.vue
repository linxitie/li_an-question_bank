<template>
  <div class="image-uploader">
    <div v-for="(image, index) in modelValue" :key="image.url" class="iu-item">
      <img :src="image.url" :alt="image.name || '图片'" />
      <button class="iu-remove" type="button" title="移除" @click="remove(index)">×</button>
    </div>

    <label class="iu-add" :class="{ 'is-disabled': disabled || uploading }">
      <input
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp"
        multiple
        :disabled="disabled || uploading"
        @change="onChange"
      />
      <span v-if="!uploading">+ 图片</span>
      <span v-else>上传中…</span>
    </label>

    <p v-if="error" class="iu-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

import {
  MAX_IMAGE_SIZE,
  uploadForumImage,
  type ForumImageAttachment
} from './imageUtils';

const props = withDefaults(
  defineProps<{
    modelValue: ForumImageAttachment[];
    max?: number;
    disabled?: boolean;
  }>(),
  { max: 0, disabled: false }
);

const emit = defineEmits<{
  (event: 'update:modelValue', value: ForumImageAttachment[]): void;
}>();

const uploading = ref(false);
const error = ref('');

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
  if (props.max > 0 && props.modelValue.length + files.length > props.max) {
    error.value = `最多还能上传 ${Math.max(0, props.max - props.modelValue.length)} 张`;
    return;
  }
  const oversize = files.find((file) => file.size > MAX_IMAGE_SIZE);
  if (oversize) {
    error.value = `${oversize.name} 超过 5MB`;
    return;
  }

  uploading.value = true;
  try {
    const uploaded: ForumImageAttachment[] = [];
    for (const file of files) {
      uploaded.push(await uploadForumImage(file));
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
.image-uploader {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.iu-item {
  position: relative;
  width: 76px;
  height: 76px;
  border-radius: 10px;
  overflow: hidden;
  background: #f2f5fa;
}
.iu-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.iu-remove {
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
.iu-add {
  width: 76px;
  height: 76px;
  border: 1px dashed #c9d3e4;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7896;
  font-size: 12px;
  cursor: pointer;
  background: #f8fafd;
}
.iu-add.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.iu-add input {
  display: none;
}
.iu-error {
  width: 100%;
  margin: 0;
  color: #c41e3a;
  font-size: 12px;
}
</style>
