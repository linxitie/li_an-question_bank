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

    <!-- 形状族：星（准确率） -->
    <g v-else-if="shape === 'star'">
      <path d="M50 6 L61 37 H94 L67 56 L77 88 L50 69 L23 88 L33 56 L6 37 H39 Z"
            :fill="`url(#${uid}-outer)`" />
      <path d="M50 22 L56 40 H75 L60 51 L66 70 L50 58 L34 70 L40 51 L25 40 H44 Z"
            :fill="`url(#${uid}-inner)`" opacity="0.55" />
    </g>

    <!-- 档位工艺层：青铜铆钉 / 白银双环 / 黄金放射 / 钻石棱镜碎面 -->
    <g v-if="!locked && tier.index === 1" fill="#5b2f12" opacity="0.5">
      <circle cx="28" cy="30" r="2.6" /><circle cx="72" cy="30" r="2.6" />
      <circle cx="28" cy="70" r="2.6" /><circle cx="72" cy="70" r="2.6" />
    </g>
    <path v-if="!locked && tier.index === 2" d="M18 62 C30 82 70 82 82 62"
          fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" opacity="0.55" />
    <g v-if="!locked && tier.index === 3">
      <rect v-for="i in 12" :key="`ray-${i}`" x="49" y="4" width="2" height="11"
            fill="#fff8d0" opacity="0.75" :transform="`rotate(${(i - 1) * 30} 50 50)`" />
    </g>
    <g v-if="!locked && tier.index === 4">
      <path d="M50 14 L66 38 L58 62 L42 62 L34 38 Z" fill="#ffffff" opacity="0.22" />
      <path d="M34 38 L42 62 L22 56 Z" fill="#67e8f9" opacity="0.28" />
      <path d="M66 38 L78 56 L58 62 Z" fill="#f0abfc" opacity="0.28" />
    </g>

    <!-- 未获得：灰阶花纹之上标注档位文字（黑铁–钻石） -->
    <text v-if="locked" x="50" y="99" text-anchor="middle"
          font-size="13" font-weight="600" fill="#6b7280">{{ tier.label }}</text>

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
  LOCKED_PAINT,
  SHAPE_LABELS,
  tierByIndex,
  nextBadgeUid,
  type BadgeShape
} from './badgePalette';

const props = withDefaults(
  defineProps<{
    shape?: BadgeShape | 'star';
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
const baseTier = computed(() => tierByIndex(props.tier));
/** 未获得：同形状同花纹，但整体换成更深灰阶（不是简单降透明度，花纹仍可见） */
const tier = computed(() =>
  props.locked
    ? { ...baseTier.value, outer: LOCKED_PAINT.outer, inner: LOCKED_PAINT.inner,
        text: LOCKED_PAINT.text, special: false }
    : baseTier.value
);
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
  filter: grayscale(0.15);
  opacity: 1;
}
.badge-icon:not(.is-locked) {
  filter: drop-shadow(0 2px 6px rgba(22, 35, 59, 0.12));
}
</style>
