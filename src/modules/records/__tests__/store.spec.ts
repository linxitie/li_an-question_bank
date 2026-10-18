import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { EVENT_NAMES, emitEvent } from '@/stores/event-bus';
import { useRecordsStore } from '../store';
import {
  fetchRecordsList,
  fetchRecordsStats,
  fetchRecordsTrend
} from '../api';

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    fetchRecordsList: vi.fn(),
    fetchRecordsStats: vi.fn(),
    fetchRecordsTrend: vi.fn()
  };
});

const mockedFetchList = vi.mocked(fetchRecordsList);
const mockedFetchStats = vi.mocked(fetchRecordsStats);
const mockedFetchTrend = vi.mocked(fetchRecordsTrend);

function makeRecord(id: number, overrides: Record<string, unknown> = {}) {
  return {
    record_id: id,
    question_id: 100 + id,
    subject_id: 1,
    type_id: 1,
    is_correct: true,
    time_spent: 30,
    user_answer: 'A',
    question_content: `题目 ${id}`,
    correct_answer: 'A',
    practice_date: '2026-10-18',
    practice_time: '2026-10-18 10:00:00',
    source: '顺序练习',
    ...overrides
  };
}

function mockList(
  items: ReturnType<typeof makeRecord>[],
  total = items.length
) {
  mockedFetchList.mockResolvedValue({
    total,
    items,
    dailyStats: [{ date: '2026-10-18', total: items.length, correct: 1, accuracy: 100 }]
  });
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  mockedFetchStats.mockResolvedValue({
    todayQuestions: 1,
    weeklyQuestions: 3,
    monthlyQuestions: 5,
    totalQuestions: 9,
    accuracyRate: 88.9,
    totalStudyHours: 1.5,
    streak: 2
  });
  mockedFetchTrend.mockResolvedValue([
    { date: '2026-10-18', questionsDone: 3, correctCount: 2, accuracy: 66.7, timeSpent: 90 }
  ]);
});

describe('records store 列表与状态', () => {
  it('加载成功写入记录、每日统计、总数与分页偏移', async () => {
    mockList([makeRecord(1), makeRecord(2)]);

    const store = useRecordsStore();
    await store.load();

    expect(mockedFetchList).toHaveBeenCalledWith({
      limit: 20,
      offset: 0,
      subjectId: undefined
    });
    expect(store.records).toHaveLength(2);
    expect(store.dailyStats).toHaveLength(1);
    expect(store.total).toBe(2);
    expect(store.offset).toBe(2);
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
    expect(store.hasMore).toBe(false);
  });

  it('空态可识别', async () => {
    mockList([]);

    const store = useRecordsStore();
    await store.load();

    expect(store.records).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.initialized).toBe(true);
    expect(store.isEmpty).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('错误写入 error 并清空列表', async () => {
    mockedFetchList.mockRejectedValue(new Error('记录接口失败'));

    const store = useRecordsStore();
    await store.load();

    expect(store.error).toBe('记录接口失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.records).toEqual([]);
  });

  it('拒绝并发的 loadMore 且不越过分页总数', async () => {
    mockList([makeRecord(1), makeRecord(2)], 2);

    const store = useRecordsStore();
    await store.load();
    await store.loadMore();

    expect(mockedFetchList).toHaveBeenCalledTimes(1);
  });
});

describe('records store 游标分页', () => {
  it('loadMore 以已加载条数为偏移并去重追加', async () => {
    mockList([makeRecord(1), makeRecord(2)], 3);

    const store = useRecordsStore();
    await store.load();
    mockList([makeRecord(2), makeRecord(3)], 3);
    await store.loadMore();

    expect(mockedFetchList).toHaveBeenLastCalledWith({
      limit: 20,
      offset: 2,
      subjectId: undefined
    });
    expect(store.records.map((r) => r.record_id)).toEqual([1, 2, 3]);
    expect(store.offset).toBe(4);
    expect(store.hasMore).toBe(false);
  });

  it('首页未拉满时仍继续发出下一页请求', async () => {
    mockList([makeRecord(1)], 5);

    const store = useRecordsStore();
    await store.load();
    mockList([makeRecord(2)], 5);
    await store.loadMore();

    expect(mockedFetchList).toHaveBeenCalledTimes(2);
    expect(store.hasMore).toBe(true);
  });
});

describe('records store 筛选与统计', () => {
  it('setFilters 将学科作为后端查询参数并重置分页', async () => {
    mockList([makeRecord(1)], 1);

    const store = useRecordsStore();
    await store.setFilters({ subjectId: 5 });

    expect(mockedFetchList).toHaveBeenCalledWith({
      limit: 20,
      offset: 0,
      subjectId: 5
    });
    expect(store.filters.subjectId).toBe(5);
  });

  it('对错、来源、关键字在已加载数据上过滤', async () => {
    mockList([
      makeRecord(1, { is_correct: true, source: '顺序练习', question_content: '治安管理处罚' }),
      makeRecord(2, { is_correct: false, source: '快速练习', question_content: '刑法总则' }),
      makeRecord(3, { is_correct: false, source: '快速练习', question_content: '治安管理处罚法' })
    ]);

    const store = useRecordsStore();
    await store.load();
    await store.setFilters({ isCorrect: false, source: '快速练习', keyword: '治安' });

    expect(store.filteredRecords.map((r) => r.record_id)).toEqual([3]);
    expect(store.isEmpty).toBe(false);
  });

  it('统计与趋势写入 store', async () => {
    mockList([]);

    const store = useRecordsStore();
    await store.loadStats();
    await store.loadTrend(30);

    expect(store.stats?.totalQuestions).toBe(9);
    expect(mockedFetchTrend).toHaveBeenCalledWith(30);
    expect(store.trendDays).toBe(30);
    expect(store.trend).toHaveLength(1);
  });

  it('统计失败写入 error 且保留空统计', async () => {
    mockedFetchStats.mockRejectedValue(new Error('统计失败'));

    const store = useRecordsStore();
    await store.loadStats();

    expect(store.stats).toBeNull();
    expect(store.error).toBe('统计失败');
  });
});

describe('records store 事件与重置', () => {
  it('订阅 wrong-questions:changed 后增量刷新', async () => {
    mockList([makeRecord(1)]);

    const store = useRecordsStore();
    const off = store.bindRecordsRefresh();
    emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, { source: 'practice' });
    await vi.waitFor(() => expect(mockedFetchList).toHaveBeenCalledTimes(1));

    off();
  });

  it('reset 恢复初始状态', async () => {
    mockList([makeRecord(1)]);

    const store = useRecordsStore();
    await store.load();
    await store.setFilters({ subjectId: 2 });
    store.reset();

    expect(store.records).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.offset).toBe(0);
    expect(store.filters).toEqual({});
    expect(store.initialized).toBe(false);
  });
});
