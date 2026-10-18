/**
 * 每日新闻（news）域 Store（P2-33）。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * items / total / page / pageSize / selected 为本域业务状态。
 *
 * 约定：
 *   - 已读状态一律以服务端返回的 `is_read` 为准，**不写 localStorage**；
 *   - 分页为客户端分页（后端 `limit` 上限 50，一次取回后本地切页）；
 *   - 打开详情调用 `openArticle()`，由后端详情端点记录已读并发布 E7。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchNewsDetail,
  fetchNewsList,
  type NewsItem,
  type NewsListQuery
} from './api';

export interface NewsState {
  /** 是否正在加载数据 */
  loading: boolean;
  /** 最近一次错误信息（无错误为 null） */
  error: string | null;
  /** 是否已完成首次初始化 */
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createNewsInitialState(): NewsState {
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

export const useNewsStore = defineStore('news', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const items = ref<NewsItem[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const selected = ref<NewsItem | null>(null);

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 空态：加载完成、无错误、确实没有数据 */
  const isEmpty = computed(
    () => initialized.value && !loading.value && items.value.length === 0
  );

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(total.value / Math.max(1, pageSize.value)))
  );

  /** 当前页数据（客户端切页） */
  const pageItems = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return items.value.slice(start, start + pageSize.value);
  });

  const hasPrevPage = computed(() => page.value > 1);
  const hasNextPage = computed(() => page.value < totalPages.value);

  /** 翻页（越界自动收敛，不重新请求） */
  function goPage(target: number): void {
    const next = Math.floor(Number(target) || 1);
    page.value = Math.min(Math.max(1, next), totalPages.value);
  }

  /**
   * 加载列表。成功写入 items / total，失败进入错误态并清空。
   * `query.page`、`query.pageSize` 仅用于客户端分页，不发给后端。
   */
  async function load(query: NewsListQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    if (query.pageSize && query.pageSize > 0) {
      pageSize.value = query.pageSize;
    }
    try {
      const result = await fetchNewsList(query);
      items.value = result.items ?? [];
      total.value = result.total ?? items.value.length;
      goPage(query.page ?? 1);
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

  /**
   * 打开新闻详情（同时是阅读上报入口）。
   * 返回详情；失败时记录 error，并回退到调用方提供的列表项（若有），
   * 保证正文仍可阅读；两者都没有则返回 null。
   */
  async function openArticle(
    id: string | number,
    fallback: NewsItem | null = null
  ): Promise<NewsItem | null> {
    error.value = null;
    try {
      const article = await fetchNewsDetail(id);
      selected.value = article;
      const index = items.value.findIndex((item) => item.id === article.id);
      if (index >= 0) {
        items.value[index] = {
          ...items.value[index],
          ...article,
          is_read: article.is_read ?? true
        };
      }
      return article;
    } catch (e) {
      error.value = errorMessage(e);
      selected.value = fallback;
      return fallback;
    }
  }

  /** 关闭详情 */
  function clearSelection(): void {
    selected.value = null;
  }

  /** 是否已读（以后端返回的 is_read 为准） */
  function isRead(id: string | number): boolean {
    const found = items.value.find((item) => item.id === id);
    return Boolean(found?.is_read);
  }

  /** 重置为初始状态 */
  function reset(): void {
    const initial = createNewsInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    items.value = [];
    total.value = 0;
    page.value = 1;
    pageSize.value = 20;
    selected.value = null;
  }

  return {
    loading,
    error,
    initialized,
    items,
    total,
    page,
    pageSize,
    selected,
    ready,
    isEmpty,
    totalPages,
    pageItems,
    hasPrevPage,
    hasNextPage,
    reset,
    load,
    openArticle,
    clearSelection,
    isRead,
    goPage
  };
});
