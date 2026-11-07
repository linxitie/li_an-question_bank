<template>
  <div class="adm-tb">
    <div class="adm-tb__left"><slot /></div>
    <div v-if="$slots.actions" class="adm-tb__right"><slot name="actions" /></div>
  </div>
</template>

<script setup lang="ts">
/**
 * 筛选/操作条（A0）：左侧筛选项、右侧按钮组。
 *
 * 现网问题：`.bar`（materials）、`.member-filter-bar`（users）、`.af-toolbar`（forum）
 * 三种写法，高度/内边距/间距都不同。统一为一个横条 + 两端对齐。
 */
</script>

<style scoped>
.adm-tb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--adm-s2);
  padding: var(--adm-s2) var(--adm-s3);
  margin-bottom: var(--adm-s2);
  background: var(--adm-surface);
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-card);
  box-shadow: var(--adm-shadow-card);
  font-family: var(--adm-font);
}
.adm-tb__left,
.adm-tb__right {
  display: flex;
  align-items: center;
  gap: var(--adm-s1);
  flex-wrap: wrap;
}
.adm-tb__right { flex: none; }
</style>
