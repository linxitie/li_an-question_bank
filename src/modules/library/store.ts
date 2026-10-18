/**
 * 备考资料（library）域 Store（P2-37）。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * items / total / page / pageSize / selected / summary 为本域业务状态。
 *
 * 约定：
 *   - 学习进度一律以后端 `user_material_progress` 为准，**不写 localStorage**；
 *   - 列表为服务端分页（后端支持 page / page_size）；
 *   - 打开详情调用 `openMaterial()`，由后端详情端点记录打开并发布 E8。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchLibraryDetail,
  fetchLibraryList,
  fetchLibraryProgressSummary,
  reportLibraryProgress,
  toggleLibraryFavorite,
  type LibraryMaterial,
  type LibraryMaterialDetail,
  type LibraryMaterialType,
  type LibraryProgressSummary,
  type LibrarySubject
} from './api';

export interface LibraryState {
  /** 是否正在加载数据 */
  loading: boolean;
  /** 最近一次错误信息（无错误为 null） */
  error: string | null;
  /** 是否已完成首次初始化 */
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createLibraryInitialState(): LibraryState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export interface LibraryStoreQuery {
  subject?: LibrarySubject;
  type?: LibraryMaterialType;
  page?: number;
  pageSize?: number;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

export const useLibraryStore = defineStore('library', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const subject = ref<LibrarySubject>('xingce');
  const type = ref<LibraryMaterialType | null>(null);
  const items = ref<LibraryMaterial[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const selected = ref<LibraryMaterialDetail | null>(null);
  const summary = ref<LibraryProgressSummary>({
    studied: 0,
    total: 0,
    percentage: 0
  });

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
   * 加载列表。成功写入 items / total，失败进入错误态并清空。
   * 参数原样传给 fetchLibraryList（pageSize 由 api 映射为 page_size）。
   */
  async function load(query: LibraryStoreQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    subject.value = query.subject ?? subject.value;
    type.value = query.type ?? (query.subject ? null : type.value);
    pageSize.value = query.pageSize && query.pageSize > 0
      ? query.pageSize
      : pageSize.value;
    page.value = query.page && query.page > 0 ? query.page : 1;
    try {
      const result = await fetchLibraryList({
        subject: subject.value,
        type: type.value ?? undefined,
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

  /** 翻页（服务端分页，越界自动收敛） */
  async function goPage(target: number): Promise<void> {
    const next = Math.min(
      Math.max(1, Math.floor(Number(target) || 1)),
      totalPages.value
    );
    if (next === page.value) return;
    await load({ page: next });
  }

  /**
   * 打开资料详情（同时是打开行为上报入口）。
   * 返回详情；失败时记录 error，并回退到调用方提供的列表项（若有）。
   */
  async function openMaterial(
    id: string | number,
    fallback: LibraryMaterial | null = null
  ): Promise<LibraryMaterialDetail | null> {
    error.value = null;
    try {
      const detail = await fetchLibraryDetail(id);
      selected.value = detail;
      const index = items.value.findIndex((item) => item.id === detail.id);
      if (index >= 0) {
        items.value[index] = { ...items.value[index], ...detail };
      }
      return detail;
    } catch (e) {
      error.value = errorMessage(e);
      selected.value = fallback
        ? ({ ...fallback, content: '', card_back: '', video_url: '' } as
            LibraryMaterialDetail)
        : null;
      return selected.value;
    }
  }

  /** 关闭详情 */
  function clearSelection(): void {
    selected.value = null;
  }

  /**
   * 上报学习进度（视频播放 / 标记已学）。
   * 进度只写后端；成功后同步本地条目，完成时刷新科目概览。
   */
  async function reportProgress(
    materialId: number,
    progressPercent = 0,
    completed = false
  ): Promise<boolean> {
    error.value = null;
    try {
      const result = await reportLibraryProgress({
        materialId,
        progressPercent,
        completed
      });
      const index = items.value.findIndex((item) => item.id === materialId);
      if (index >= 0) {
        items.value[index] = {
          ...items.value[index],
          progress_percent: result.progress_percent,
          is_studied: result.completed
        };
      }
      if (selected.value && selected.value.id === materialId) {
        selected.value = {
          ...selected.value,
          progress_percent: result.progress_percent,
          is_studied: result.completed
        };
      }
      if (result.completed) await loadProgressSummary();
      return true;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    }
  }

  /** 拉取当前科目学习进度概览；失败返回 null */
  async function loadProgressSummary(
    subjectKey: LibrarySubject = subject.value
  ): Promise<LibraryProgressSummary | null> {
    try {
      summary.value = await fetchLibraryProgressSummary(subjectKey);
      return summary.value;
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    }
  }

  /** 收藏切换；失败返回 null */
  async function toggleFavorite(
    materialId: number
  ): Promise<{ is_favorite: boolean } | null> {
    error.value = null;
    try {
      const result = await toggleLibraryFavorite(materialId);
      const index = items.value.findIndex((item) => item.id === materialId);
      if (index >= 0) {
        items.value[index] = {
          ...items.value[index],
          is_favorite: result.is_favorite
        };
      }
      if (selected.value && selected.value.id === materialId) {
        selected.value = {
          ...selected.value,
          is_favorite: result.is_favorite
        };
      }
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    }
  }

  /** 按类型取一组资料（供分栏页面使用，不覆盖主列表） */
  async function loadSection(
    sectionType: LibraryMaterialType,
    subjectKey: LibrarySubject = subject.value
  ): Promise<LibraryMaterial[]> {
    const result = await fetchLibraryList({
      subject: subjectKey,
      type: sectionType,
      page: 1,
      pageSize: 50
    });
    return result.items ?? [];
  }

  /** 重置为初始状态 */
  function reset(): void {
    const initial = createLibraryInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    subject.value = 'xingce';
    type.value = null;
    items.value = [];
    total.value = 0;
    page.value = 1;
    pageSize.value = 20;
    selected.value = null;
    summary.value = { studied: 0, total: 0, percentage: 0 };
  }

  return {
    loading,
    error,
    initialized,
    subject,
    type,
    items,
    total,
    page,
    pageSize,
    selected,
    summary,
    ready,
    isEmpty,
    totalPages,
    hasPrevPage,
    hasNextPage,
    reset,
    load,
    goPage,
    openMaterial,
    clearSelection,
    reportProgress,
    loadProgressSummary,
    toggleFavorite,
    loadSection
  };
});
