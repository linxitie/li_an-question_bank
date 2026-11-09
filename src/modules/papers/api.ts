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

/**
 * 考试状态块（P2，2026-11-09 补到列表）：与资料页 `paper.exam` **同一份契约**
 * （后端 `exam/contract.py::exam_state`），因此 `open_at/close_at` 是**服务器本地时间**，
 * 前端不要自己拿浏览器时间比，直接用 `ready` / `reason` / `exam_hint`。
 */
export interface PaperExamState {
  known: boolean;
  published: boolean;
  open: boolean;
  ready: boolean;
  /** ready | closed | not_started | expired | no_questions | draft | no_paper */
  reason: string;
  open_at: string | null;
  close_at: string | null;
  question_count: number;
  server_now: string;
}

/** 学生试卷列表条目（`/api/exams/list`：含考试状态，未过滤"暂不可考"的卷）。 */
export interface ExamPaperItem {
  paper_id: number;
  paper_name: string;
  paper_code?: string;
  subject_id?: number;
  subject_name?: string;
  exam_type?: string | null;
  paper_type?: string;
  question_count?: number;
  duration?: number;
  total_score?: number;
  exam?: PaperExamState | null;
  answerable?: boolean;
  exam_hint?: string;
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

/**
 * 学生「历年试卷」用的列表：走 `/api/exams/list`。
 *
 * 与 `fetchPapersList`（`/api/papers/list`）的差别（2026-11-09 P2 补）：
 *   · `/api/papers/list` 对**学生**会把「关掉 / 未到时间 / 已过期 / 0 题」的卷直接过滤掉，
 *     学生看不到"为什么这套卷不见了"；
 *   · `/api/exams/list` 不过滤，并下发 `exam.ready / reason / exam_hint`，
 *     手机/平板列表因此能显示「未开放 + 原因」，而不是凭空少一张卷。
 * 代价：这里拿到的是**全部已发布卷**，前端要按 `answerable` 决定能不能点。
 */
export async function fetchExamPapers(pageSize = 50): Promise<ExamPaperItem[]> {
  const data = await request<{ total?: number; data?: ExamPaperItem[] }>({
    url: '/api/exams/list',
    method: 'GET',
    params: { page: 1, page_size: normalizePageSize(pageSize) }
  });
  return data.data ?? [];
}

export async function refreshPapers(): Promise<void> {
  await fetchPapersList({ page: 1 });
}
