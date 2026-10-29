<template>
  <svg
    class="badge-icon"
    :class="[`shape-${shape}`, { 'is-locked': locked }]"
    :width="size"
    :height="size"
    viewBox="0 0 100 100"
    role="img"
    :aria-label="ariaLabel"
  >
    <defs>
      <!-- 外轮廓渐变（135°） -->
      <linearGradient :id="`${uid}-outer`" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" :stop-color="tier.outer[0]" />
        <stop offset="100%" :stop-color="tier.outer[1]" />
      </linearGradient>
      <!-- 内芯渐变（45°） -->
      <linearGradient :id="`${uid}-inner`" x1="0%" y1="100%" x2="100%" y2="0%">
        <stop offset="0%" :stop-color="tier.inner[0]" />
        <stop offset="100%" :stop-color="tier.inner[1]" />
      </linearGradient>
      <!-- 钻石：径向光晕 -->
      <radialGradient :id="`${uid}-glow`" cx="50%" cy="50%" r="50%">
        <stop offset="55%" stop-color="#8be9ff" stop-opacity="0.55" />
        <stop offset="100%" stop-color="#8be9ff" stop-opacity="0" />
      </radialGradient>
      <!-- 奖章中心径向 -->
      <radialGradient :id="`${uid}-core`" cx="50%" cy="42%" r="60%">
        <stop offset="0%" :stop-color="tier.inner[1]" />
        <stop offset="100%" :stop-color="tier.inner[0]" />
      </radialGradient>
    </defs>

    <!-- 钻石光晕 -->
    <circle v-if="tier.special && !locked" cx="50" cy="50" r="46" :fill="`url(#${uid}-glow)`" />

    <!-- 盾牌 -->
    <g v-if="shape === 'shield'">
      <path :d="SHIELD_OUTER" :fill="`url(#${uid}-outer)`" />
      <path :d="SHIELD_INNER" :fill="`url(#${uid}-inner)`" />
      <line x1="50" y1="19" x2="50" y2="82" :stroke="tier.outer[0]" stroke-width="1.2" opacity="0.7" />
    </g>

    <!-- 缎带 -->
    <g v-else-if="shape === 'ribbon'">
      <path :d="RIBBON_TAIL_L" :fill="`url(#${uid}-outer)`" />
      <path :d="RIBBON_TAIL_R" :fill="`url(#${uid}-outer)`" />
      <rect x="16" y="12" width="68" height="42" rx="9" :fill="`url(#${uid}-outer)`" />
      <rect x="25" y="21" width="50" height="24" rx="6" :fill="`url(#${uid}-inner)`" />
    </g>

    <!-- 科目奖章（锯齿圆 + 内圆 + 中心圆） -->
    <g v-else-if="shape === 'rosette'">
      <path :d="ROSETTE_OUTER" :fill="`url(#${uid}-outer)`" />
      <circle cx="50" cy="50" r="27" :fill="`url(#${uid}-inner)`" />
      <circle cx="50" cy="50" r="15" :fill="`url(#${uid}-core)`" />
    </g>

    <!-- 稀有宝石（六边形 + 内六边形 + 十字） -->
    <g v-else>
      <path :d="GEM_OUTER" :fill="`url(#${uid}-outer)`" />
      <path :d="GEM_INNER" :fill="`url(#${uid}-inner)`" />
      <line x1="50" y1="17" x2="50" y2="83" :stroke="tier.outer[0]" stroke-width="1.1" opacity="0.65" />
      <line x1="19" y1="50" x2="81" y2="50" :stroke="tier.outer[0]" stroke-width="1.1" opacity="0.65" />
    </g>

    <!-- 钻石星芒 -->
    <g v-if="tier.special && !locked" stroke="#dff8ff" stroke-width="2.2" stroke-linecap="round">
      <line x1="78" y1="22" x2="88" y2="12" />
      <line x1="22" y1="22" x2="12" y2="12" />
      <line x1="78" y1="78" x2="88" y2="88" />
      <line x1="22" y1="78" x2="12" y2="88" />
    </g>

    <!-- 锁定：遮罩 + 锁形 -->
    <g v-if="locked" class="badge-lock">
      <path :d="SHIELD_OUTER" fill="rgba(244,246,251,0.62)" />
      <rect x="43" y="47" width="14" height="12" rx="3" fill="none" stroke="#94a3b8" stroke-width="2" />
      <path d="M46 47 v-4 a4 4 0 0 1 8 0 v4" fill="none" stroke="#94a3b8" stroke-width="2" />
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import {
  SHAPE_LABELS,
  tierByIndex,
  nextBadgeUid,
  type BadgeShape
} from './badgePalette';

const props = withDefaults(
  defineProps<{
    shape?: BadgeShape;
    /** 档位索引 0–4 */
    tier?: number;
    /** 像素尺寸（正方形） */
    size?: number;
    /** 未获得/未解锁 */
    locked?: boolean;
    /** 无障碍标签；缺省按形状+档位生成 */
    label?: string;
  }>(),
  { shape: 'shield', tier: 0, size: 72, locked: false, label: '' }
);

const uid = nextBadgeUid('badge');
const tier = computed(() => tierByIndex(props.tier));
const ariaLabel = computed(
  () => props.label || `${SHAPE_LABELS[props.shape]}徽章 · ${tier.value.label}${props.locked ? '（未获得）' : ''}`
);

// 几何路径（100×100 视口）
const SHIELD_OUTER = 'M50 6 L88 19 V50 C88 72 70 86 50 94 C30 86 12 72 12 50 V19 Z';
const SHIELD_INNER = 'M50 18 L77 27 V50 C77 66 64 77 50 83 C36 77 23 66 23 50 V27 Z';
const RIBBON_TAIL_L = 'M34 50 L20 92 L38 84 L46 94 Z';
const RIBBON_TAIL_R = 'M66 50 L80 92 L62 84 L54 94 Z';
const GEM_OUTER = 'M50 6 L86 29 V71 L50 94 L14 71 V29 Z';
const GEM_INNER = 'M50 20 L75 34 V66 L50 80 L25 66 V34 Z';

/** 16 齿花环外轮廓 */
const ROSETTE_OUTER = (() => {
  const n = 16;
  const pts: string[] = [];
  for (let i = 0; i < n * 2; i += 1) {
    const ang = (Math.PI * i) / n - Math.PI / 2;
    const r = i % 2 === 0 ? 46 : 38;
    pts.push(`${(50 + r * Math.cos(ang)).toFixed(2)} ${(50 + r * Math.sin(ang)).toFixed(2)}`);
  }
  return `M${pts.join(' L')} Z`;
})();
</script>

<style scoped>
.badge-icon {
  display: block;
  flex: 0 0 auto;
  overflow: visible;
}
.badge-icon.is-locked {
  filter: grayscale(0.92);
  opacity: 0.62;
}
.badge-icon:not(.is-locked) {
  filter: drop-shadow(0 2px 6px rgba(22, 35, 59, 0.12));
}
</style>
