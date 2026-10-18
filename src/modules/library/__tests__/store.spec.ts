import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useLibraryStore } from '../store';
import {
  fetchLibraryDetail,
  fetchLibraryList,
  fetchLibraryProgressSummary,
  reportLibraryProgress,
  toggleLibraryFavorite,
  type LibraryMaterial,
  type LibraryMaterialDetail
} from '../api';

vi.mock('../api', () => ({
  fetchLibraryList: vi.fn(),
  fetchLibraryDetail: vi.fn(),
  fetchLibraryProgressSummary: vi.fn(),
  fetchLibraryFavorites: vi.fn(),
  reportLibraryProgress: vi.fn(),
  toggleLibraryFavorite: vi.fn(),
  refreshLibrary: vi.fn()
}));

const mockedFetchList = vi.mocked(fetchLibraryList);
const mockedFetchDetail = vi.mocked(fetchLibraryDetail);
const mockedFetchSummary = vi.mocked(fetchLibraryProgressSummary);
const mockedReportProgress = vi.mocked(reportLibraryProgress);
const mockedToggleFavorite = vi.mocked(toggleLibraryFavorite);

function makeItem(
  id: number,
  overrides: Partial<LibraryMaterial> = {}
): LibraryMaterial {
  return {
    id,
    subject: 'xingce',
    type: 'article',
    category: '备考指南',
    title: `资料 ${id}`,
    summary: '摘要',
    badge: null,
    cover_image: null,
    duration: 0,
    read_time: 5,
    difficulty: 1,
    view_count: 0,
    card_front: null,
    sort_order: id,
    is_studied: false,
    progress_percent: 0,
    is_favorite: false,
    ...overrides
  };
}

function makeDetail(
  id: number,
  overrides: Partial<LibraryMaterialDetail> = {}
): LibraryMaterialDetail {
  return {
    ...makeItem(id),
    content: '<p>正文</p>',
    card_back: '',
    video_url: '',
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('library store 列表与分页', () => {
  it('按科目/类型/页码/每页条数拼装列表参数', async () => {
    mockedFetchList.mockResolvedValue({ total: 0, items: [] });

    const store = useLibraryStore();
    await store.load({
      subject: 'xingce',
      type: 'article',
      page: 2,
      pageSize: 10
    });

    expect(mockedFetchList).toHaveBeenCalledWith({
      subject: 'xingce',
      type: 'article',
      page: 2,
      pageSize: 10
    });
    expect(store.subject).toBe('xingce');
    expect(store.type).toBe('article');
    expect(store.page).toBe(2);
    expect(store.pageSize).toBe(10);
  });

  it('加载成功后写入列表与总数，并标记已初始化', async () => {
    mockedFetchList.mockResolvedValue({
      total: 25,
      items: [makeItem(1), makeItem(2)]
    });

    const store = useLibraryStore();
    await store.load({ subject: 'xingce', pageSize: 10 });

    expect(store.items).toHaveLength(2);
    expect(store.total).toBe(25);
    expect(store.totalPages).toBe(3);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('空态：加载完成但无数据', async () => {
    mockedFetchList.mockResolvedValue({ total: 0, items: [] });

    const store = useLibraryStore();
    await store.load({ subject: 'shenlun' });

    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.totalPages).toBe(1);
    expect(store.isEmpty).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('错误态：加载失败写入 error 并清空数据', async () => {
    mockedFetchList.mockRejectedValue(new Error('网络连接失败'));

    const store = useLibraryStore();
    await store.load({ subject: 'xingce' });

    expect(store.error).toBe('网络连接失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
  });
});

describe('library store 详情与学习进度', () => {
  it('打开详情写入 selected 并同步列表条目', async () => {
    mockedFetchList.mockResolvedValue({ total: 1, items: [makeItem(7)] });
    mockedFetchDetail.mockResolvedValue(makeDetail(7));

    const store = useLibraryStore();
    await store.load({ subject: 'xingce' });
    const detail = await store.openMaterial(7);

    expect(mockedFetchDetail).toHaveBeenCalledWith(7);
    expect(detail?.content).toBe('<p>正文</p>');
    expect(store.selected?.id).toBe(7);
    expect((store.items[0] as LibraryMaterialDetail).content).toBe('<p>正文</p>');
  });

  it('详情失败时记录 error 并回退到列表项', async () => {
    const fallback = makeItem(8);
    mockedFetchDetail.mockRejectedValue(new Error('详情接口不可用'));

    const store = useLibraryStore();
    const detail = await store.openMaterial(8, fallback);

    expect(detail?.id).toBe(8);
    expect(store.error).toBe('详情接口不可用');
    expect(store.selected?.id).toBe(8);
  });

  it('上报进度写入后端并同步条目；完成后刷新概览', async () => {
    mockedFetchList.mockResolvedValue({ total: 1, items: [makeItem(9)] });
    mockedReportProgress.mockResolvedValue({
      ok: true,
      completed: true,
      progress_percent: 100
    });
    mockedFetchSummary.mockResolvedValue({
      studied: 1,
      total: 1,
      percentage: 100
    });

    const store = useLibraryStore();
    await store.load({ subject: 'xingce' });
    const ok = await store.reportProgress(9, 100, true);

    expect(ok).toBe(true);
    expect(mockedReportProgress).toHaveBeenCalledWith({
      materialId: 9,
      progressPercent: 100,
      completed: true
    });
    expect(store.items[0].is_studied).toBe(true);
    expect(store.items[0].progress_percent).toBe(100);
    expect(store.summary.percentage).toBe(100);
    expect(mockedFetchSummary).toHaveBeenCalledWith('xingce');
  });

  it('上报进度失败返回 false 并写入错误态', async () => {
    mockedReportProgress.mockRejectedValue(new Error('进度提交失败'));

    const store = useLibraryStore();
    const ok = await store.reportProgress(10, 50, false);

    expect(ok).toBe(false);
    expect(store.error).toBe('进度提交失败');
  });

  it('收藏切换同步条目与详情状态', async () => {
    mockedFetchList.mockResolvedValue({ total: 1, items: [makeItem(11)] });
    mockedFetchDetail.mockResolvedValue(makeDetail(11));
    mockedToggleFavorite.mockResolvedValue({ is_favorite: true });

    const store = useLibraryStore();
    await store.load({ subject: 'xingce' });
    await store.openMaterial(11);
    const result = await store.toggleFavorite(11);

    expect(mockedToggleFavorite).toHaveBeenCalledWith(11);
    expect(result).toEqual({ is_favorite: true });
    expect(store.items[0].is_favorite).toBe(true);
    expect(store.selected?.is_favorite).toBe(true);
  });
});

describe('library store 重置', () => {
  it('reset 清空业务状态并回到初始契约', async () => {
    mockedFetchList.mockResolvedValue({ total: 1, items: [makeItem(1)] });
    mockedFetchDetail.mockResolvedValue(makeDetail(1));

    const store = useLibraryStore();
    await store.load({ subject: 'shenlun', type: 'card', pageSize: 5 });
    await store.openMaterial(1);
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.subject).toBe('xingce');
    expect(store.type).toBeNull();
    expect(store.items).toEqual([]);
    expect(store.total).toBe(0);
    expect(store.page).toBe(1);
    expect(store.pageSize).toBe(20);
    expect(store.selected).toBeNull();
    expect(store.summary.percentage).toBe(0);
  });
});
