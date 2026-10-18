/**
 * 招考信息（recruitment）域 Store（P2-66）。
 *
 * 后端按分类返回 `items: Record<分类, 条目[]>`，每类最多 `limit` 条；
 * 因此本域不做客户端分页，分类 Tab 即筛选维度（分类筛选在本地切换）。
 *
 * 状态全部驻留内存，不写 localStorage。
 * 本域无事件进出：页面 `onMounted`（及统一刷新内核）主动 `load()`。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchRecruitmentDetail,
  fetchRecruitmentList,
  type RecruitmentItem,
  type RecruitmentListQuery,
  type RecruitmentMeta
} from './api';

/** 公共状态骨架 */
export interface RecruitmentState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createRecruitmentInitialState(): RecruitmentState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const candidate = error as { name?: string; code?: string; __aborted?: boolean };
  return (
    candidate.name === 'AbortError' ||
    candidate.name === 'CanceledError' ||
    candidate.code === 'ERR_CANCELED' ||
    candidate.__aborted === true
  );
}

export const useRecruitmentStore = defineStore('recruitment', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const categories = ref<string[]>([]);
  const items = ref<Record<string, RecruitmentItem[]>>({});
  const activeCategory = ref('');
  const meta = ref<RecruitmentMeta | null>(null);

  const detail = ref<RecruitmentItem | null>(null);
  const detailLoading = ref(false);

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 当前分类下的条目（分类筛选） */
  const currentItems = computed<RecruitmentItem[]>(
    () => items.value[activeCategory.value] ?? []
  );

  /** 空态：加载完成、无错误、当前分类确实没有数据 */
  const isEmpty = computed(
    () => initialized.value && !loading.value && currentItems.value.length === 0
  );

  const total = computed(() =>
    Object.values(items.value).reduce((sum, list) => sum + (list?.length ?? 0), 0)
  );

  const categoryCount = computed(() => categories.value.length);

  /** 切换分类（纯本地筛选，不重新请求） */
  function setCategory(category: string): void {
    activeCategory.value = category;
  }

  /**
   * 加载招考信息。
   * 不传 category 时一次取回全部分类；传 category 时仅取该分类。
   * 失败进入错误态并清空数据；请求取消不写入错误。
   */
  async function load(query: RecruitmentListQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const result = await fetchRecruitmentList({
        limit: query.limit ?? 20,
        category: query.category,
        signal: query.signal,
        ts: query.ts
      });
      categories.value = result.categories ?? [];
      items.value = result.items ?? {};
      meta.value = result.meta ?? null;

      const preferred =
        query.category && items.value[query.category] ? query.category : '';
      if (preferred) {
        activeCategory.value = preferred;
      } else if (
        !activeCategory.value ||
        !Object.prototype.hasOwnProperty.call(items.value, activeCategory.value)
      ) {
        activeCategory.value = categories.value[0] ?? '';
      }
    } catch (e) {
      if (isAbortError(e)) return;
      error.value = errorMessage(e);
      categories.value = [];
      items.value = {};
      meta.value = null;
      activeCategory.value = '';
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  /** 打开招考详情（同时刷新浏览量） */
  async function openDetail(
    id: string | number,
    fallback: RecruitmentItem | null = null
  ): Promise<RecruitmentItem | null> {
    detailLoading.value = true;
    error.value = null;
    try {
      const item = await fetchRecruitmentDetail(id);
      detail.value = item;
      const list = items.value[item.category];
      if (list) {
        const index = list.findIndex((entry) => entry.id === item.id);
        if (index >= 0) list[index] = { ...list[index], ...item };
      }
      return item;
    } catch (e) {
      if (isAbortError(e)) return fallback;
      error.value = errorMessage(e);
      detail.value = fallback;
      return fallback;
    } finally {
      detailLoading.value = false;
      initialized.value = true;
    }
  }

  /** 关闭详情 */
  function clearDetail(): void {
    detail.value = null;
  }

  /** 重置为初始状态 */
  function reset(): void {
    const initial = createRecruitmentInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    categories.value = [];
    items.value = {};
    activeCategory.value = '';
    meta.value = null;
    detail.value = null;
    detailLoading.value = false;
  }

  return {
    loading,
    error,
    initialized,
    categories,
    items,
    activeCategory,
    meta,
    detail,
    detailLoading,
    ready,
    currentItems,
    isEmpty,
    total,
    categoryCount,
    setCategory,
    reset,
    load,
    openDetail,
    clearDetail
  };
});
