/**
 * 组卷与历年试卷（papers）域 Store。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * items / total / filters 为本域业务状态。
 * 不写 localStorage；事件只做增量刷新加速，页面 onMounted 仍须主动 load()。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchPapersList,
  type PaperItem,
  type PapersFilters,
  type PapersListQuery
} from './api';
import { onPapersDataChanged } from './events';

export interface PapersState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createPapersInitialState(): PapersState {
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
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message?: unknown }).message);
  }
  return '请求失败，请稍后重试';
}

export const usePapersStore = defineStore('papers', () => {
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const items = ref<PaperItem[]>([]);
  const total = ref(0);
  const pageSize = ref(DEFAULT_PAGE_SIZE);
  const filters = ref<PapersFilters>({});

  let pendingRefresh: Promise<void> | null = null;
  let activeLoadToken = 0;

  const ready = computed(() => initialized.value && error.value === null);
  const isEmpty = computed(
    () => initialized.value && !loading.value && items.value.length === 0
  );
  const hasMore = computed(() => items.value.length < total.value);
  const loadedPages = computed(() =>
    Math.max(1, Math.ceil(items.value.length / pageSize.value))
  );

  function buildQuery(page: number): PapersListQuery {
    return {
      page,
      pageSize: pageSize.value,
      subjectId: filters.value.subjectId ?? undefined,
      examType: filters.value.examType || undefined,
      keyword: filters.value.keyword || undefined
    };
  }

  function remember(itemsToMerge: PaperItem[]): void {
    const merged = new Map<number, PaperItem>();
    items.value.forEach((item) => merged.set(item.paper_id, item));
    itemsToMerge.forEach((item) => merged.set(item.paper_id, item));
    items.value = Array.from(merged.values());
  }

  async function load(query: PapersListQuery = {}): Promise<void> {
    const token = ++activeLoadToken;
    loading.value = true;
    error.value = null;
    if (query.pageSize) pageSize.value = query.pageSize;
    if (query.subjectId !== undefined) {
      filters.value = { ...filters.value, subjectId: query.subjectId };
    }
    if (query.examType !== undefined) {
      filters.value = { ...filters.value, examType: query.examType };
    }
    if (query.keyword !== undefined) {
      filters.value = { ...filters.value, keyword: query.keyword };
    }
    try {
      const result = await fetchPapersList(buildQuery(1));
      if (token !== activeLoadToken) return;
      items.value = result.items;
      total.value = result.total;
    } catch (e) {
      if (token !== activeLoadToken) return;
      error.value = errorMessage(e);
      items.value = [];
      total.value = 0;
    } finally {
      if (token === activeLoadToken) {
        loading.value = false;
        initialized.value = true;
      }
    }
  }

  async function loadMore(): Promise<void> {
    if (loading.value || loadingMore.value || !hasMore.value) return;
    loadingMore.value = true;
    error.value = null;
    try {
      const result = await fetchPapersList(buildQuery(loadedPages.value + 1));
      remember(result.items);
      total.value = result.total;
    } catch (e) {
      error.value = errorMessage(e);
    } finally {
      loadingMore.value = false;
    }
  }

  async function setFilters(next: PapersFilters): Promise<void> {
    filters.value = { ...filters.value, ...next };
    await load();
  }

  async function refresh(): Promise<void> {
    await load();
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
    return onPapersDataChanged((payload) => {
      if (payload.source === 'papers') return;
      void refreshIncrement();
    });
  }

  function findItem(id: string | number): PaperItem | undefined {
    const target = Number(id);
    return items.value.find((item) => item.paper_id === target);
  }

  function reset(): void {
    const initial = createPapersInitialState();
    loading.value = initial.loading;
    loadingMore.value = false;
    error.value = initial.error;
    initialized.value = initial.initialized;
    items.value = [];
    total.value = 0;
    pageSize.value = DEFAULT_PAGE_SIZE;
    filters.value = {};
    pendingRefresh = null;
    activeLoadToken += 1;
  }

  return {
    loading,
    loadingMore,
    error,
    initialized,
    ready,
    items,
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
    refresh,
    refreshIncrement,
    bindRefresh,
    findItem
  };
});
