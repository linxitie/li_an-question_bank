import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { EVENT_NAMES, emitEvent } from '@/stores/event-bus';
import { usePracticeStore } from '../store';
import {
  fetchPracticeRecords,
  fetchPracticeStats,
  submitPracticeAnswer
} from '../api';

vi.mock('../api', () => ({
  fetchPracticeRecords: vi.fn(),
  fetchPracticeStats: vi.fn(),
  fetchPracticeTypeSummary: vi.fn(),
  submitPracticeAnswer: vi.fn(),
  submitPracticeBatch: vi.fn(),
  submitQuickPractice: vi.fn()
}));

const mockedFetchRecords = vi.mocked(fetchPracticeRecords);
const mockedFetchStats = vi.mocked(fetchPracticeStats);
const mockedSubmitAnswer = vi.mocked(submitPracticeAnswer);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('practice store 加载状态', () => {
  it('加载成功后写入记录与日统计', async () => {
    mockedFetchRecords.mockResolvedValue({
      total: 1,
      items: [
        {
          record_id: 1,
          question_id: 10,
          subject_id: 1,
          type_id: 1,
          is_correct: true,
          time_spent: 30,
          user_answer: 'A',
          question_content: '题干',
          correct_answer: 'A',
          practice_date: '2026-10-18',
          practice_time: '2026-10-18 10:00:00',
          source: '快速练习'
        }
      ],
      daily_stats: [
        { date: '2026-10-18', total: 1, correct: 1, accuracy: 100 }
      ]
    });

    const store = usePracticeStore();
    await store.load({ limit: 10 });

    expect(mockedFetchRecords).toHaveBeenCalledWith({ limit: 10 });
    expect(store.records).toHaveLength(1);
    expect(store.dailyStats).toHaveLength(1);
    expect(store.total).toBe(1);
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('空态：加载完成但无记录', async () => {
    mockedFetchRecords.mockResolvedValue({
      total: 0,
      items: [],
      daily_stats: []
    });

    const store = usePracticeStore();
    await store.load();

    expect(store.records).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.initialized).toBe(true);
    expect(store.isEmpty).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('加载失败进入错误态并清空数据', async () => {
    mockedFetchRecords.mockRejectedValue(new Error('网络连接失败'));

    const store = usePracticeStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.records).toEqual([]);
  });

  it('统计加载失败写入 error', async () => {
    mockedFetchStats.mockRejectedValue(new Error('统计接口不可用'));

    const store = usePracticeStore();
    await store.loadStats();

    expect(store.stats).toBeNull();
    expect(store.error).toBe('统计接口不可用');
  });
});

describe('practice store 提交防护与结果', () => {
  it('提交中再次提交被直接拒绝，不重复发请求', async () => {
    const pending = deferred<Awaited<ReturnType<typeof submitPracticeAnswer>>>();
    mockedSubmitAnswer.mockReturnValue(pending.promise);

    const store = usePracticeStore();
    const first = store.submit({ question_id: 1, user_answer: 'A' });
    const second = await store.submit({ question_id: 2, user_answer: 'B' });

    expect(second).toBeNull();
    expect(mockedSubmitAnswer).toHaveBeenCalledTimes(1);
    expect(store.submitting).toBe(true);

    pending.resolve({
      status: 'ok',
      record_id: 9,
      has_new_wrong: true,
      wrong_question_stats: { new: 1, updated: 0, skipped: 0 }
    });
    const result = await first;

    expect(result?.record_id).toBe(9);
    expect(store.submitting).toBe(false);
    expect(store.lastResult?.record_id).toBe(9);
    expect(store.hasNewWrong).toBe(true);
  });

  it('提交失败写入 error 并复位 submitting', async () => {
    mockedSubmitAnswer.mockRejectedValue(new Error('提交失败'));

    const store = usePracticeStore();
    await expect(
      store.submit({ question_id: 1, user_answer: 'A' })
    ).rejects.toThrow('提交失败');

    expect(store.error).toBe('提交失败');
    expect(store.submitting).toBe(false);
    expect(store.lastResult).toBeNull();
  });
});

describe('practice store 事件驱动增量刷新', () => {
  it('订阅 wrong-questions:changed 后触发重新拉取', async () => {
    mockedFetchRecords.mockResolvedValue({
      total: 0,
      items: [],
      daily_stats: []
    });

    const store = usePracticeStore();
    await store.load();
    expect(mockedFetchRecords).toHaveBeenCalledTimes(1);

    const off = store.bindWrongQuestionsRefresh();
    emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, { source: 'practice' });

    await vi.waitFor(() => {
      expect(mockedFetchRecords).toHaveBeenCalledTimes(2);
    });

    off();
    emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, { source: 'practice' });
    await Promise.resolve();
    expect(mockedFetchRecords).toHaveBeenCalledTimes(2);
  });
});

describe('practice store 重置', () => {
  it('reset 清空业务状态并回到初始契约', async () => {
    mockedFetchRecords.mockResolvedValue({
      total: 1,
      items: [
        {
          record_id: 1,
          question_id: 10,
          subject_id: 1,
          type_id: 1,
          is_correct: true,
          time_spent: 30,
          user_answer: 'A',
          question_content: '题干',
          correct_answer: 'A',
          practice_date: '2026-10-18',
          practice_time: '2026-10-18 10:00:00',
          source: '快速练习'
        }
      ],
      daily_stats: []
    });

    const store = usePracticeStore();
    await store.load();
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.records).toEqual([]);
    expect(store.dailyStats).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.stats).toBeNull();
    expect(store.submitting).toBe(false);
    expect(store.lastResult).toBeNull();
  });
});
