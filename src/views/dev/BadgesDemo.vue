<template>
  <div class="bd-page">
    <header class="bd-head">
      <div>
        <h1 class="bd-title">我的徽章</h1>
        <p class="bd-sub">演示数据（组件预览用）：徽章档位随累计积分实时提升；已获得的徽章不会因积分变化而降级。</p>
      </div>
      <span class="bd-total">共 {{ total }} 枚</span>
    </header>

    <BadgeTierCard :score="score" :tier-index="tierIndex" :owned="owned" :total="total" />

    <section class="bd-filters">
      <div class="bd-filter-group">
        <button
          v-for="k in KIND_OPTIONS"
          :key="k.value"
          class="bd-chip"
          :class="{ 'is-active': kind === k.value }"
          @click="kind = k.value; goPage(1)"
        >{{ k.label }}</button>
      </div>
      <div class="bd-filter-group">
        <button
          v-for="s in STATE_OPTIONS"
          :key="s.value"
          class="bd-chip"
          :class="{ 'is-active': state === s.value }"
          @click="state = s.value; goPage(1)"
        >{{ s.label }}</button>
      </div>
      <div class="bd-filter-group">
        <button
          v-for="t in TIER_OPTIONS"
          :key="t.value"
          class="bd-chip"
          :class="{ 'is-active': tierFilter === t.value }"
          @click="tierFilter = t.value; goPage(1)"
        >{{ t.label }}</button>
      </div>
    </section>

    <BadgeWall
      class="bd-wall"
      :items="wall"
      :current-tier-index="tierIndex"
      @select="openDetail"
      @view-all="() => {}"
    />

    <BadgesGrid :items="pageItems" :current-tier-index="tierIndex" @select="openDetail" />

    <BadgeDetailModal :item="detailItem" :current-tier-index="tierIndex" @close="detailItem = null" />

    <!-- 个人主页徽章墙的等价预览（同一套卡片样式，选中项即精选徽章） -->
    <section class="bd-wall-strip">
      <div class="bws-head">
        <h2>我的徽章（主页墙预览 · 精选优先）</h2>
        <span class="bws-all">查看全部 →</span>
      </div>
      <div class="bws-grid">
        <div v-for="b in wallPinned" :key="`w-${b.id}`" class="bws-item">
          <BadgeIcon
            :shape="(b.shape as BadgeShape) || 'shield'"
            :tier="tierIndexOf(b)"
            :size="66"
            :locked="!b.owned"
          />
          <span class="bws-name">{{ b.name }}</span>
          <span v-if="b.owned && b.rarity_text" class="bws-rarity">{{ b.rarity_text }}</span>
          <span v-if="b.is_first_owner" class="bws-first">全服首个获得</span>
        </div>
      </div>
    </section>

    <footer class="bd-pager">
      <button class="bd-page-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span class="bd-page-info">第 {{ page }} / {{ maxPage }} 页 · 共 {{ filteredTotal }} 枚</span>
      <button class="bd-page-btn" :disabled="page >= maxPage" @click="goPage(page + 1)">下一页</button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import BadgeTierCard from '@/components/badge/BadgeTierCard.vue';
import BadgesGrid from '@/components/badge/BadgesGrid.vue';
import BadgeIcon from '@/components/badge/BadgeIcon.vue';
import BadgeWall from '@/components/badge/BadgeWall.vue';
import BadgeDetailModal from '@/components/badge/BadgeDetailModal.vue';
import { BADGE_TIERS, type BadgeShape } from '@/components/badge/badgePalette';
import {
  filterBadges,
  filterByTier,
  maxPageOf,
  paginate,
  type BadgeFilters,
  type BadgeItem,
  type KindFilter,
  type StateFilter,
  type TierFilter,
  wallItems
} from '@/views/student/badgesLogic';

const PAGE_SIZE = 15;
const score = 780;
const tierIndex = 3;
const owned = 23;
const total = 57;

const SHAPES: Record<string, string> = { 社交: 'ribbon', 成长: 'ribbon', 称号: 'ribbon' };
const NAMES: Array<[string, string, boolean]> = [
  ['初来乍到', '成长', true], ['连续学习7天', '坚持', true], ['月度学霸', '坚持', true],
  ['铁壁行者', '坚持', true], ['百题斩', '数量', true], ['千锤者', '数量', false],
  ['精准神射', '正确率', true], ['磐石判官', '正确率', false], ['全科通关', '综合', false],
  ['并肩同行', '社交', true], ['引路灯塔', '社交', false], ['复盘之刃', '错题', true],
  ['破茧追光', '错题', false], ['见习', '称号', true], ['入门', '称号', true],
  ['熟练', '称号', false], ['精通', '称号', false], ['大师', '称号', false],
  ['宗师', '称号', false], ['砺安之星', '称号', true], ['公考达人', '称号', false]
];

const TIER_LABELS = ['黑铁', '青铜', '白银', '黄金', '钻石'];

