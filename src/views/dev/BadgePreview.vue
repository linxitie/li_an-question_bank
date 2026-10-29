<template>
  <div class="bp-page">
    <header class="bp-head">
      <h1>徽章图标组件预览（S3-a）</h1>
      <p>矢量 SVG：4 形状 × 5 档品质，全渐变；钻石档额外光晕与星芒；支持锁定态与任意尺寸。</p>
    </header>

    <!-- 档位阶梯 -->
    <section class="bp-card">
      <h2>① 五档品质阶梯</h2>
      <div class="bp-tiers">
        <div v-for="t in BADGE_TIERS" :key="t.code" class="bp-tier">
          <BadgeIcon shape="rosette" :tier="t.index" :size="72" />
          <span class="bp-tier-label">{{ t.label }}</span>
          <span class="bp-tier-th">{{ t.threshold }}</span>
        </div>
      </div>
    </section>

    <!-- 4 形状 × 5 档 -->
    <section class="bp-card">
      <h2>② 四类形状 × 五档品质</h2>
      <table class="bp-matrix">
        <thead>
          <tr>
            <th></th>
            <th v-for="t in BADGE_TIERS" :key="t.code">{{ t.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in SHAPES" :key="s">
            <th>{{ SHAPE_LABELS[s] }}</th>
            <td v-for="t in BADGE_TIERS" :key="t.code">
              <BadgeIcon :shape="s" :tier="t.index" :size="64" />
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 状态 -->
    <section class="bp-card">
      <h2>③ 三种状态（同一组件）</h2>
      <div class="bp-states">
        <figure>
          <BadgeIcon shape="shield" :tier="3" :size="72" />
          <figcaption>已获得</figcaption>
        </figure>
        <figure>
          <BadgeIcon shape="shield" :tier="4" :size="72" locked />
          <figcaption>未解锁（灰度 + 锁形）</figcaption>
        </figure>
        <figure>
          <BadgeIcon shape="ribbon" :tier="2" :size="72" />
          <figcaption>称号（缎带）</figcaption>
        </figure>
        <figure>
          <BadgeIcon shape="gem" :tier="4" :size="72" />
          <figcaption>稀有（宝石 · 钻石）</figcaption>
        </figure>
      </div>
    </section>

    <!-- 尺寸 -->
    <section class="bp-card">
      <h2>④ 尺寸适配（16 / 24 / 40 / 72 / 120）</h2>
      <div class="bp-sizes">
        <BadgeIcon shape="shield" :tier="3" :size="16" />
        <BadgeIcon shape="shield" :tier="3" :size="24" />
        <BadgeIcon shape="shield" :tier="3" :size="40" />
        <BadgeIcon shape="shield" :tier="3" :size="72" />
        <BadgeIcon shape="shield" :tier="3" :size="120" />
      </div>
    </section>

    <!-- 档位换算 -->
    <section class="bp-card">
      <h2>⑤ 积分 → 档位（与后端同口径）</h2>
      <div class="bp-calc">
        <div v-for="s in SAMPLE_SCORES" :key="s" class="bp-calc-item">
          <BadgeIcon shape="shield" :tier="tierByScore(s).index" :size="40" />
          <div>
            <b>{{ s }} 分 → {{ tierByScore(s).label }}</b>
            <span v-if="needToNext(s).maxed">已满档（积分继续累积）</span>
            <span v-else>还差 {{ needToNext(s).need }} 分到下一档 · {{ needToNext(s).percent }}%</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import BadgeIcon from '@/components/badge/BadgeIcon.vue';
import {
  BADGE_TIERS,
  SHAPE_LABELS,
  needToNext,
  tierByScore,
  type BadgeShape
} from '@/components/badge/badgePalette';

const SHAPES: BadgeShape[] = ['shield', 'ribbon', 'rosette', 'gem'];
const SAMPLE_SCORES = [0, 199, 200, 700, 780, 800, 1200];
</script>

<style scoped>
.bp-page {
  min-height: 100vh;
  padding: 24px 32px 48px;
  background: #f4f6fb;
  color: #16233b;
}
.bp-head h1 {
  margin: 0 0 6px;
  font-size: 22px;
}
.bp-head p {
  margin: 0 0 18px;
  font-size: 13px;
  color: #5c6b80;
}
.bp-card {
  margin-bottom: 18px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e6ecf5;
  border-radius: 16px;
}
.bp-card h2 {
  margin: 0 0 14px;
  font-size: 15px;
}
.bp-tiers {
  display: flex;
  gap: 28px;
  align-items: flex-end;
}
.bp-tier {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.bp-tier-label {
  font-size: 13px;
  font-weight: 700;
}
.bp-tier-th {
  font-size: 11px;
  color: #8493a8;
}
.bp-matrix {
  border-collapse: collapse;
}
.bp-matrix th {
  padding: 8px 14px;
  font-size: 12px;
  color: #5c6b80;
  text-align: center;
  font-weight: 600;
}
.bp-matrix td {
  padding: 8px 14px;
  text-align: center;
}
.bp-matrix tbody th {
  text-align: left;
}
.bp-states {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}
.bp-states figure {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.bp-states figcaption {
  font-size: 12px;
  color: #5c6b80;
}
.bp-sizes {
  display: flex;
  gap: 24px;
  align-items: center;
}
.bp-calc {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bp-calc-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.bp-calc-item b {
  display: block;
  font-size: 13px;
}
.bp-calc-item span {
  font-size: 11px;
  color: #8493a8;
}
</style>
