<template>
  <div class="adm-ph">
    <div class="adm-ph__text">
      <h2 class="adm-ph__title">{{ title }}</h2>
      <p v-if="desc || $slots.desc" class="adm-ph__desc">
        <slot name="desc">{{ desc }}</slot>
      </p>
    </div>
    <div v-if="$slots.actions" class="adm-ph__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 页头（A0）：标题 + 说明 + 右侧操作。
 *
 * 现网问题：顶栏面包屑已写"系统总览"，页面里又写一遍「📊 系统总览」（标题重复）；
 * 操作按钮位置每页不同（dashboard 右上、materials 在筛选条里）。
 * 统一后：**页面内只放一个标题**，面包屑由 `AdminLayout` 负责。
 */
defineProps<{ title: string; desc?: string }>();
</script>

<style scoped>
.adm-ph {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--adm-s3);
  margin-bottom: var(--adm-s3);
  font-family: var(--adm-font);
}
.adm-ph__title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.2px;
  color: var(--adm-text);
  line-height: 1.3;
}
.adm-ph__desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--adm-text-weak);
  line-height: 1.5;
}
.adm-ph__actions {
  display: flex;
  align-items: center;
  gap: var(--adm-s1);
  flex: none;
}
</style>
