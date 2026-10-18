import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useCalendarStore } from '../store';
import { fetchCalendarList, type ExamCalendarItem } from '../api';
import { PUBLISHED_EVENTS, SUBSCRIBED_EVENTS } from '../events';

vi.mock('../api', () => ({
  fetchCalendarList: vi.fn(),
  fetchLatestExam: vi.fn(),
  refreshCalendar: vi.fn()
}));

const mockedFetchList = vi.mocked(fetchCalendarList);

function makeItem(id: number, overrides: Partial<ExamCalendarItem> = {}): ExamCalendarItem {
  return {
    id,
    title: `考试 ${id}`,
    month: 3,
    day: id,
    province: '全国',
    exam_type: '公务员',
    exam_format: '笔试',
    exam_date: '2026-03-15T00:00:00',
    registration_start: '2026-02-01T00:00:00',
    registration_end: '2026-02-20T00:00:00',
    url: '',
    description: '',
    content_html: '',
    recruitment_count: '',
    status: '报名中',
    status_color: '#10b981',
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('calendar store 列表与空态', () => {
  it('加载成功后写入列表、总数与 hasMore', async () => {
    mockedFetchList.mockResolvedValue({
      total: 2,
      items: [makeItem(1), makeItem(2)],
      has_more: true
    });

    const store = useCalendarStore();
    await store.load({ limit: 30 });

    expect(mockedFetchList).toHaveBeenCalledWith({
      limit: 30,
      offset: 0,
      province: undefined,
      signal: undefined,
      ts: undefined
    });
    expect(store.items).toHaveLength(2);
    expect(store.total).toBe(2);
    expect(store.hasMore).toBe(true);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('空态：加载完成但无数据', async () => {
    mockedFetchList.mockResolvedValue({ total: 0, items: [], has_more: false });

    const store = useCalendarStore();
    await store.load();

    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.hasMore).toBe(false);
    expect(store.isEmpty).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('错误态：加载失败写入 error 并清空数据', async () => {
    mockedFetchList.mockRejectedValue(new Error('网络连接失败'));

    const store = useCalendarStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
  });

  it('请求取消不写入错误态', async () => {
    const aborted = Object.assign(new Error('canceled'), { name: 'AbortError' });
    mockedFetchList.mockRejectedValue(aborted);

    const store = useCalendarStore();
    await store.load();

    expect(store.error).toBeNull();
    expect(store.items).toEqual([]);
  });
});

describe('calendar store 时间分组派生', () => {
  it('按月份升序分组，缺失月份用 exam_date 回退', async () => {
    mockedFetchList.mockResolvedValue({
      total: 4,
      items: [
        makeItem(1, { month: 10, exam_date: '2026-10-01T00:00:00' }),
        makeItem(2, { month: 3, exam_date: '2026-03-01T00:00:00' }),
        makeItem(3, { month: null, exam_date: '2026-03-20T00:00:00' }),
        makeItem(4, { month: null, exam_date: null })
      ],
      has_more: false
    });

    const store = useCalendarStore();
    await store.load();

    expect(store.monthGroups.map((group) => group.label)).toEqual([
      '3月',
      '10月',
      '日期待定'
    ]);
    expect(store.monthGroups[0].items.map((item) => item.id)).toEqual([2, 3]);
    expect(store.monthGroups[1].items.map((item) => item.id)).toEqual([1]);
    expect(store.monthGroups[2].items.map((item) => item.id)).toEqual([4]);
  });

  it('省份筛选透传到请求层', async () => {
    mockedFetchList.mockResolvedValue({ total: 0, items: [], has_more: false });

    const store = useCalendarStore();
    await store.load({ province: '江苏' });

    expect(store.province).toBe('江苏');
    expect(mockedFetchList).toHaveBeenCalledWith(
      expect.objectContaining({ province: '江苏' })
    );
  });
});

describe('calendar store 重置与事件契约', () => {
  it('reset 清空业务状态并回到初始契约', async () => {
    mockedFetchList.mockResolvedValue({
      total: 1,
      items: [makeItem(1)],
      has_more: true
    });

    const store = useCalendarStore();
    await store.load({ province: '江苏' });
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.hasMore).toBe(false);
    expect(store.province).toBe('');
    expect(store.monthGroups).toEqual([]);
  });

  it('events.ts 不导出任何事件常量（本域零事件）', () => {
    expect(Object.keys(PUBLISHED_EVENTS)).toEqual([]);
    expect(Object.keys(SUBSCRIBED_EVENTS)).toEqual([]);
  });
});
