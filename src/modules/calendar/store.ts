/**
 * 考试日历（calendar）域 Store（P2-63）。
 *
 * 状态全部驻留内存，不写 localStorage。
 * 本域无事件进出：页面 `onMounted` 主动 `load()`，不依赖事件总线。
 *
 * 派生：
 *   - `monthGroups`：按月份分组的时间视图（月份升序，「日期待定」沉底）
 *   - `isEmpty`：加载完成且确实没有数据
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchCalendarList,
  type CalendarListQuery,
  type ExamCalendarItem
} from './api';

/** 公共状态骨架 */
export interface CalendarState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

/** 月份分组视图 */
export interface CalendarMonthGroup {
  month: number;
  label: string;
  items: ExamCalendarItem[];
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createCalendarInitialState(): CalendarState {
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

/** 解析条目所属月份：优先 month 字段，其次从 exam_date 提取；无法判断返回 0 */
function resolveMonth(item: ExamCalendarItem): number {
  if (
    typeof item.month === 'number' &&
    Number.isFinite(item.month) &&
    item.month >= 1 &&
    item.month <= 12
  ) {
    return item.month;
  }
  const matched = /^\d{4}-(\d{1,2})/.exec(item.exam_date ?? '');
  if (matched) {
    const month = Number(matched[1]);
    if (month >= 1 && month <= 12) return month;
  }
  return 0;
}

export const useCalendarStore = defineStore('calendar', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const items = ref<ExamCalendarItem[]>([]);
  const total = ref(0);
  const hasMore = ref(false);
  const province = ref('');

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 空态：加载完成、无错误、确实没有数据 */
  const isEmpty = computed(
    () => initialized.value && !loading.value && items.value.length === 0
  );

  /** 按月份分组（时间分组派生） */
  const monthGroups = computed<CalendarMonthGroup[]>(() => {
    const buckets = new Map<number, ExamCalendarItem[]>();
    for (const item of items.value) {
      const month = resolveMonth(item);
      const bucket = buckets.get(month);
      if (bucket) bucket.push(item);
      else buckets.set(month, [item]);
    }
    return Array.from(buckets.entries())
      .sort((a, b) => {
        if (a[0] === 0) return 1;
        if (b[0] === 0) return -1;
        return a[0] - b[0];
      })
      .map(([month, groupItems]) => ({
        month,
        label: month ? `${month}月` : '日期待定',
        items: groupItems
      }));
  });

  /**
   * 加载考试日历。
   * 成功写入 items / total / hasMore，失败进入错误态并清空数据。
   */
  async function load(query: CalendarListQuery = {}): Promise<void> {
    if (query.province !== undefined) province.value = query.province;

    loading.value = true;
    error.value = null;
    try {
      const result = await fetchCalendarList({
        limit: query.limit ?? 20,
        offset: query.offset ?? 0,
        province: province.value || undefined,
        signal: query.signal,
        ts: query.ts
      });
      items.value = result.items ?? [];
      total.value = result.total ?? items.value.length;
      hasMore.value = Boolean(result.has_more);
    } catch (e) {
      if (isAbortError(e)) return;
      error.value = errorMessage(e);
      items.value = [];
      total.value = 0;
      hasMore.value = false;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  /** 重置为初始状态 */
  function reset(): void {
    const initial = createCalendarInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    items.value = [];
    total.value = 0;
    hasMore.value = false;
    province.value = '';
  }

  return {
    loading,
    error,
    initialized,
    items,
    total,
    hasMore,
    province,
    ready,
    isEmpty,
    monthGroups,
    reset,
    load
  };
});
