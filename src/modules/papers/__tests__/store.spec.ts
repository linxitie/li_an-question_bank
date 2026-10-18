import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { clearAllEvents, emitEvent, EVENT_NAMES } from '@/stores/event-bus';
import { usePapersStore } from '../store';
import { fetchPapersList } from '../api';

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    fetchPapersList: vi.fn()
  };
});

const mockedFetchList = vi.mocked(fetchPapersList);

function makePaper(id: number, overrides: Record<string, unknown> = {}) {
  return {
    paper_id: id,
    paper_name: `试卷 ${id}`,
    paper_code: `PAPER-${id}`,
    subject_id: 1,
    subject_name: '行测',
    exam_type: 'SIMULATION',
    paper_type: 'PUBLISHED',
    question_count: 10,
    duration: 60,
    total_score: 100,
    difficulty: 3,
    create_time: '2026-10-18 10:00:00',
    publish_time: '2026-10-18 10:00:00',
    ...overrides
  };
}

function mockList(items: ReturnType<typeof makePaper>[], total = items.length, page = 1) {
  mockedFetchList.mockResolvedValue({
    total,
    page,
    pageSize: 20,
    items
  });
}

beforeEach(() => {
  setActivePinia(createPinia());
  clearAllEvents();
  vi.clearAllMocks();
});

describe('papers store 列表与状态', () => {
  it('加载成功写入试卷、总数与就绪状态', async () => {
    mockList([makePaper(1), makePaper(2)]);

    const store = usePapersStore();
    await store.load();

    expect(mockedFetchList).toHaveBeenCalledWith({
      page: 1,
      pageSize: 20,
      subjectId: undefined,
      examType: undefined,
      keyword: undefined
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

    const store = usePapersStore();
    await store.load();

    expect(store.items).toEqual([]);
    expect(store.initialized).toBe(true);
    expect(store.isEmpty).toBe(true);
  });

  it('请求失败写入 error 并清空列表', async () => {
    mockedFetchList.mockRejectedValue(new Error('试卷接口失败'));

    const store = usePapersStore();
    await store.load();

    expect(store.error).toBe('试卷接口失败');
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
  });

  it('loadMore 按页码叠加并去重', async () => {
    mockList([makePaper(1)], 3);
    const store = usePapersStore();
    await store.load();

    mockedFetchList.mockResolvedValueOnce({
      total: 3,
      page: 2,
      pageSize: 20,
      items: [makePaper(1), makePaper(2)]
    });
    await store.loadMore();

    expect(store.items.map((item) => item.paper_id)).toEqual([1, 2]);
    expect(mockedFetchList).toHaveBeenLastCalledWith({
      page: 2,
      pageSize: 20,
      subjectId: undefined,
      examType: undefined,
      keyword: undefined
    });
  });

  it('筛选条件并入请求参数', async () => {
    mockList([makePaper(1)]);
    const store = usePapersStore();
    await store.setFilters({ subjectId: 2, examType: 'FORMAL', keyword: '真题' });

    expect(mockedFetchList).toHaveBeenLastCalledWith({
      page: 1,
      pageSize: 20,
      subjectId: 2,
      examType: 'FORMAL',
      keyword: '真题'
    });
  });

  it('data-changed 事件触发增量刷新', async () => {
    mockList([makePaper(1)]);
    const store = usePapersStore();
    await store.load();
    const unbind = store.bindRefresh();

    mockList([makePaper(1), makePaper(2)]);
    emitEvent(EVENT_NAMES.PAPERS_DATA_CHANGED, {
      domain: 'exam',
      type: 'paper.published',
      id: 2,
      source: 'exam'
    });
    await Promise.resolve();
    await Promise.resolve();

    expect(store.items).toHaveLength(2);
    unbind();
  });

  it('reset 回到初始状态', async () => {
    mockList([makePaper(1)]);
    const store = usePapersStore();
    await store.load();

    store.reset();

    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.initialized).toBe(false);
    expect(store.error).toBeNull();
  });
});
