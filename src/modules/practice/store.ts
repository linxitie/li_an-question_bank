/**
 * 答题练习（practice）域 Store。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * records / dailyStats / stats / submitting / lastResult 为本域业务状态。
 * 不写 localStorage；事件只做增量刷新加速，页面 onMounted 仍须主动 load()。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { EVENT_NAMES, onEvent } from '@/stores/event-bus';
import {
  fetchPracticeRecords,
  fetchPracticeStats,
  fetchPracticeTypeSummary,
  submitPracticeAnswer,
  submitPracticeBatch,
  submitQuickPractice,
  type PracticeDailyStat,
  type PracticeRecordItem,
  type PracticeRecordsQuery,
  type PracticeStatsResult,
  type PracticeSubmitItem,
  type PracticeSubmitResult,
  type PracticeTypeSummaryItem
} from './api';

export interface PracticeState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createPracticeInitialState(): PracticeState {
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

export const usePracticeStore = defineStore('practice', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const records = ref<PracticeRecordItem[]>([]);
  const dailyStats = ref<PracticeDailyStat[]>([]);
  const total = ref(0);
  const stats = ref<PracticeStatsResult | null>(null);
  const typeSummary = ref<PracticeTypeSummaryItem[]>([]);
  const submitting = ref(false);
  const lastResult = ref<PracticeSubmitResult | null>(null);

  const ready = computed(() => initialized.value && error.value === null);
  const isEmpty = computed(
    () => initialized.value && !loading.value && records.value.length === 0
  );
  const hasNewWrong = computed(() => Boolean(lastResult.value?.has_new_wrong));

  async function load(query: PracticeRecordsQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const result = await fetchPracticeRecords(query);
      records.value = result.items ?? [];
      dailyStats.value = result.daily_stats ?? [];
      total.value = result.total ?? 0;
    } catch (e) {
      error.value = errorMessage(e);
      records.value = [];
      dailyStats.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadStats(): Promise<void> {
    try {
      stats.value = await fetchPracticeStats();
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function loadTypeSummary(): Promise<void> {
    try {
      const result = await fetchPracticeTypeSummary();
      typeSummary.value = result.types ?? [];
    } catch (e) {
      error.value = errorMessage(e);
      typeSummary.value = [];
    }
  }

  async function submit(
    item: PracticeSubmitItem & { session_id?: string }
  ): Promise<PracticeSubmitResult | null> {
    if (submitting.value) return null;
    submitting.value = true;
    error.value = null;
    try {
      const result = await submitPracticeAnswer(item);
      lastResult.value = result;
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      submitting.value = false;
    }
  }

  async function submitBatch(
    items: PracticeSubmitItem[],
    options: { subjectId?: number; sessionId?: string; source?: string } = {}
  ): Promise<PracticeSubmitResult | null> {
    if (submitting.value) return null;
    submitting.value = true;
    error.value = null;
    try {
      const result = await submitPracticeBatch(items, options);
      lastResult.value = result;
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      submitting.value = false;
    }
  }

  async function submitQuick(
    items: PracticeSubmitItem[],
    options: { subjectId?: number; sessionId?: string } = {}
  ): Promise<PracticeSubmitResult | null> {
    if (submitting.value) return null;
    submitting.value = true;
    error.value = null;
    try {
      const result = await submitQuickPractice(items, options);
      lastResult.value = result;
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      submitting.value = false;
    }
  }

  function bindWrongQuestionsRefresh(): () => void {
    return onEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, () => {
      void load();
    });
  }

  function reset(): void {
    const initial = createPracticeInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    records.value = [];
    dailyStats.value = [];
    total.value = 0;
    stats.value = null;
    typeSummary.value = [];
    submitting.value = false;
    lastResult.value = null;
  }

  return {
    loading,
    error,
    initialized,
    ready,
    records,
    dailyStats,
    total,
    stats,
    typeSummary,
    submitting,
    lastResult,
    isEmpty,
    hasNewWrong,
    reset,
    load,
    loadStats,
    loadTypeSummary,
    submit,
    submitBatch,
    submitQuick,
    bindWrongQuestionsRefresh
  };
});
