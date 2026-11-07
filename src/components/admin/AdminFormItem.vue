<template>
  <div class="adm-fi" :class="{ 'has-error': !!error }">
    <label class="adm-fi__label">
      {{ label }}
      <span v-if="required" class="adm-fi__req" aria-hidden="true">*</span>
    </label>
    <div class="adm-fi__ctl"><slot /></div>
    <p v-if="error" class="adm-fi__error">{{ error }}</p>
    <p v-else-if="hint" class="adm-fi__hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
/**
 * 表单行（A0）：label + 控件插槽 + 提示/错误。
 *
 * 现网问题：profile / settings / backup 的 label 宽度、必填星号、错误提示样式各不相同；
 * 有的必填星号是红色 `*`，有的写"（必填）"。统一为：星号 + 统一 12px 提示灰 + 错误红。
 *
 * 注意：与 D32「元数据全字段非必填」不冲突——`required` 只影响星号显示，不做校验拦截。
 */
withDefaults(
  defineProps<{
    label: string;
    required?: boolean;
    hint?: string;
    error?: string;
  }>(),
  { required: false, hint: '', error: '' }
);
</script>

<style scoped>
.adm-fi { font-family: var(--adm-font); margin-bottom: var(--adm-s3); }
.adm-fi__label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--adm-text-mid);
}
.adm-fi__req { color: var(--adm-danger); margin-left: 3px; }
.adm-fi__ctl { display: flex; align-items: center; gap: var(--adm-s1); }
.adm-fi__hint { margin-top: 5px; font-size: 11.5px; color: var(--adm-text-weak); line-height: 1.5; }
.adm-fi__error { margin-top: 5px; font-size: 11.5px; color: var(--adm-danger); line-height: 1.5; }
.adm-fi.has-error :deep(.adm-input),
.adm-fi.has-error :deep(.adm-select) { border-color: var(--adm-danger); }
</style>
