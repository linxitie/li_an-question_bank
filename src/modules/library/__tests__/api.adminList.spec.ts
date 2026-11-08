import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchAdminMaterialList, libraryClient } from '../api';

vi.mock('@/services/api/client', () => ({
  apiClient: { request: vi.fn() }
}));

const mockedRequest = vi.mocked(libraryClient.request);

beforeEach(() => {
  vi.clearAllMocks();
});

/**
 * A2：管理端列表的参数拼装。
 *
 * 要点：空字符串/空值**不下发**——后端对 `created_within` 做了
 * `pattern="^(7d|30d)$"` 校验，若前端把 `created_within=` 空值发过去会 422。
 */
describe('fetchAdminMaterialList 参数拼装', () => {
  it('默认只要 id_desc（2026-11-08 ID 方案 A：列表时间倒序）+ 第 1 页 20 条', async () => {
    mockedRequest.mockResolvedValue({ data: { total: 0, items: [] } } as never);

    await fetchAdminMaterialList();

    expect(mockedRequest).toHaveBeenCalledWith({
      url: '/api/materials/admin/list',
      method: 'GET',
      // 本域统一显式置空 baseURL（后端端点挂在 /api/materials，不走默认 /api/v1）
      baseURL: '',
      params: {
        subject: undefined,
        type: undefined,
        status: undefined,
        keyword: undefined,
        created_within: undefined,
        order: 'id_desc',
        publisher_id: undefined,
        page: 1,
        page_size: 20
      }
    });
  });

  it('显式 order 原样透传（含按上传时间排序）', async () => {
    mockedRequest.mockResolvedValue({ data: { total: 0, items: [] } } as never);

    await fetchAdminMaterialList({ order: 'created_desc' });

    const arg = mockedRequest.mock.calls[0][0] as unknown as { params: Record<string, unknown> };
    expect(arg.params.order).toBe('created_desc');
  });

  it('最近 7 天 + 正序 + 指定发布者', async () => {
    mockedRequest.mockResolvedValue({ data: { total: 0, items: [] } } as never);

    await fetchAdminMaterialList({
      created_within: '7d',
      order: 'created_asc',
      publisher_id: 3,
      subject: 'gongzhuan',
      type: 'paper',
      status: 1,
      keyword: '国考',
      page: 2,
      pageSize: 50
    });

    const arg = mockedRequest.mock.calls[0][0] as unknown as { params: Record<string, unknown> };
    expect(arg.params.created_within).toBe('7d');
    expect(arg.params.order).toBe('created_asc');
    expect(arg.params.publisher_id).toBe(3);
    expect(arg.params.subject).toBe('gongzhuan');
    expect(arg.params.type).toBe('paper');
    expect(arg.params.status).toBe(1);
    expect(arg.params.keyword).toBe('国考');
    expect(arg.params.page).toBe(2);
    expect(arg.params.page_size).toBe(50);
  });

  it('空字符串筛选不下发（避免 422）', async () => {
    mockedRequest.mockResolvedValue({ data: { total: 0, items: [] } } as never);

    await fetchAdminMaterialList({ created_within: '', subject: '', type: '', keyword: '' });

    const arg = mockedRequest.mock.calls[0][0] as unknown as { params: Record<string, unknown> };
    expect(arg.params.created_within).toBeUndefined();
    expect(arg.params.subject).toBeUndefined();
    expect(arg.params.type).toBeUndefined();
    expect(arg.params.keyword).toBeUndefined();
  });

  it('原样返回后端的 created_at / publisher（不在前端重算）', async () => {
    mockedRequest.mockResolvedValue({
      data: {
        total: 1,
        items: [
          {
            id: 115,
            created_at: '2026-11-05T21:12:00+08:00',
            publisher: { id: 2, name: 'cbrycc', role: 'admin', role_label: '管理员' }
          }
        ]
      }
    } as never);

    const res = await fetchAdminMaterialList({ created_within: '7d' });
    expect(res.items[0].created_at).toBe('2026-11-05T21:12:00+08:00');
    expect(res.items[0].publisher?.role_label).toBe('管理员');
  });
});
