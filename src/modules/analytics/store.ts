/**
 * 成绩分析（analytics）域 Store（P2-59）。
 *
 * `load()` 一次拉取趋势、掌握度、薄弱点三块快照；任一请求失败即记录错误并
 * 回到空态，避免半截数据被当成完整成绩分析展示。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchKnowledgeMastery,
  fetchScoreTrend,
  fetchWeakPoints,
  refreshAnalytics,
  type ExamType,
  type KnowledgeMasteryItem,
  type ScoreTrend,
  type ScoreTrendQuery,
  type WeakPoint
} from './api';

export interface AnalyticsState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createAnalyticsInitialState(): AnalyticsState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '成绩分析加载失败，请稍后重试';
}

const EMPTY_TREND: ScoreTrend = { examType: 'SELF_TEST', trend: [], avgScore: 0 };

export const useAnalyticsStore = defineStore('analytics', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const trend = ref<ScoreTrend>({ ...EMPTY_TREND });
  const mastery = ref<KnowledgeMasteryItem[]>([]);
  const weakPoints = ref<WeakPoint[]>([]);

  const ready = computed(() => initialized.value && error.value === null);
  const hasWeakPoints = computed(() => weakPoints.value.length > 0);
  const weakPointNames = computed(() =>
    weakPoints.value.map((item) => item.knowledge_point)
  );
  const weakestPoint = computed(() => weakPoints.value[0] ?? null);

  const masteryAverage = computed(() => {
    const total = mastery.value.reduce((sum, item) => sum + item.count, 0);
    if (total <= 0) return 0;
    const correct = mastery.value.reduce((sum, item) => sum + item.correct, 0);
    return Math.round((correct / total) * 1000) / 10;
  });

  const trendDelta = computed(() => {
    const scores = trend.value.trend.map((point) => point.accuracy);
    if (scores.length < 2) return 0;
    return Math.round((scores[scores.length - 1] - scores[0]) * 10) / 10;
  });

  const isEmpty = computed(
    () =>
      trend.value.trend.length === 0 &&
      mastery.value.length === 0 &&
      weakPoints.value.length === 0
  );

  async function load(query: ScoreTrendQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const result = await refreshAnalytics(query);
      trend.value = result.trend;
      mastery.value = result.mastery;
      weakPoints.value = result.weakPoints;
    } catch (e) {
      error.value = errorMessage(e);
      trend.value = { ...EMPTY_TREND };
      mastery.value = [];
      weakPoints.value = [];
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadSection(
    section: 'trend' | 'mastery' | 'weakPoints',
    examType: ExamType = 'SELF_TEST'
  ): Promise<void> {
    try {
      if (section === 'trend') {
        trend.value = await fetchScoreTrend({ examType });
      } else if (section === 'mastery') {
        mastery.value = await fetchKnowledgeMastery();
      } else {
        weakPoints.value = await fetchWeakPoints();
      }
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  function reset(): void {
    const initial = createAnalyticsInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    trend.value = { ...EMPTY_TREND };
    mastery.value = [];
    weakPoints.value = [];
  }

  return {
    loading,
    error,
    initialized,
    trend,
    mastery,
    weakPoints,
    ready,
    hasWeakPoints,
    weakPointNames,
    weakestPoint,
    masteryAverage,
    trendDelta,
    isEmpty,
    load,
    loadSection,
    reset
  };
});
