/**
 * 题库浏览（catalog）域 Store 单测（P2-75）。
 *
 * 覆盖：加载成功 / 空态 / 错误态 / 服务端分页与越界收敛 / 详情缓存。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useCatalogStore } from '../store';
import {
  fetchCatalogDetail,
  fetchCatalogList,
  type CatalogQuestion
} from '../api';

vi.mock('../api', () => ({
  fetchCatalogList: vi.fn(),
  fetchCatalogDetail: vi.fn(),
  refreshCatalog: vi.fn()
}));

const mockedFetchList = vi.mocked(fetchCatalogList);
const mockedFetchDetail = vi.mocked(fetchCatalogDetail);

function makeQuestion(id: number, overrides: Partial<CatalogQuestion> = {}): CatalogQuestion {
  return {
    question_id: id,
    subject_id: 1,
    type_id: 1,
    question_content: `题目 ${id}`,
    options: [
      { key: 'A', value: '选项 A' },
      { key: 'B', value: '选项 B' }
    ],
    answer: 'A',
    answer_analysis: '解析',
    point_id: null,
    difficulty: 3,
    score: 1,
    year: 2024,
    source: '真题',
    tags: '测试',
    video_url: null,
    accuracy_rate: 0,
    exam_frequency: 0,
    creator_id: 1,
    auditor_id: null,
    audit_status: 1,
    create_time: '2026-10-18T08:00:00',
    update_time: null,
    status: 1,
    version: 1,
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('catalog store 加载与空态', () => {
  it('加载成功后写入列表与总数', async () => {
    mockedFetchList.mockResolvedValue({
      total: 2,
      page: 1,
      page_size: 10,
      items: [makeQuestion(1), makeQuestion(2)]
    });

    const store = useCatalogStore();
    await store.load();

    expect(store.items).toHaveLength(2);
    expect(store.total).toBe(2);
    expect(store.page).toBe(1);
    expect(store.pageSize).toBe(10);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('空态：加载完成但无数据', async () => {
    mockedFetchList.mockResolvedValue({ total: 0, page: 1, page_size: 10, items: [] });

    const store = useCatalogStore();
    await store.load({ keyword: '不存在的题' });

    expect(store.items).toHaveLength(0);
    expect(store.total).toBe(0);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(true);
    expect(store.filters.keyword).toBe('不存在的题');
  });

  it('错误态：请求失败写入 error 并清空列表', async () => {
    mockedFetchList.mockRejectedValue(new Error('网络异常'));

    const store = useCatalogStore();
    await store.load();

    expect(store.error).toBe('网络异常');
    expect(store.items).toHaveLength(0);
    expect(store.total).toBe(0);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.isEmpty).toBe(true);
  });
});

describe('catalog store 分页', () => {
  it('按 page / pageSize 请求，并计算分页派生值', async () => {
    mockedFetchList.mockResolvedValue({
      total: 45,
      page: 2,
      page_size: 20,
      items: [makeQuestion(21)]
    });

    const store = useCatalogStore();
    await store.load({ page: 2, pageSize: 20 });

    expect(mockedFetchList).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, pageSize: 20 })
    );
    expect(store.page).toBe(2);
    expect(store.totalPages).toBe(3);
    expect(store.hasPrevPage).toBe(true);
    expect(store.hasNextPage).toBe(true);
  });

  it('goPage 翻页并下发目标页', async () => {
    mockedFetchList.mockResolvedValue({
      total: 45,
      page: 1,
      page_size: 20,
      items: [makeQuestion(1)]
    });

    const store = useCatalogStore();
    await store.load({ page: 1, pageSize: 20 });
    expect(store.totalPages).toBe(3);

    mockedFetchList.mockClear();
    await store.goPage(3);

    expect(mockedFetchList).toHaveBeenCalledWith(
      expect.objectContaining({ page: 3, pageSize: 20 })
    );
    expect(store.page).toBe(3);
  });

  it('goPage 越界时收敛到最后一页', async () => {
    mockedFetchList.mockResolvedValue({
      total: 25,
      page: 1,
      page_size: 20,
      items: [makeQuestion(1)]
    });

    const store = useCatalogStore();
    await store.load({ page: 1, pageSize: 20 });
    mockedFetchList.mockClear();

    await store.goPage(99);

    expect(mockedFetchList).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2 })
    );
  });

  it('pageSize 超过后端上限时收敛到 100', async () => {
    mockedFetchList.mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 100,
      items: []
    });

    const store = useCatalogStore();
    await store.load({ pageSize: 500 });

    expect(store.pageSize).toBe(100);
    expect(mockedFetchList).toHaveBeenCalledWith(
      expect.objectContaining({ pageSize: 100 })
    );
  });
});

describe('catalog store 详情', () => {
  it('openQuestion 拉取详情并回填列表缓存', async () => {
    mockedFetchList.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 10,
      items: [makeQuestion(7, { answer_analysis: null })]
    });
    mockedFetchDetail.mockResolvedValue(
      makeQuestion(7, { answer_analysis: '完整解析' })
    );

    const store = useCatalogStore();
    await store.load();
    const detail = await store.openQuestion(7);

    expect(detail?.answer_analysis).toBe('完整解析');
    expect(store.selected?.question_id).toBe(7);
    expect(store.items[0].answer_analysis).toBe('完整解析');
  });

  it('openQuestion 失败时返回 null 并记录错误', async () => {
    mockedFetchDetail.mockRejectedValue(new Error('题目不存在'));

    const store = useCatalogStore();
    const detail = await store.openQuestion(404);

    expect(detail).toBeNull();
    expect(store.selected).toBeNull();
    expect(store.error).toBe('题目不存在');
  });
});
