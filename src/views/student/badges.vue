<template>
  <div class="bd-page">
    <header class="bd-head">
      <div>
        <h1 class="bd-title">我的徽章</h1>
        <p class="bd-sub">徽章档位随累计积分实时提升；已获得的徽章不会因积分变化而降级。</p>
      </div>
      <span class="bd-total" v-if="!loading">共 {{ total }} 枚</span>
    </header>

    <BadgeTierCard
      :score="score"
      :tier-index="tierIndex"
      :owned="owned"
      :total="total"
    />

    <section class="bd-filters">
      <div class="bd-filter-group">
        <button
          v-for="k in KIND_OPTIONS"
          :key="k.value"
          class="bd-chip"
          :class="{ 'is-active': filters.kind === k.value }"
          @click="filters.kind = k.value; goPage(1)"
        >{{ k.label }}</button>
      </div>

      <div class="bd-filter-group">
        <button
          v-for="s in STATE_OPTIONS"
          :key="s.value"
          class="bd-chip"
          :class="{ 'is-active': filters.state === s.value }"
          @click="filters.state = s.value; goPage(1)"
        >{{ s.label }}</button>
      </div>

      <div class="bd-filter-group">
        <button
          v-for="t in TIER_OPTIONS"
          :key="t.value"
          class="bd-chip"
          :class="{ 'is-active': filters.tier === t.value }"
          @click="filters.tier = t.value; goPage(1)"
        >{{ t.label }}</button>
      </div>

      <select v-model="filters.category" class="bd-select" @change="goPage(1)">
        <option value="">全部类别</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>

      <input
        v-model="filters.keyword"
        class="bd-search"
        type="text"
        placeholder="搜索徽章名称"
        @input="goPage(1)"
      />
    </section>

    <div v-if="error" class="bd-error">{{ error }}</div>
    <div v-if="loading" class="bd-empty">加载中…</div>

    <template v-else>
      <BadgesGrid :items="pageItems" :current-tier-index="tierIndex" @select="openDetail" />

      <footer class="bd-pager" v-if="maxPage > 1">
        <button class="bd-page-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="bd-page-info">第 {{ page }} / {{ maxPage }} 页 · 共 {{ filteredTotal }} 枚</span>
        <button class="bd-page-btn" :disabled="page >= maxPage" @click="goPage(page + 1)">下一页</button>
      </footer>
      <p v-else-if="filteredTotal" class="bd-page-info bd-page-single">共 {{ filteredTotal }} 枚</p>
    </template>

    <BadgeDetailModal
      :item="detailItem"
      :current-tier-index="tierIndex"
      @close="detailItem = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import BadgeTierCard from '@/components/badge/BadgeTierCard.vue';
import BadgesGrid from '@/components/badge/BadgesGrid.vue';
import BadgeDetailModal from '@/components/badge/BadgeDetailModal.vue';
import { BADGE_TIERS } from '@/components/badge/badgePalette';
import {
  DEFAULT_FILTERS,
  filterBadges,
  filterByTier,
  maxPageOf,
  paginate,
  type BadgeFilters,
  type BadgeItem,
  type KindFilter,
  type StateFilter,
  type TierFilter
} from './badgesLogic';

const PAGE_SIZE = 15;

const apiFetch = (url: string, init?: RequestInit) => {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
};

const items = ref<BadgeItem[]>([]);
const score = ref(0);
const tierIndex = ref(0);
const owned = ref(0);
const total = ref(0);
const loading = ref(true);
const error = ref('');
const page = ref(1);
const detailItem = ref<BadgeItem | null>(null);

const openDetail = (item: BadgeItem) => {
  detailItem.value = item;
};
const filters = reactive<BadgeFilters>({ ...DEFAULT_FILTERS });

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

const categories = computed(() => {
  const set = new Set(items.value.map((i) => i.category).filter(Boolean));
  return Array.from(set);
});

const tierLabelOf = (it: BadgeItem) => it.snapshot_tier || it.current_tier || '黑铁';

const filtered = computed(() => {
  const byBase = filterBadges(items.value, filters);
  return filterByTier(byBase, filters.tier, tierLabelOf);
});
const filteredTotal = computed(() => filtered.value.length);
const maxPage = computed(() => maxPageOf(filteredTotal.value, PAGE_SIZE));
const pageItems = computed(() => paginate(filtered.value, page.value, PAGE_SIZE));

const goPage = (p: number) => {
  page.value = Math.min(Math.max(1, Math.round(p)), maxPage.value);
};

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    const resp = await apiFetch('/api/badges/my');
    if (!resp.ok) {
      error.value =
        resp.status === 401 || resp.status === 403
          ? '请先登录后查看我的徽章'
          : `加载失败（${resp.status}）`;
      items.value = [];
      return;
    }
    const data = await resp.json();
    items.value = (data.items || []) as BadgeItem[];
    score.value = data.score || 0;
    tierIndex.value = data.tier?.index ?? 0;
    owned.value = data.owned || 0;
    total.value = data.total || items.value.length;
  } catch (e) {
    error.value = `加载失败：${(e as Error)?.message || e}`;
  } finally {
    loading.value = false;
  }
};

onMounted(load);
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
.bd-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}
.bd-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #5c6b80;
}
.bd-total {
  font-size: 13px;
  color: #8493a8;
}
.bd-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 16px 0 18px;
}
.bd-filter-group {
  display: inline-flex;
  gap: 6px;
}
.bd-chip {
  height: 30px;
  padding: 0 14px;
  border: 1px solid #e6ecf5;
  border-radius: 15px;
  background: #fff;
  color: #5c6b80;
  font-size: 12px;
  cursor: pointer;
}
.bd-chip.is-active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
  font-weight: 600;
}
.bd-select,
.bd-search {
  height: 30px;
  padding: 0 12px;
  border: 1px solid #e6ecf5;
  border-radius: 15px;
  background: #fff;
  font-size: 12px;
  color: #3d4d66;
}
.bd-search {
  width: 180px;
  margin-left: auto;
}
.bd-error {
  margin: 10px 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fdecec;
  color: #c22b2b;
  font-size: 13px;
}
.bd-empty {
  padding: 48px 0;
  text-align: center;
  color: #94a3b8;
}
.bd-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 18px;
}
.bd-page-btn {
  height: 32px;
  padding: 0 16px;
  border: 1px solid #e6ecf5;
  border-radius: 10px;
  background: #fff;
  color: #5c6b80;
  font-size: 13px;
  cursor: pointer;
}
.bd-page-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.bd-page-info {
  font-size: 12px;
  color: #8493a8;
}
.bd-page-single {
  margin-top: 16px;
  text-align: center;
}
</style>
