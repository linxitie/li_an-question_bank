<template>
  <div v-if="item" class="dm-mask" @click.self="$emit('close')">
    <div class="dm-card" role="dialog" aria-modal="true">
      <button class="dm-close" aria-label="关闭" @click="$emit('close')">×</button>

      <div class="dm-hero">
        <BadgeIcon
          :shape="(item.shape as BadgeShape) || 'shield'"
          :tier="tierIndex"
          :size="140"
          :locked="!item.owned"
        />
        <div class="dm-hero-info">
          <h2 class="dm-name">{{ item.name }}</h2>
          <div class="dm-chips">
            <span class="dm-chip dm-chip-tier" :style="{ color: tier.text, background: tint }">
              {{ tierLabel }}
            </span>
            <span class="dm-chip">{{ item.category }}</span>
            <span v-if="item.kind === 'title'" class="dm-chip dm-chip-title">称号</span>
          </div>
          <p class="dm-cond">{{ item.condition_desc || '达成条件未记录' }}</p>
          <p v-if="item.owned && item.rarity_text" class="dm-rarity">
            {{ item.rarity_text }}<span v-if="item.is_first_owner" class="dm-first">全服首个获得</span>
          </p>
          <p class="dm-time" v-if="item.owned">获得于 {{ dateOnly(item.obtained_at) || '未记录' }}</p>
          <p class="dm-time dm-time-todo" v-else>尚未获得</p>
        </div>
        <!-- 精选：弹层右侧空白处的金色五角星（与徽章页卡片左上角同一图形） -->
        <div v-if="item.pinned" class="dm-pin-col">
          <PinStar :size="42" />
          <span class="dm-pin-text">精选</span>
        </div>
      </div>

      <div class="dm-rows">
        <div class="dm-row">
          <span>获得时档位</span>
          <b>
            {{ item.snapshot_tier || item.badge_tier || '未记录' }}
            <span v-if="item.snapshot_estimated" class="dm-est">（估算）</span>
          </b>
        </div>
        <div class="dm-row">
          <span>徽章成色</span>
          <b>{{ item.badge_tier || tierLabel }}</b>
        </div>
        <div class="dm-row">
          <span>奖励</span>
          <b>{{ item.reward_coins ? `${item.reward_coins} 金币` : '—' }}</b>
        </div>
        <div class="dm-row">
          <span>全站稀有度</span>
          <b>{{ rarity || '暂无统计' }}</b>
        </div>
      </div>

      <div class="dm-tip">
        提示：档位随累计积分实时提升；已获得的徽章不会因积分变化而降级。
      </div>

      <div class="dm-actions">
        <button
          v-if="item.owned && item.kind === 'achievement'"
          class="dm-btn dm-btn-pin"
          @click="$emit('toggle-pin', item)"
        >{{ item.pinned ? '取消精选' : '设为精选' }}</button>
        <button class="dm-btn" @click="$emit('close')">关闭</button>
        <button class="dm-btn dm-btn-primary" @click="onShare">复制徽章文案</button>
      </div>

      <p v-if="copied" class="dm-copied">已复制到剪贴板</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import BadgeIcon from './BadgeIcon.vue';
import PinStar from './PinStar.vue';
import { type BadgeShape, tierByIndex } from './badgePalette';
import { dateOnly, rarityText, type BadgeItem } from '@/views/student/badgesLogic';

const props = withDefaults(
  defineProps<{
    item?: BadgeItem | null;
    currentTierIndex?: number;
  }>(),
  { item: null, currentTierIndex: 0 }
);

defineEmits<{ (e: 'close'): void; (e: 'toggle-pin', item: BadgeItem): void }>();

const copied = ref(false);
const LABEL_TO_INDEX: Record<string, number> = { 黑铁: 0, 青铜: 1, 白银: 2, 黄金: 3, 钻石: 4 };

const tierLabel = computed(() => props.item?.badge_tier || props.item?.current_tier || '黑铁');
const tier = computed(() => tierByIndex(LABEL_TO_INDEX[tierLabel.value] ?? props.currentTierIndex));
const tierIndex = computed(() => LABEL_TO_INDEX[tierLabel.value] ?? props.currentTierIndex);
const rarity = computed(() =>
  rarityText(props.item?.owned_count as number | undefined, props.item?.owned_percent as number | undefined)
);
const tint = computed(() => `${tier.value.inner[1]}33`);

const onShare = async () => {
  const text = `我在砺安题库获得了「${props.item?.name || ''}」（${tierLabel.value}）徽章！`;
  try {
    await navigator.clipboard.writeText(text);
    copied.value = true;
    window.setTimeout(() => (copied.value = false), 2000);
  } catch {
    copied.value = false;
  }
};
</script>

<style scoped>
.dm-mask {
  position: fixed;
  inset: 0;
  z-index: 2200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 25, 40, 0.45);
}
.dm-card {
  position: relative;
  width: 560px;
  max-width: calc(100vw - 40px);
  max-height: 88vh;
  overflow-y: auto;
  padding: 24px;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 24px 60px rgba(16, 25, 40, 0.24);
}
.dm-close {
  position: absolute;
  top: 14px;
  right: 16px;
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #8493a8;
  cursor: pointer;
}
.dm-hero {
  display: flex;
  gap: 20px;
  align-items: center;
}
.dm-hero-info {
  flex: 1;
  min-width: 0;
}
/* 精选星标列：贴右缘、与标题区同高 */
.dm-pin-col {
  align-self: flex-start;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-top: 4px;
}
.dm-pin-text {
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  letter-spacing: 1px;
}
@media (max-width: 560px) {
  .dm-hero {
    gap: 12px;
    padding-right: 46px;
  }
  .dm-pin-col {
    position: absolute;
    top: 46px;
    right: 12px;
  }
}
.dm-name {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: #16233b;
}
.dm-chips {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.dm-chip {
  padding: 3px 10px;
  border-radius: 10px;
  background: #f1f3f7;
  color: #5c6b80;
  font-size: 12px;
  font-weight: 600;
}
.dm-chip-title {
  background: #eef3ff;
  color: #2563eb;
}
.dm-cond {
  margin: 0 0 6px;
  font-size: 13px;
  color: #5c6b80;
}
.dm-time {
  margin: 0;
  font-size: 12px;
  color: #8493a8;
}
.dm-time-todo {
  color: #94a3b8;
}
.dm-rows {
  margin: 18px 0 0;
  border-top: 1px solid #eef2f9;
}
.dm-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #f2f5fa;
  font-size: 13px;
  color: #5c6b80;
}
.dm-row b {
  color: #16233b;
}
.dm-tip {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f7f9fc;
  color: #8493a8;
  font-size: 12px;
}
.dm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}
.dm-btn {
  height: 36px;
  padding: 0 18px;
  border: 1px solid #e6ecf5;
  border-radius: 10px;
  background: #fff;
  color: #5c6b80;
  font-size: 13px;
  cursor: pointer;
}
.dm-btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
  font-weight: 600;
}
.dm-copied {
  margin: 10px 0 0;
  text-align: right;
  font-size: 12px;
  color: #12a150;
}

.dm-rarity {
  font-size: 12px;
  color: #94a3b8;
  margin: 4px 0 0;
}
.dm-first {
  margin-left: 8px;
  font-size: 11px;
  color: #475569;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 1px 6px;
}
.dm-est { font-size: 11px; color: #94a3b8; font-weight: 400; }
</style>
