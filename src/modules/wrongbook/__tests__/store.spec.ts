import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { clearAllEvents, emitEvent, EVENT_NAMES } from '@/stores/event-bus';
import { useWrongbookStore } from '../store';
import {
  chopWrongbook,
  fetchWrongbookList,
  updateWrongbookMastery
} from '../api';

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    fetchWrongbookList: vi.fn(),
    updateWrongbookMastery: vi.fn(),
    chopWrongbook: vi.fn()
  };
});

const mockedFetchList = vi.mocked(fetchWrongbookList);
const mockedMastery = vi.mocked(updateWrongbookMastery);
const mockedChop = vi.mocked(chopWrongbook);

function makeWrongQuestion(id: number, overrides: Record<string, unknown> = {}) {
  return {
    wrong_id: id,
    question_id: 100 + id,
    question_content: `错题 ${id}`,
    question_type_detail: '单选题',
    options: ['A. 甲', 'B. 乙'],
    answer: 'A',
    user_answer: 'B',
    answer_analysis: '解析',
    subject_id: 1,
    subject_name: '行测',
    sub_category: '治安管理',
    error_count: 2,
    mastery_level: 'UNMASTERED',
    is_cut: false,
    accuracy_rate: 0,
    review_count: 2,
    last_review_time: null,
    add_time: '2026-10-18 10:00:00',
    note: null,
    ...overrides
  };
}

function mockList(items: ReturnType<typeof makeWrongQuestion>[], total = items.length) {
  mockedFetchList.mockResolvedValue({
    total,
    page: 1,
    pageSize: 20,
    items
  });
}

beforeEach(() => {
  setActivePinia(createPinia());
  clearAllEvents();
  vi.clearAllMocks();
  mockedMastery.mockResolvedValue({ mastery_level: 'MASTERED' });
  mockedChop.mockResolvedValue({ wrong_id: 1 });
});

describe('wrongbook store 列表与状态', () => {
  it('加载成功写入错题、总数与就绪状态', async () => {
    mockList([makeWrongQuestion(1), makeWrongQuestion(2)]);

    const store = useWrongbookStore();
    await store.load();

    expect(mockedFetchList).toHaveBeenCalledWith({
      page: 1,
      pageSize: 20,
      subjectId: undefined
    });
    expect(store.items).toHaveLength(2);
    expect(store.total).toBe(2);
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
    expect(store.hasMore).toBe(false);
  });

  it('空列表可识别为空态', async () => {
    mockList([]);

    const store = useWrongbookStore();
    await store.load();

    expect(store.items).toEqual([]);
    expect(store.initialized).toBe(true);
    expect(store.isEmpty).toBe(true);
  });

  it('请求失败写入 error 并清空列表', async () => {
    mockedFetchList.mockRejectedValue(new Error('错题接口失败'));

    const store = useWrongbookStore();
    await store.load();

    expect(store.error).toBe('错题接口失败');
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
  });

  it('loadMore 以页码叠加并按 wrong_id 去重', async () => {
    mockList([makeWrongQuestion(1)], 3);

    const store = useWrongbookStore();
    await store.load();
    mockedFetchList.mockResolvedValueOnce({
      total: 3,
      page: 2,
      pageSize: 20,
      items: [makeWrongQuestion(1), makeWrongQuestion(2)]
    });
    await store.loadMore();

    expect(store.items.map((item) => item.wrong_id)).toEqual([1, 2]);
    expect(store.hasMore).toBe(true);
  });
});

describe('wrongbook store 掌握度筛选', () => {
  it('setFilters 将学科作为后端参数并把掌握度留在本地筛选', async () => {
    mockList([
      makeWrongQuestion(1, { subject_id: 3, mastery_level: 'UNMASTERED' }),
      makeWrongQuestion(2, { subject_id: 3, mastery_level: 'MASTERED' })
    ]);

    const store = useWrongbookStore();
    await store.setFilters({ subjectId: 3, masteryLevel: 'UNMASTERED' });

    expect(mockedFetchList).toHaveBeenLastCalledWith({
      page: 1,
      pageSize: 20,
      subjectId: 3
    });
    expect(store.filters).toEqual({ subjectId: 3, masteryLevel: 'UNMASTERED' });
    expect(store.visibleItems.map((item) => item.wrong_id)).toEqual([1]);
  });

  it('关键字在题干与子科目上过滤', async () => {
    mockList([
      makeWrongQuestion(1, { question_content: '治安管理处罚', sub_category: '治安' }),
      makeWrongQuestion(2, { question_content: '刑法总则', sub_category: '刑法' })
    ]);

    const store = useWrongbookStore();
    await store.load();
    await store.setFilters({ keyword: '治安' });

    expect(store.visibleItems.map((item) => item.wrong_id)).toEqual([1]);
  });
});

