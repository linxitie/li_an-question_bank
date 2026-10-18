import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchLibraryList, libraryClient } from '../api';

vi.mock('@/services/api/client', () => ({
  apiClient: {
    request: vi.fn()
  }
}));

const mockedRequest = vi.mocked(libraryClient.request);

beforeEach(() => {
  vi.clearAllMocks();
});

describe('library api 列表参数拼装', () => {
  it('将 subject/type/pageSize 映射为后端参数（page_size）', async () => {
    mockedRequest.mockResolvedValue({
      data: { total: 0, items: [] }
    } as never);

    await fetchLibraryList({
      subject: 'xingce',
      type: 'video_advanced',
      page: 2,
      pageSize: 10
    });

    expect(mockedRequest).toHaveBeenCalledWith({
      url: '/api/materials',
      method: 'GET',
      baseURL: '',
      params: {
        subject: 'xingce',
        type: 'video_advanced',
        page: 2,
        page_size: 10
      }
    });
  });

  it('缺省页码与每页条数使用 1 / 20', async () => {
    mockedRequest.mockResolvedValue({
      data: { total: 0, items: [] }
    } as never);

    await fetchLibraryList({ subject: 'shenlun' });

    expect(mockedRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        params: {
          subject: 'shenlun',
          type: undefined,
          page: 1,
          page_size: 20
        }
      })
    );
  });
});
