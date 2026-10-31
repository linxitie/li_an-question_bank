<template>
  <section class="dw">
    <header class="dw-head">
      <h2 class="dw-title">我的徽章</h2>
      <button class="dw-more" @click="$emit('viewAll')">查看全部 →</button>
    </header>

    <div v-if="!items.length" class="dw-empty">
      还没有获得徽章，去完成学习任务解锁第一枚吧
    </div>

    <ul v-else class="dw-list">
      <li v-for="it in items" :key="it.id" class="dw-item" @click="$emit('select', it)">
        <BadgeIcon
          :shape="(it.shape as BadgeShape) || 'shield'"
          :tier="tierIndexOf(it)"
          :size="64"
          :label="it.name"
        />
        <span class="dw-name">{{ it.name }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import BadgeIcon from './BadgeIcon.vue';
import { type BadgeShape } from './badgePalette';
import type { BadgeItem } from '@/views/student/badgesLogic';

const props = withDefaults(
  defineProps<{
    items?: BadgeItem[];
    currentTierIndex?: number;
  }>(),
  { items: () => [], currentTierIndex: 0 }
);

defineEmits<{ (e: 'select', item: BadgeItem): void; (e: 'viewAll'): void }>();

const LABEL_TO_INDEX: Record<string, number> = { 黑铁: 0, 青铜: 1, 白银: 2, 黄金: 3, 钻石: 4 };
const tierIndexOf = (it: BadgeItem): number => {
  const label = it.badge_tier || it.current_tier || '黑铁';
  return LABEL_TO_INDEX[label] ?? props.currentTierIndex;
};
</script>

<style scoped>
.dw {
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e6ecf5;
  border-radius: 16px;
}
.dw-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.dw-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #16233b;
}
.dw-more {
  border: none;
  background: none;
  color: #2563eb;
  font-size: 12px;
  cursor: pointer;
}
.dw-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}
.dw-list {
  display: flex;
  gap: 18px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.dw-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: transform 0.2s ease;
}
.dw-item:hover {
  transform: translateY(-2px);
}
.dw-name {
  font-size: 11px;
  color: #5c6b80;
  max-width: 72px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
