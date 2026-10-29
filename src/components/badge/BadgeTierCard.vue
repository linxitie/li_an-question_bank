<template>
  <section class="tc">
    <BadgeIcon shape="rosette" :tier="tierIndex" :size="96" />

    <div class="tc-main">
      <div class="tc-title-row">
        <h2 class="tc-title">当前档位：{{ tierLabel }}</h2>
        <span v-if="maxed" class="tc-maxed">钻石档不封顶</span>
      </div>

      <p class="tc-sub">
        累计积分 <b>{{ score }}</b>
        <template v-if="maxed"> · 已达最高档，积分继续累积（用于星级与排名）</template>
        <template v-else> · 距下一档还差 <b>{{ need }}</b> 分</template>
      </p>

      <!-- 进度条 + 五档刻度 -->
      <div class="tc-bar-wrap">
        <div class="tc-bar">
          <div class="tc-bar-fill" :style="{ width: `${percent}%`, background: gradient }" />
        </div>
        <div class="tc-ticks">
          <span
            v-for="(t, i) in ticks"
            :key="t.threshold"
            class="tc-tick"
            :class="{ 'is-reached': score >= t.threshold }"
            :style="{ left: `${t.pos}%` }"
          >
            <i />
            <em>{{ t.threshold }}</em>
          </span>
        </div>
      </div>

      <p class="tc-legend">
        已获得 <b>{{ owned }}</b> / {{ total }} 枚
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import BadgeIcon from './BadgeIcon.vue';
import { BADGE_TIERS, tierByIndex } from './badgePalette';
import { tierPercent } from '@/views/student/badgesLogic';

const props = withDefaults(
  defineProps<{
    score?: number;
    tierIndex?: number;
    owned?: number;
    total?: number;
  }>(),
  { score: 0, tierIndex: 0, owned: 0, total: 0 }
);

const tier = computed(() => tierByIndex(props.tierIndex));
const tierLabel = computed(() => tier.value.label);
const next = computed(() => BADGE_TIERS[props.tierIndex + 1] || null);
const maxed = computed(() => !next.value);
const need = computed(() =>
  maxed.value ? 0 : Math.max(0, (next.value as { threshold: number }).threshold - props.score)
);
const percent = computed(() =>
  tierPercent(props.score, tier.value.threshold, next.value ? next.value.threshold : null)
);
const gradient = computed(
  () => `linear-gradient(90deg, ${tier.value.outer[0]}, ${tier.value.outer[1]})`
);

/** 五档刻度位置（按总分 800 归一；钻石档 100%） */
const ticks = computed(() =>
  BADGE_TIERS.map((t) => ({ threshold: t.threshold, pos: (t.threshold / 800) * 100 }))
);
</script>

<style scoped>
.tc {
  display: flex;
  gap: 20px;
  align-items: center;
  padding: 20px 24px;
  background: #fff;
  border: 1px solid #e6ecf5;
  border-radius: 18px;
}
.tc-main {
  flex: 1;
  min-width: 0;
}
.tc-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.tc-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #16233b;
}
.tc-maxed {
  font-size: 12px;
  font-weight: 700;
  color: #7a5af8;
}
.tc-sub {
  margin: 6px 0 14px;
  font-size: 13px;
  color: #5c6b80;
}
.tc-sub b {
  color: #16233b;
}
.tc-bar-wrap {
  position: relative;
  padding-bottom: 6px;
}
.tc-bar {
  height: 12px;
  border-radius: 6px;
  background: #eef2f9;
  overflow: hidden;
}
.tc-bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.4s ease;
}
.tc-ticks {
  position: relative;
  height: 20px;
  margin-top: 2px;
}
.tc-tick {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  text-align: center;
}
.tc-tick i {
  display: block;
  width: 1px;
  height: 6px;
  background: #d7e0ee;
  margin: 0 auto;
}
.tc-tick.is-reached i {
  background: #b9c6db;
}
.tc-tick em {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  font-style: normal;
  color: #94a3b8;
}
.tc-legend {
  margin: 8px 0 0;
  font-size: 12px;
  color: #8493a8;
}
</style>