const items: BadgeItem[] = NAMES.map(([name, category, isOwned], i) => ({
  kind: category === '称号' ? 'title' : 'achievement',
  id: i + 1,
  name,
  category,
  shape: SHAPES[category] || 'shield',
  owned: isOwned,
  // 演示页刻意铺满 5 档，且已获得/未获得交替，便于一次看全新样式
  badge_tier: TIER_LABELS[i % 5],
  obtained_at: isOwned ? `2026-10-${(i % 27) + 1}` : null,
  snapshot_tier: TIER_LABELS[i % 5],
  current_tier: '黄金',
  rarity_text: `全服 ${Math.round(((120 + i * 37) / 1204) * 1000) / 10}% 获得`,
  is_first_owner: isOwned && i % 7 === 1,
  pinned: i < 3,                       // 演示精选：前 3 枚
  snapshot_estimated: i % 4 === 0,     // 演示「（估算）」标注
  threshold: isOwned ? 0 : (i % 5) * 10,
  condition_desc: isOwned
    ? '达成对应学习条件后自动解锁（演示数据）'
    : '再完成 ' + ((i % 5) * 5 + 5) + ' 次对应行为即可解锁',
  reward_coins: [10, 30, 80, 150, 300][i % 5],
  owned_count: 120 + i * 37,
  owned_percent: Math.round(((120 + i * 37) / 1204) * 1000) / 10
}));

const kind = ref<KindFilter>('all');
const state = ref<StateFilter>('all');
const tierFilter = ref<TierFilter>('all');
const page = ref(1);
const filters = reactive<Partial<BadgeFilters>>({});

const KIND_OPTIONS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'achievement', label: '成就' },
  { value: 'title', label: '称号' }
];
const STATE_OPTIONS: { value: StateFilter; label: string }[] = [
  { value: 'all', label: '全部状态' },
  { value: 'owned', label: '已获得' },
  { value: 'unowned', label: '未获得' }
];
const TIER_OPTIONS: { value: TierFilter; label: string }[] = [
  { value: 'all', label: '全部品质' },
  ...BADGE_TIERS.map((t) => ({ value: t.code as TierFilter, label: t.label }))
];

const tierLabelOf = (it: BadgeItem) => it.snapshot_tier || it.current_tier || '黑铁';
const tierIndexOf = (it: BadgeItem) => {
  const label = (it as any).badge_tier || it.snapshot_tier || '黑铁';
  const i = TIER_LABELS.indexOf(label);
  return i < 0 ? 0 : i;
};
/** 主页墙预览：精选优先，其次按 id 顺序取前 6 枚 */
const wallPinned = computed(() => {
  const owned = items.filter((i) => i.owned);
  const pinned = owned.filter((i) => (i as any).pinned);
  const rest = owned.filter((i) => !(i as any).pinned);
  return [...pinned, ...rest].slice(0, 6);
});
const filtered = computed(() => {
  const base = filterBadges(items, { ...filters, kind: kind.value, state: state.value });
  return filterByTier(base, tierFilter.value, tierLabelOf);
});
const filteredTotal = computed(() => filtered.value.length);
const maxPage = computed(() => maxPageOf(filteredTotal.value, PAGE_SIZE));
const pageItems = computed(() => paginate(filtered.value, page.value, PAGE_SIZE));
const wall = computed(() => wallItems(items, 6));
const detailItem = ref<BadgeItem | null>(null);
const openDetail = (item: BadgeItem) => {
  detailItem.value = item;
};

const goPage = (p: number) => {
  page.value = Math.min(Math.max(1, Math.round(p)), maxPage.value);
};

// ?modal=1 时自动打开第一枚，便于截图预览详情弹层
if (window.location.hash.includes('modal=1')) {
  detailItem.value = wall.value[0] || items[0] || null;
}
</script>

<style scoped>
.bd-page {
  min-height: 100vh;
  padding: 20px 28px 44px;
  background: #f4f6fb;
  color: #16233b;
}
.bd-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.bd-title { margin: 0; font-size: 22px; font-weight: 700; }
.bd-sub { margin: 6px 0 0; font-size: 13px; color: #5c6b80; }
.bd-total { font-size: 13px; color: #8493a8; }
.bd-filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 16px 0 18px; }
.bd-filter-group { display: inline-flex; gap: 6px; }
.bd-chip {
  height: 30px; padding: 0 14px; border: 1px solid #e6ecf5; border-radius: 15px;
  background: #fff; color: #5c6b80; font-size: 12px; cursor: pointer;
}
.bd-chip.is-active { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 600; }
.bd-wall { margin-bottom: 18px; }
.bd-pager { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 18px; }
.bd-page-btn {
  height: 32px; padding: 0 16px; border: 1px solid #e6ecf5; border-radius: 10px;
  background: #fff; color: #5c6b80; font-size: 13px; cursor: pointer;
}
.bd-page-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.bd-page-info { font-size: 12px; color: #8493a8; }

/* 主页墙预览 */
.bd-wall-strip {
  margin-top: 18px;
  background: #fff;
  border: 1px solid #e5eaf3;
  border-radius: 14px;
  padding: 14px 18px;
}
.bws-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.bws-head h2 { font-size: 15px; margin: 0; color: #16233b; }
.bws-all { font-size: 12.5px; color: #2a5298; }
.bws-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.bws-item { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.bws-name { font-size: 12.5px; color: #1f2d3d; }
.bws-rarity { font-size: 11px; color: #94a3b8; }
.bws-first {
  font-size: 10.5px; color: #64748b; border: 1px solid #cbd5e1;
  border-radius: 6px; padding: 0 5px;
}
@media (max-width: 900px) {
  .bws-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
