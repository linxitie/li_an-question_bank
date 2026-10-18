import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import {
  fetchKnowledgeMastery,
  fetchScoreTrend,
  fetchWeakPoints,
  refreshAnalytics,
  type KnowledgeMasteryItem,
  type ScoreTrend,
  type WeakPoint
} from '../api';
import { useAnalyticsStore } from '../store';

vi.mock('../api', () => ({
  fetchScoreTrend: vi.fn(),
  fetchKnowledgeMastery: vi.fn(),
  fetchWeakPoints: vi.fn(),
  refreshAnalytics: vi.fn()
}));

const mockedTrend = vi.mocked(fetchScoreTrend);
const mockedMastery = vi.mocked(fetchKnowledgeMastery);
const mockedWeakPoints = vi.mocked(fetchWeakPoints);
const mockedRefresh = vi.mocked(refreshAnalytics);

function makeTrend(overrides: Partial<ScoreTrend> = {}): ScoreTrend {
  return {
    examType: 'SELF_TEST',
    avgScore: 75,
    trend: [
      {
        index: 1,
        recordId: 1,
        paperName: '第一次自测',
        submitTime: '2026-10-01',
        totalScore: 60,
        maxScore: 100,
        accuracy: 60,
        durationUsed: 1200
      },
      {
        index: 2,
        recordId: 2,
        paperName: '第二次自测',
        submitTime: '2026-10-08',
        totalScore: 80,
        maxScore: 100,
        accuracy: 80,
        durationUsed: 1100
      }
    ],
    ...overrides
  };
}

function makeMastery(overrides: Partial<KnowledgeMasteryItem> = {}): KnowledgeMasteryItem {
  return {
    typeId: 1,
    typeName: '言语理解',
    count: 10,
    correct: 6,
    wrong: 4,
    accuracy: 60,
    minutes: 12,
    lastPracticeDate: '2026-10-08',
    ...overrides
  };
}

function makeWeakPoint(overrides: Partial<WeakPoint> = {}): WeakPoint {
  return {
    knowledge_point: '逻辑填空',
    accuracy: 40,
    total: 10,
    correct: 4,
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  mockedRefresh.mockResolvedValue({
    trend: makeTrend(),
    mastery: [makeMastery()],
    weakPoints: [makeWeakPoint()]
  });
  mockedTrend.mockResolvedValue(makeTrend());
  mockedMastery.mockResolvedValue([makeMastery()]);
  mockedWeakPoints.mockResolvedValue([makeWeakPoint()]);
});

describe('analytics store 加载与派生', () => {
  it('并行加载趋势/掌握度/薄弱点并派生指标', async () => {
    const store = useAnalyticsStore();
    await store.load({ examType: 'MOCK_EXAM', limit: 5 });

    expect(mockedRefresh).toHaveBeenCalledWith({ examType: 'MOCK_EXAM', limit: 5 });
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
    expect(store.hasWeakPoints).toBe(true);
    expect(store.weakPointNames).toEqual(['逻辑填空']);
    expect(store.weakestPoint?.accuracy).toBe(40);
    expect(store.masteryAverage).toBe(60);
    expect(store.trendDelta).toBe(20);
  });

  it('空数据时进入空态且不报错', async () => {
    mockedRefresh.mockResolvedValue({
      trend: { examType: 'SELF_TEST', trend: [], avgScore: 0 },
      mastery: [],
      weakPoints: []
    });
    const store = useAnalyticsStore();
    await store.load();

    expect(store.error).toBeNull();
    expect(store.isEmpty).toBe(true);
    expect(store.hasWeakPoints).toBe(false);
    expect(store.weakestPoint).toBeNull();
    expect(store.masteryAverage).toBe(0);
  });

  it('加载失败时记录错误并清空数据', async () => {
    mockedRefresh.mockRejectedValue(new Error('成绩服务不可用'));
    const store = useAnalyticsStore();
    await store.load();

    expect(store.error).toBe('成绩服务不可用');
    expect(store.ready).toBe(false);
    expect(store.isEmpty).toBe(true);
  });

  it('分区加载只刷新对应数据块', async () => {
    const store = useAnalyticsStore();
    await store.loadSection('weakPoints');

    expect(mockedWeakPoints).toHaveBeenCalledTimes(1);
    expect(mockedTrend).not.toHaveBeenCalled();
    expect(mockedMastery).not.toHaveBeenCalled();
    expect(store.weakPointNames).toEqual(['逻辑填空']);
  });

  it('reset 回到初始契约并清空业务数据', async () => {
    const store = useAnalyticsStore();
    await store.load();
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.isEmpty).toBe(true);
    expect(store.weakPoints).toEqual([]);
  });
});