describe('wrongbook store 掌握状态流转', () => {
  it('markMastered 调用接口并本地流转为已掌握', async () => {
    mockList([makeWrongQuestion(1)]);

    const store = useWrongbookStore();
    await store.load();
    await store.markMastered(1);

    expect(mockedMastery).toHaveBeenCalledWith(1, 'MASTERED');
    expect(store.items[0].mastery_level).toBe('MASTERED');
    expect(store.items[0].is_cut).toBe(true);
  });

  it('chop 调用斩题接口并标记已斩题', async () => {
    mockList([makeWrongQuestion(1)]);

    const store = useWrongbookStore();
    await store.load();
    await store.chop(1);

    expect(mockedChop).toHaveBeenCalledWith(1);
    expect(store.items[0].is_cut).toBe(true);
  });

  it('流转失败写入 error 并抛出', async () => {
    mockList([makeWrongQuestion(1)]);
    mockedMastery.mockRejectedValue(new Error('流转失败'));

    const store = useWrongbookStore();
    await store.load();

    await expect(store.markMastered(1)).rejects.toThrow('流转失败');
    expect(store.error).toBe('流转失败');
  });

  it('retryTarget 指向错题复习页并携带 wrong_id', async () => {
    const store = useWrongbookStore();
    const target = store.retryTarget(makeWrongQuestion(7));

    expect(target.path).toBe('/mobile/wrong-review');
    expect(target.query).toEqual({ wrong_id: 7, subject_id: 1 });
  });
});

describe('wrongbook store 事件增量刷新', () => {
  it('外部事件触发增量拉取且保留筛选项', async () => {
    mockList([makeWrongQuestion(1)]);

    const store = useWrongbookStore();
    await store.setFilters({ subjectId: 3, masteryLevel: 'UNMASTERED' });
    const off = store.bindRefresh();
    mockedFetchList.mockClear();

    emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, { source: 'practice' });
    await vi.waitFor(() => expect(mockedFetchList).toHaveBeenCalledTimes(1));

    expect(mockedFetchList).toHaveBeenCalledWith({
      page: 1,
      pageSize: 20,
      subjectId: 3
    });
    expect(store.filters).toEqual({ subjectId: 3, masteryLevel: 'UNMASTERED' });
    off();
  });

  it('重复事件在同一轮刷新内只拉取一次', async () => {
    mockList([makeWrongQuestion(1)]);

    const store = useWrongbookStore();
    await store.load();
    const off = store.bindRefresh();
    await vi.waitFor(() =>
      expect(mockedFetchList).toHaveBeenCalledTimes(1)
    );
    mockedFetchList.mockClear();

    emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, { source: 'practice' });
    emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, { source: 'practice' });
    await vi.waitFor(() => expect(mockedFetchList).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockedFetchList).toHaveBeenCalledTimes(1);
    off();
  });

  it('本域自身发布的事件不触发重复拉取', async () => {
    mockList([makeWrongQuestion(1)]);

    const store = useWrongbookStore();
    await store.load();
    const off = store.bindRefresh();
    mockedFetchList.mockClear();

    await store.markMastered(1);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockedFetchList).not.toHaveBeenCalled();
    off();
  });

  it('reset 恢复初始状态', async () => {
    mockList([makeWrongQuestion(1)]);

    const store = useWrongbookStore();
    await store.load();
    await store.setFilters({ subjectId: 2 });
    store.reset();

    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.filters).toEqual({});
    expect(store.initialized).toBe(false);
  });
});
