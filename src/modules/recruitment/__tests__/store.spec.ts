import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useRecruitmentStore } from '../store';
import {
  fetchRecruitmentDetail,
  fetchRecruitmentList,
  type RecruitmentItem
} from '../api';
import { PUBLISHED_EVENTS, SUBSCRIBED_EVENTS } from '../events';

vi.mock('../api', () => ({
  fetchRecruitmentList: vi.fn(),
  fetchRecruitmentDetail: vi.fn(),
  fetchRecruitmentCategories: vi.fn(),
  refreshRecruitment: vi.fn()
}));

const mockedFetchList = vi.mocked(fetchRecruitmentList);
const mockedFetchDetail = vi.mocked(fetchRecruitmentDetail);

function makeItem(id: number, overrides: Partial<RecruitmentItem> = {}): RecruitmentItem {
  return {
    id,
    title: `招考 ${id}`,
    url: '',
    category: '国考省考',
    organization: '某单位',
    region: '江苏',
    registration_start: '2026-10-01',
    registration_end: '2026-10-20',
    deadline: '2026-10-20',
    tag: '正在报名',
    tag_color: '',
    status_label: '正在报名',
    status_color: '#10b981',
    content: '正文',
    content_html: '<p>正文</p>',
    images: [],
    exam_format: '笔试',
    contact_info: '025-00000000',
    requirements: '',
    view_count: 0,
    publish_date: '2026-10-01',
    create_time: '2026-10-01T08:00:00',
    ...overrides
  };
}

const META = {
  last_updated: '2026-10-18T08:00:00',
  latest_publish_date: '2026-10-18',
  total: 2,
  source: 'rszk.net',
  sort_by: 'publish_date'
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('recruitment store 列表与分类筛选', () => {
  it('加载全部分类后默认选中第一个分类', async () => {
    mockedFetchList.mockResolvedValue({
      categories: ['国考省考', '教师招聘'],
      items: {
        国考省考: [makeItem(1)],
        教师招聘: [makeItem(2, { category: '教师招聘' })]
      },
      meta: META
    });

    const store = useRecruitmentStore();
    await store.load({ limit: 20 });

    expect(mockedFetchList).toHaveBeenCalledWith({
      limit: 20,
      category: undefined,
      signal: undefined,
      ts: undefined
    });
    expect(store.categories).toEqual(['国考省考', '教师招聘']);
    expect(store.categoryCount).toBe(2);
    expect(store.activeCategory).toBe('国考省考');
    expect(store.currentItems.map((item) => item.id)).toEqual([1]);
    expect(store.total).toBe(2);
    expect(store.meta?.source).toBe('rszk.net');
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('setCategory 本地切换分类，不重新请求', async () => {
    mockedFetchList.mockResolvedValue({
      categories: ['国考省考', '教师招聘'],
      items: {
        国考省考: [makeItem(1)],
        教师招聘: [makeItem(2, { category: '教师招聘' })]
      },
      meta: META
    });

    const store = useRecruitmentStore();
    await store.load();
    store.setCategory('教师招聘');

    expect(store.activeCategory).toBe('教师招聘');
    expect(store.currentItems.map((item) => item.id)).toEqual([2]);
    expect(mockedFetchList).toHaveBeenCalledTimes(1);
  });

  it('按分类请求时直接选中该分类', async () => {
    mockedFetchList.mockResolvedValue({
      categories: ['国考省考', '教师招聘'],
      items: { 教师招聘: [makeItem(5, { category: '教师招聘' })] },
      meta: META
    });

    const store = useRecruitmentStore();
    await store.load({ category: '教师招聘' });

    expect(mockedFetchList).toHaveBeenCalledWith(
      expect.objectContaining({ category: '教师招聘' })
    );
    expect(store.activeCategory).toBe('教师招聘');
    expect(store.currentItems).toHaveLength(1);
  });

  it('空态：加载完成但当前分类无数据', async () => {
    mockedFetchList.mockResolvedValue({
      categories: ['三支一扶'],
      items: { 三支一扶: [] },
      meta: { ...META, total: 0 }
    });

    const store = useRecruitmentStore();
    await store.load();

    expect(store.currentItems).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.isEmpty).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('错误态：加载失败写入 error 并清空数据', async () => {
    mockedFetchList.mockRejectedValue(new Error('网络连接失败'));

    const store = useRecruitmentStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.categories).toEqual([]);
    expect(store.items).toEqual({});
    expect(store.activeCategory).toBe('');
  });

  it('请求取消不写入错误态', async () => {
    const aborted = Object.assign(new Error('canceled'), { name: 'AbortError' });
    mockedFetchList.mockRejectedValue(aborted);

    const store = useRecruitmentStore();
    await store.load();

    expect(store.error).toBeNull();
  });
});

describe('recruitment store 详情', () => {
  it('打开详情写入 detail 并同步列表条目', async () => {
    mockedFetchList.mockResolvedValue({
      categories: ['国考省考'],
      items: { 国考省考: [makeItem(7, { view_count: 0 })] },
      meta: META
    });
    mockedFetchDetail.mockResolvedValue(makeItem(7, { view_count: 1 }));

    const store = useRecruitmentStore();
    await store.load();
    const opened = await store.openDetail(7);

    expect(mockedFetchDetail).toHaveBeenCalledWith(7);
    expect(opened?.id).toBe(7);
    expect(store.detail?.view_count).toBe(1);
    expect(store.currentItems[0].view_count).toBe(1);
    expect(store.detailLoading).toBe(false);

    store.clearDetail();
    expect(store.detail).toBeNull();
  });

  it('详情失败时回退到列表项并记录 error', async () => {
    const fallback = makeItem(8);
    mockedFetchDetail.mockRejectedValue(new Error('招考信息不存在'));

    const store = useRecruitmentStore();
    const opened = await store.openDetail(8, fallback);

    expect(opened).toBe(fallback);
    expect(store.detail).toEqual(fallback);
    expect(store.error).toBe('招考信息不存在');
  });
});

describe('recruitment store 重置与事件契约', () => {
  it('reset 清空业务状态并回到初始契约', async () => {
    mockedFetchList.mockResolvedValue({
      categories: ['国考省考'],
      items: { 国考省考: [makeItem(1)] },
      meta: META
    });

    const store = useRecruitmentStore();
    await store.load();
    await store.openDetail(1);
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.categories).toEqual([]);
    expect(store.items).toEqual({});
    expect(store.activeCategory).toBe('');
    expect(store.meta).toBeNull();
    expect(store.detail).toBeNull();
    expect(store.total).toBe(0);
  });

  it('events.ts 不导出任何事件常量（本域零事件）', () => {
    expect(Object.keys(PUBLISHED_EVENTS)).toEqual([]);
    expect(Object.keys(SUBSCRIBED_EVENTS)).toEqual([]);
  });
});
