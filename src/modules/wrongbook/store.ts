/**
 * 错题集（wrongbook）域 Store。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * items / total / filters 为本域业务状态。
 * 不写 localStorage；事件只做增量刷新加速，页面 onMounted 仍须主动 load()。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  applyWrongbookFilters,
  buildWrongbookRetryTarget,
  chopWrongbook,
  fetchWrongbookList,
  findWrongbookItem,
  updateWrongbookMastery,
  type MasteryLevel,
  type WrongbookFilters,
  type WrongQuestionItem,
  type WrongbookListQuery,
  type WrongbookRetryTarget
} from './api';
import { emitWrongQuestionsChanged, onWrongQuestionsChanged } from './events';

export interface WrongbookState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createWrongbookInitialState(): WrongbookState {
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

export const useWrongbookStore = defineStore('wrongbook', () => {
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const items = ref<WrongQuestionItem[]>([]);
  const total = ref(0);
  const pageSize = ref(DEFAULT_PAGE_SIZE);
  const filters = ref<WrongbookFilters>({});

  let pendingRefresh: Promise<void> | null = null;

  const ready = computed(() => initialized.value && error.value === null);
  const visibleItems = computed(() =>
    applyWrongbookFilters(items.value, filters.value)
  );
  const isEmpty = computed(
    () => initialized.value && !loading.value && visibleItems.value.length === 0
  );
  const hasMore = computed(() => items.value.length < total.value);
  const loadedPages = computed(() =>
    Math.max(1, Math.ceil(items.value.length / pageSize.value))
  );

  function buildQuery(page: number): WrongbookListQuery {
    return {
      page,
      pageSize: pageSize.value,
      subjectId: filters.value.subjectId ?? undefined
    };
  }

  function remember(itemsToMerge: WrongQuestionItem[]): void {
    const merged = new Map<number, WrongQuestionItem>();
    items.value.forEach((item) => merged.set(item.wrong_id, item));
    itemsToMerge.forEach((item) => merged.set(item.wrong_id, item));
    items.value = Array.from(merged.values());
  }

  async function fetchPages(pages: number[]): Promise<WrongQuestionItem[]> {
    const results = await Promise.all(
      pages.map((page) => fetchWrongbookList(buildQuery(page)))
    );
    total.value = results.reduce((acc, r) => Math.max(acc, r.total), 0);
    return results.flatMap((r) => r.items);
  }

  async function load(query: WrongbookListQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    if (query.pageSize) pageSize.value = query.pageSize;
    if (query.subjectId !== undefined) {
      filters.value = { ...filters.value, subjectId: query.subjectId };
    }
    try {
      const result = await fetchWrongbookList(buildQuery(1));
      items.value = result.items;
      total.value = result.total;
    } catch (e) {
      error.value = errorMessage(e);
      items.value = [];
      total.value = 0;
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
      const nextPage = loadedPages.value + 1;
      const result = await fetchWrongbookList(buildQuery(nextPage));
      remember(result.items);
      total.value = result.total;
    } catch (e) {
      error.value = errorMessage(e);
    } finally {
      loadingMore.value = false;
    }
  }

  async function setFilters(next: WrongbookFilters): Promise<void> {
    filters.value = { ...filters.value, ...next };
    await load();
  }

  function patchItem(
    wrongId: number,
    patch: Partial<WrongQuestionItem>
  ): void {
    items.value = items.value.map((item) =>
      item.wrong_id === wrongId ? { ...item, ...patch } : item
    );
  }

  async function markMastered(wrongId: number): Promise<void> {
    await updateMastery(wrongId, 'MASTERED');
  }

  async function updateMastery(
    wrongId: number,
    masteryLevel: MasteryLevel
  ): Promise<void> {
    error.value = null;
    try {
      await updateWrongbookMastery(wrongId, masteryLevel);
      const patch: Partial<WrongQuestionItem> = { mastery_level: masteryLevel };
      if (masteryLevel === 'MASTERED') patch.is_cut = true;
      patchItem(wrongId, patch);
      emitWrongQuestionsChanged({ action: 'mastered' });
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    }
  }

  async function chop(wrongId: number): Promise<void> {
    error.value = null;
    try {
      await chopWrongbook(wrongId);
      patchItem(wrongId, { mastery_level: 'MASTERED', is_cut: true });
      emitWrongQuestionsChanged({ action: 'removed' });
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    }
  }

  function retryTarget(item: WrongQuestionItem): WrongbookRetryTarget {
    return buildWrongbookRetryTarget(item);
  }

  async function refresh(): Promise<void> {
    const pages = Array.from(
      { length: loadedPages.value },
      (_, index) => index + 1
    );
    const fresh = await fetchPages(pages);
    items.value = fresh;
  }

  async function refreshIncrement(): Promise<void> {
    if (pendingRefresh) return pendingRefresh;
    pendingRefresh = (async () => {
      try {
        await refresh();
      } catch (e) {
        error.value = errorMessage(e);
      } finally {
        pendingRefresh = null;
      }
    })();
    return pendingRefresh;
  }

  function bindRefresh(): () => void {
    return onWrongQuestionsChanged((payload) => {
      if (payload.source === 'wrongbook') return;
      void refreshIncrement();
    });
  }

  function reset(): void {
    const initial = createWrongbookInitialState();
    loading.value = initial.loading;
    loadingMore.value = false;
    error.value = initial.error;
    initialized.value = initial.initialized;
    items.value = [];
    total.value = 0;
    pageSize.value = DEFAULT_PAGE_SIZE;
    filters.value = {};
    pendingRefresh = null;
  }

  return {
    loading,
    loadingMore,
    error,
    initialized,
    ready,
    items,
    visibleItems,
    total,
    pageSize,
    filters,
    isEmpty,
    hasMore,
    loadedPages,
    reset,
    load,
    loadMore,
    setFilters,
    updateMastery,
    markMastered,
    chop,
    retryTarget,
    refresh,
    refreshIncrement,
    bindRefresh,
    findItem: findWrongbookItem
  };
});
