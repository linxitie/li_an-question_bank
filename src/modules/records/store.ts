/**
 * 练习记录（records）域 Store。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * records / dailyStats / stats / trend / filters 为本域业务状态。
 * 不写 localStorage；事件只做增量刷新加速，页面 onMounted 仍须主动 load()。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  applyRecordsFilters,
  fetchRecordsList,
  fetchRecordsStats,
  fetchRecordsTrend,
  type RecordsDailyStat,
  type RecordsFilters,
  type RecordsItem,
  type RecordsListQuery,
  type RecordsStats,
  type RecordsTrendPoint
} from './api';
import { onRecordsChanged } from './events';

export interface RecordsState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createRecordsInitialState(): RecordsState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

const DEFAULT_PAGE_SIZE = 20;

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

export const useRecordsStore = defineStore('records', () => {
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const records = ref<RecordsItem[]>([]);
  const dailyStats = ref<RecordsDailyStat[]>([]);
  const total = ref(0);
  const offset = ref(0);
  const pageSize = ref(DEFAULT_PAGE_SIZE);
  const filters = ref<RecordsFilters>({});
  const stats = ref<RecordsStats | null>(null);
  const trend = ref<RecordsTrendPoint[]>([]);
  const trendDays = ref(7);

  const ready = computed(() => initialized.value && error.value === null);
  const filteredRecords = computed(() =>
    applyRecordsFilters(records.value, filters.value)
  );
  const isEmpty = computed(
    () => initialized.value && !loading.value && filteredRecords.value.length === 0
  );
  const hasMore = computed(() => records.value.length < total.value);

  function buildQuery(nextOffset: number): RecordsListQuery {
    return {
      limit: pageSize.value,
      offset: nextOffset,
      subjectId: filters.value.subjectId ?? undefined
    };
  }

  function appendItems(items: RecordsItem[]): void {
    const seen = new Set(records.value.map((item) => item.record_id));
    const fresh = items.filter((item) => !seen.has(item.record_id));
    records.value = records.value.concat(fresh);
  }

  async function load(query: RecordsListQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    if (query.limit) pageSize.value = query.limit;
    if (query.subjectId !== undefined) {
      filters.value = { ...filters.value, subjectId: query.subjectId };
    }
    offset.value = 0;
    try {
      const result = await fetchRecordsList(buildQuery(0));
      records.value = result.items;
      dailyStats.value = result.dailyStats;
      total.value = result.total;
      offset.value = result.items.length;
    } catch (e) {
      error.value = errorMessage(e);
      records.value = [];
      dailyStats.value = [];
      total.value = 0;
      offset.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadMore(): Promise<void> {
    if (loading.value || loadingMore.value || !hasMore.value) return;
    loadingMore.value = true;
    error.value = null;
    try {
      const result = await fetchRecordsList(buildQuery(offset.value));
      appendItems(result.items);
      total.value = result.total;
      offset.value += result.items.length;
    } catch (e) {
      error.value = errorMessage(e);
    } finally {
      loadingMore.value = false;
    }
  }

  async function setFilters(next: RecordsFilters): Promise<void> {
    filters.value = { ...filters.value, ...next };
    await load();
  }

  async function loadStats(): Promise<void> {
    try {
      stats.value = await fetchRecordsStats();
    } catch (e) {
      error.value = errorMessage(e);
      stats.value = null;
    }
  }

  async function loadTrend(days = trendDays.value): Promise<void> {
    trendDays.value = days;
    try {
      trend.value = await fetchRecordsTrend(days);
    } catch (e) {
      error.value = errorMessage(e);
      trend.value = [];
    }
  }

  async function refresh(): Promise<void> {
    await Promise.all([load(), loadStats(), loadTrend()]);
  }

  function bindRecordsRefresh(): () => void {
    return onRecordsChanged(() => {
      void refresh();
    });
  }

  function reset(): void {
    const initial = createRecordsInitialState();
    loading.value = initial.loading;
    loadingMore.value = false;
    error.value = initial.error;
    initialized.value = initial.initialized;
    records.value = [];
    dailyStats.value = [];
    total.value = 0;
    offset.value = 0;
    pageSize.value = DEFAULT_PAGE_SIZE;
    filters.value = {};
    stats.value = null;
    trend.value = [];
    trendDays.value = 7;
  }

  return {
    loading,
    loadingMore,
    error,
    initialized,
    ready,
    records,
    filteredRecords,
    dailyStats,
    total,
    offset,
    pageSize,
    filters,
    stats,
    trend,
    trendDays,
    isEmpty,
    hasMore,
    reset,
    load,
    loadMore,
    setFilters,
    loadStats,
    loadTrend,
    refresh,
    bindRecordsRefresh
  };
});
