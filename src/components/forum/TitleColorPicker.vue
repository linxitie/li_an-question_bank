<template>
  <div class="title-color-picker">
    <button
      v-for="color in TITLE_COLORS"
      :key="color.key"
      type="button"
      :class="['tcp-dot', { active: modelValue === color.key }]"
      :style="{ background: color.value }"
      :title="color.name"
      @click="emit('update:modelValue', color.key)"
    />
    <span class="tcp-label">{{ currentName }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import { TITLE_COLORS, normalizeTitleColor } from './titleColors';

const props = defineProps<{ modelValue?: string }>();
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>();

const currentName = computed(() => {
  const key = normalizeTitleColor(props.modelValue);
  return TITLE_COLORS.find((item) => item.key === key)?.name || '默认';
});
</script>

<style scoped>
.title-color-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tcp-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px #d7dee9;
  cursor: pointer;
  padding: 0;
}
.tcp-dot.active {
  box-shadow: 0 0 0 2px #1a2b5f;
}
.tcp-label {
  font-size: 12px;
  color: #6b7896;
  margin-left: 2px;
}
</style>
