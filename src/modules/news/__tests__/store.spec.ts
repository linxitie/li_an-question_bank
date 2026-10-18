import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useNewsStore } from '../store';
import { fetchNewsDetail, fetchNewsList, type NewsItem } from '../api';

vi.mock('../api', () => ({
  fetchNewsList: vi.fn(),
  fetchNewsDetail: vi.fn(),
  fetchTodayNews: vi.fn(),
  refreshNews: vi.fn()
}));

const mockedFetchList = vi.mocked(fetchNewsList);
const mockedFetchDetail = vi.mocked(fetchNewsDetail);

function makeItem(id: number, overrides: Partial<NewsItem> = {}): NewsItem {
  return {
    id,
    title: `新闻 ${id}`,
    url: `https://example.com/news/${id}`,
    source: 'cpd',
    category: '理论',
    publish_date: '2026-10-18T08:00:00',
    summary: '摘要',
    content: '正文',
    images: [],
    is_favorited: false,
    is_read: false,
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('news store 加载与空态', () => {
  it('加载成功后写入列表与总数', async () => {
    mockedFetchList.mockResolvedValue({
      total: 2,
      items: [makeItem(1), makeItem(2)]
    });

    const store = useNewsStore();
    await store.load({ limit: 20 });

    expect(store.items).toHaveLength(2);
    expect(store.total).toBe(2);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('空态：加载完成但无数据', async () => {
    mockedFetchList.mockResolvedValue({ total: 0, items: [] });

    const store = useNewsStore();
    await store.load();

    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.totalPages).toBe(1);
    expect(store.isEmpty).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('错误态：加载失败写入 error 并清空数据', async () => {
    mockedFetchList.mockRejectedValue(new Error('网络连接失败'));

    const store = useNewsStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
  });
});

describe('news store 客户端分页', () => {
  const twentyFive = Array.from({ length: 25 }, (_, i) => makeItem(i + 1));

  it('按 pageSize 切页并计算总页数', async () => {
    mockedFetchList.mockResolvedValue({ total: 25, items: twentyFive });

    const store = useNewsStore();
    await store.load({ pageSize: 10 });

    expect(store.totalPages).toBe(3);
    expect(store.page).toBe(1);
    expect(store.pageItems).toHaveLength(10);
    expect(store.pageItems[0].id).toBe(1);
    expect(store.hasPrevPage).toBe(false);
    expect(store.hasNextPage).toBe(true);
  });

  it('翻页取对应区间，越界自动收敛', async () => {
    mockedFetchList.mockResolvedValue({ total: 25, items: twentyFive });

    const store = useNewsStore();
    await store.load({ pageSize: 10 });

    store.goPage(2);
    expect(store.page).toBe(2);
    expect(store.pageItems).toHaveLength(10);
    expect(store.pageItems[0].id).toBe(11);

    store.goPage(3);
    expect(store.pageItems).toHaveLength(5);
    expect(store.pageItems[0].id).toBe(21);
    expect(store.hasNextPage).toBe(false);

    store.goPage(99);
    expect(store.page).toBe(3);

    store.goPage(0);
    expect(store.page).toBe(1);
  });
});

describe('news store 详情与已读', () => {
  it('打开详情写入 selected，并用后端 is_read 更新列表项', async () => {
    mockedFetchList.mockResolvedValue({
      total: 1,
      items: [makeItem(7)]
    });
    mockedFetchDetail.mockResolvedValue(makeItem(7, { is_read: true }));

    const store = useNewsStore();
    await store.load();
    expect(store.isRead(7)).toBe(false);

    const article = await store.openArticle(7);

    expect(mockedFetchDetail).toHaveBeenCalledWith(7);
    expect(article?.id).toBe(7);
    expect(store.selected?.id).toBe(7);
    expect(store.isRead(7)).toBe(true);
  });

  it('详情失败时记录 error 并回退到列表项', async () => {
    const fallback = makeItem(8);
    mockedFetchDetail.mockRejectedValue(new Error('详情接口不可用'));

    const store = useNewsStore();
    const article = await store.openArticle(8, fallback);

    expect(article).toBe(fallback);
    expect(store.selected).toEqual(fallback);
    expect(store.error).toBe('详情接口不可用');
    expect(store.ready).toBe(false);
  });

  it('关闭详情清空 selected', async () => {
    mockedFetchDetail.mockResolvedValue(makeItem(9));

    const store = useNewsStore();
    await store.openArticle(9);
    store.clearSelection();

    expect(store.selected).toBeNull();
  });
});

describe('news store 重置', () => {
  it('reset 清空业务状态并回到初始契约', async () => {
    mockedFetchList.mockResolvedValue({ total: 1, items: [makeItem(1)] });
    mockedFetchDetail.mockResolvedValue(makeItem(1, { is_read: true }));

    const store = useNewsStore();
    await store.load({ pageSize: 5 });
    await store.openArticle(1);
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.page).toBe(1);
    expect(store.pageSize).toBe(20);
    expect(store.selected).toBeNull();
  });
});
