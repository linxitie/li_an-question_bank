/**
 * 题库浏览（catalog）域 Store（P2-71）。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * filters / items / total / page / pageSize / selected 为本域业务状态。
 *
 * 约定：
 *   - 列表为服务端分页（后端支持 page / page_size，上限 100）；
 *   - 本域只读：不负责答题落库，不发布任何事件；
 *   - 筛选参数保持在本域，详情复用当前列表缓存；
 *   - ⑱⑲⑳（联考小智 / 院校联考机考系统 / 小模考）不在此实现。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchCatalogDetail,
  fetchCatalogList,
  type CatalogListQuery,
  type CatalogQuestion
} from './api';

/** 本域状态契约（公共骨架字段） */
export interface CatalogState {
  /** 是否正在加载数据 */
  loading: boolean;
  /** 最近一次错误信息（无错误为 null） */
  error: string | null;
  /** 是否已完成首次初始化 */
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createCatalogInitialState(): CatalogState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

/** 当前生效的筛选条件（不含分页） */
export interface CatalogFilters {
  subjectId?: number;
  typeId?: number;
  pointId?: number;
  difficulty?: number;
  auditStatus?: number;
  year?: number;
  keyword: string;
}

export const EMPTY_CATALOG_FILTERS: CatalogFilters = {
  subjectId: undefined,
  typeId: undefined,
  pointId: undefined,
  difficulty: undefined,
  auditStatus: undefined,
  year: undefined,
  keyword: ''
};

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

function normalizePage(value: number | undefined): number {
  return value && value > 0 ? Math.floor(value) : 1;
}

function normalizePageSize(value: number | undefined, fallback: number): number {
  if (!value || value <= 0) return fallback;
  return Math.min(100, Math.max(1, Math.floor(value)));
}

export const useCatalogStore = defineStore('catalog', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const filters = ref<CatalogFilters>({ ...EMPTY_CATALOG_FILTERS });
  const items = ref<CatalogQuestion[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(10);
  const selected = ref<CatalogQuestion | null>(null);

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 空态：加载完成、无错误、确实没有数据 */
  const isEmpty = computed(
    () => initialized.value && !loading.value && items.value.length === 0
  );

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(total.value / Math.max(1, pageSize.value)))
  );

  const hasPrevPage = computed(() => page.value > 1);
  const hasNextPage = computed(() => page.value < totalPages.value);

  /**
   * 加载题目列表（只读）。
   * 传入的筛选字段覆盖当前筛选；未传的字段沿用当前值。
   * 失败进入错误态并清空列表，同时置 initialized 便于展示空态/错误态。
   */
  async function load(query: CatalogListQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;

    if (query.subjectId !== undefined) filters.value.subjectId = query.subjectId;
    if (query.typeId !== undefined) filters.value.typeId = query.typeId;
    if (query.pointId !== undefined) filters.value.pointId = query.pointId;
    if (query.difficulty !== undefined) filters.value.difficulty = query.difficulty;
    if (query.auditStatus !== undefined) filters.value.auditStatus = query.auditStatus;
    if (query.year !== undefined) filters.value.year = query.year;
    if (query.keyword !== undefined) filters.value.keyword = query.keyword;

    page.value = normalizePage(query.page);
    pageSize.value = normalizePageSize(query.pageSize, pageSize.value);

    try {
      const result = await fetchCatalogList({
        ...filters.value,
        page: page.value,
        pageSize: pageSize.value
      });
      items.value = result.items ?? [];
      total.value = result.total ?? items.value.length;
    } catch (e) {
      error.value = errorMessage(e);
      items.value = [];
      total.value = 0;
      page.value = 1;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  /** 翻页（服务端分页，越界自动收敛到合法页） */
  async function goPage(target: number): Promise<void> {
    const next = Math.min(
      Math.max(1, Math.floor(Number(target) || 1)),
      totalPages.value
    );
    if (next === page.value) return;
    await load({ page: next });
  }

  /** 清空筛选并按第一页重新加载 */
  async function clearFilters(): Promise<void> {
    filters.value = { ...EMPTY_CATALOG_FILTERS };
    await load({ page: 1 });
  }

  /** 打开题目详情（只读）；失败时记录 error 并返回 null */
  async function openQuestion(
    id: string | number,
    fallback: CatalogQuestion | null = null
  ): Promise<CatalogQuestion | null> {
    error.value = null;
    try {
      const detail = await fetchCatalogDetail(id);
      selected.value = detail;
      const index = items.value.findIndex(
        (item) => item.question_id === detail.question_id
      );
      if (index >= 0) {
        items.value[index] = { ...items.value[index], ...detail };
      }
      return detail;
    } catch (e) {
      error.value = errorMessage(e);
      selected.value = fallback;
      return null;
    }
  }

  /** 关闭详情 */
  function clearSelection(): void {
    selected.value = null;
  }

  /** 重置为初始状态 */
  function reset(): void {
    const initial = createCatalogInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    filters.value = { ...EMPTY_CATALOG_FILTERS };
    items.value = [];
    total.value = 0;
    page.value = 1;
    pageSize.value = 10;
    selected.value = null;
  }

  return {
    loading,
    error,
    initialized,
    filters,
    items,
    total,
    page,
    pageSize,
    selected,
    ready,
    isEmpty,
    totalPages,
    hasPrevPage,
    hasNextPage,
    reset,
    load,
    goPage,
    clearFilters,
    openQuestion,
    clearSelection
  };
});
