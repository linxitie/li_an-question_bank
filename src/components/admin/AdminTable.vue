<template>
  <section class="adm-table" :class="{ 'is-dense': dense }">
    <header v-if="title || $slots.head" class="adm-table__head">
      <h3 v-if="title" class="adm-table__title">{{ title }}</h3>
      <div class="adm-table__extra"><slot name="head" /></div>
    </header>

    <div class="adm-table__body">
      <!-- 页面自己写 <table>，组件只负责"壳"与统一表头/行高/空态样式。
           这样现网各页的表格可以整体包进来，不必重写列定义。 -->
      <slot />
      <div v-if="empty" class="adm-empty">{{ emptyText }}</div>
    </div>

    <footer v-if="$slots.footer" class="adm-table__foot"><slot name="footer" /></footer>
  </section>
</template>

<script setup lang="ts">
/**
 * 表格壳（A0）：统一表头底色/字号、行分隔线、行高、空状态、分页位置。
 *
 * 为什么用"壳 + 默认插槽"而不是"传 columns/rows"：
 * 现网各页表格列结构差异大（含操作列、徽标、行内开关），改造成本最低的做法是
 * **页面保留自己的 `<table>`，外面包一层 `<AdminTable>`**，样式由 `:deep()` 统一。
 * 空态由 `empty` 控制，避免每页自己写"暂无数据"。
 */
withDefaults(
  defineProps<{
    title?: string;
    dense?: boolean;
    empty?: boolean;
    emptyText?: string;
  }>(),
  { title: '', dense: false, empty: false, emptyText: '暂无数据' }
);
</script>

<style scoped>
.adm-table {
  background: var(--adm-surface);
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-card);
  box-shadow: var(--adm-shadow-card);
  overflow: hidden;
  font-family: var(--adm-font);
}
.adm-table__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--adm-s3) var(--adm-s4);
  border-bottom: 1px solid var(--adm-line-soft);
}
.adm-table__title { font-size: 12.5px; font-weight: 700; color: var(--adm-text-mid); }
.adm-table__extra { display: flex; align-items: center; gap: var(--adm-s1); }
.adm-table__body { padding: 0 var(--adm-s4); }
.adm-table__foot {
  padding: var(--adm-s2) var(--adm-s4);
  border-top: 1px solid var(--adm-line-soft);
  display: flex;
  justify-content: flex-end;
}

/* —— 统一表格外观（作用于插槽里的 table）—— */
.adm-table__body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  color: var(--adm-text-mid);
}
.adm-table__body :deep(thead th) {
  background: var(--adm-head-bg);
  color: var(--adm-text-sub);
  font-size: 11.5px;
  font-weight: 600;
  text-align: left;
  padding: 9px 10px;
  border-bottom: 1px solid #e6eaf4;
  white-space: nowrap;
}
.adm-table__body :deep(tbody td) {
  padding: 11px 10px;
  border-bottom: 1px solid var(--adm-line-soft);
  vertical-align: middle;
}
.adm-table__body :deep(tbody tr:last-child td) { border-bottom: none; }
.adm-table__body :deep(tbody tr:hover td) { background: #fbfcff; }
.adm-table.is-dense :deep(tbody td) { padding: 7px 10px; }
</style>
