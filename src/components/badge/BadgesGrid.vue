<template>
  <div class="bg-wrap">
    <div v-if="!items.length" class="bg-empty">没有符合筛选条件的徽章</div>

    <ul v-else class="bg-grid">
      <li v-for="it in items" :key="`${it.kind}-${it.id}`" class="bg-card" :class="{ 'is-locked': !it.owned, 'is-pinned': it.pinned }" @click="$emit('select', it)">
        <!-- 精选：左上角金色五角星（T2 设为精选后的可视反馈） -->
        <span v-if="it.pinned" class="bg-pin-star"><PinStar :size="20" /></span>

        <BadgeIcon
          :shape="(it.shape as BadgeShape) || 'shield'"
          :tier="tierIndexOf(it)"
          :size="88"
          :locked="!it.owned"
          :label="`${it.name}（${it.owned ? '已获得' : '未获得'}）`"
        />

        <span class="bg-name">{{ it.name }}</span>
        <span class="bg-meta">{{ it.category }} · {{ tierLabelOf(it) }}</span>

        <!-- 稀有度：只做文字（灰色小字），不参与颜色 -->
        <span v-if="it.owned && it.rarity_text" class="bg-rarity">{{ it.rarity_text }}</span>
        <span v-if="it.is_first_owner" class="bg-first">全服首个获得</span>
        <span v-if="it.owned && it.snapshot_estimated" class="bg-est">档位（估算）</span>

        <span class="bg-state" :class="stateClass(it)">
          {{ stateText(it) }}
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import BadgeIcon from './BadgeIcon.vue';
import PinStar from './PinStar.vue';
import { type BadgeShape, tierByScore } from './badgePalette';
import type { BadgeItem } from '@/views/student/badgesLogic';

defineEmits<{ (e: 'select', item: BadgeItem): void }>();

const props = withDefaults(
  defineProps<{
    items?: BadgeItem[];
    /** 用户当前档位索引（未获得/无快照时用） */
    currentTierIndex?: number;
  }>(),
  { items: () => [], currentTierIndex: 0 }
);

/** 徽章档位：优先"获得时快照"的中文，其次用当前档位 */
const tierLabelOf = (it: BadgeItem): string => it.badge_tier || it.current_tier || tierByScore(0).label;

/** BadgeIcon 需要索引：由中文反查，找不到就用当前档位 */
const LABEL_TO_INDEX: Record<string, number> = { 黑铁: 0, 青铜: 1, 白银: 2, 黄金: 3, 钻石: 4 };
const tierIndexOf = (it: BadgeItem): number => {
  const label = tierLabelOf(it);
  return LABEL_TO_INDEX[label] ?? props.currentTierIndex;
};

const stateText = (it: BadgeItem): string => {
  if (it.owned) return it.obtained_at ? `已获得 · ${it.obtained_at.slice(0, 10)}` : '已获得';
  return it.threshold ? `进行中 · 目标 ${it.threshold}` : '未解锁';
};

const stateClass = (it: BadgeItem): string => (it.owned ? 'is-owned' : 'is-todo');
</script>

<style scoped>
.bg-wrap {
  min-height: 120px;
}
.bg-empty {
  padding: 56px 0;
  text-align: center;
  color: #94a3b8;
  background: #fff;
  border: 1px dashed #e3e9f3;
  border-radius: 16px;
}
.bg-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.bg-card {
  cursor: pointer;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 18px 12px 14px;
  background: #fff;
  border: 1px solid #e6ecf5;
  border-radius: 16px;
  transition: border-color 0.2s ease, transform 0.2s ease;
}
.bg-card:hover {
  border-color: #c9d6ea;
  transform: translateY(-2px);
}
.bg-card.is-locked {
  background: #fafbfe;
  border-color: #eef2f9;
}
.bg-name {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 700;
  color: #16233b;
  text-align: center;
}
.bg-card.is-locked .bg-name {
  color: #7d8ba0;
}
.bg-meta {
  font-size: 11px;
  color: #8493a8;
}
.bg-state {
  margin-top: 2px;
  font-size: 11px;
  font-weight: 600;
}
.bg-state.is-owned {
  color: #12a150;
}
.bg-state.is-todo {
  color: #94a3b8;
}
@media (max-width: 1280px) {
  .bg-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
@media (max-width: 900px) {
  .bg-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
/* 手机端：3 列的最小内容宽（图标 88 + 卡片内边距）会撑破 390px 视口（实测溢出 13px，右侧被裁），
   这里收紧内边距与列间距，让三列真正装得下。 */
@media (max-width: 600px) {
  .bg-grid {
    gap: 8px;
  }
  .bg-card {
    padding: 12px 6px 10px;
  }
  .bg-name {
    font-size: 13px;
  }
  .bg-meta,
  .bg-rarity {
    font-size: 10px;
    text-align: center;
  }
  .bg-first,
  .bg-est {
    font-size: 9.5px;
    padding: 0 3px;
  }
  .bg-state {
    font-size: 10px;
    text-align: center;
  }
}

.bg-rarity {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}
.bg-first {
  font-size: 10.5px;
  color: #64748b;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 5px;
  margin-top: 3px;
}
/* 精选星标：卡片左上角留白处，不占文字流 */
.bg-pin-star {
  position: absolute;
  top: 8px;
  left: 8px;
  line-height: 0;
  pointer-events: none;
}
.bg-card.is-pinned {
  border-color: #f2d9a6;
}
.bg-card.is-pinned:hover {
  border-color: #e6bf76;
}
.bg-est {
  font-size: 10.5px;
  color: #94a3b8;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  padding: 0 5px;
  margin-top: 3px;
}
</style>
