/**
 * 组卷与历年试卷（papers）域 API 封装。
 *
 * 后端组卷端点挂在 `/api/papers`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 * 学生端列表强制 `paper_type=PUBLISHED`，未发布试卷不出现在本域。
 */
import { apiClient } from '@/services/api/client';

export const papersClient = apiClient;

export interface PaperItem {
  paper_id: number;
  paper_name: string;
  paper_code: string;
  subject_id: number;
  subject_name?: string;
  exam_type?: string;
  paper_type?: string;
  question_count?: number;
  duration?: number;
  total_score?: number;
  difficulty?: number;
  create_time?: string | null;
  publish_time?: string | null;
}

export interface PapersListQuery {
  page?: number;
  pageSize?: number;
  subjectId?: number | null;
  examType?: string | null;
  keyword?: string | null;
}

export interface PapersListResult {
  items: PaperItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PapersFilters {
  subjectId?: number | null;
  examType?: string | null;
  keyword?: string | null;
}

interface PapersRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
  data?: unknown;
}

const DEFAULT_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 100;

async function request<T>(config: PapersRequestConfig): Promise<T> {
  const response = await papersClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

function normalizePageSize(size?: number): number {
  if (!size || size < 1) return DEFAULT_PAGE_SIZE;
  return Math.min(Math.floor(size), MAX_PAGE_SIZE);
}

export async function fetchPapersList(
  query: PapersListQuery = {}
): Promise<PapersListResult> {
  const page = query.page && query.page > 0 ? Math.floor(query.page) : 1;
  const pageSize = normalizePageSize(query.pageSize);
  const data = await request<{
    total?: number;
    page?: number;
    page_size?: number;
    items?: PaperItem[];
  }>({
    url: '/api/papers/list',
    method: 'GET',
    params: {
      page,
      page_size: pageSize,
      paper_type: 'PUBLISHED',
      subject_id: query.subjectId ?? undefined,
      exam_type: query.examType ?? undefined,
      keyword: query.keyword?.trim() || undefined
    }
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    pageSize: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}

export function fetchPapersDetail(
  id: string | number
): Promise<PaperItem> {
  return request<PaperItem>({
    url: `/api/papers/${id}`,
    method: 'GET'
  });
}

export async function refreshPapers(): Promise<void> {
  await fetchPapersList({ page: 1 });
}
