/**
 * 错题集（wrongbook）域 API 封装。
 *
 * 后端错题端点挂在 `/api/wrong-questions`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 */
import { apiClient } from '@/services/api/client';

export const wrongbookClient = apiClient;

export type WrongbookCollectionType = 'WRONG' | 'FAVORITE' | 'ESSAY';
export type MasteryLevel = 'UNMASTERED' | 'PARTIAL' | 'MASTERED';
export type MasteryFilter = 'all' | MasteryLevel;

export interface WrongQuestionItem {
  wrong_id: number;
  question_id: number | null;
  question_content: string;
  question_type_detail: string;
  options: unknown;
  answer: string;
  user_answer: string;
  answer_analysis: string;
  subject_id: number | null;
  subject_name: string;
  sub_category: string;
  error_count: number;
  mastery_level: MasteryLevel | string;
  is_cut: boolean;
  accuracy_rate: number;
  review_count: number;
  last_review_time: string | null;
  add_time: string | null;
  note: string | null;
}

export interface WrongbookListQuery {
  subjectId?: number | null;
  collectionType?: WrongbookCollectionType;
  page?: number;
  pageSize?: number;
}

export interface WrongbookListResult {
  total: number;
  page: number;
  pageSize: number;
  items: WrongQuestionItem[];
}

export interface WrongbookFilters {
  subjectId?: number | null;
  masteryLevel?: MasteryFilter;
  keyword?: string;
}

export interface WrongbookReviewAnswer {
  wrong_id: number;
  question_id: number;
  user_answer: string;
}

export interface WrongbookReviewResult {
  total: number;
  correct_count: number;
  wrong_count: number;
  results: Array<Record<string, unknown>>;
  auto_chopped: number[];
}

export interface WrongbookRetryTarget {
  path: string;
  query: Record<string, string | number>;
}

/** 重练统一落在手机/平板共用的错题复习页（R12：不新建重复副本）。 */
export const WRONGBOOK_REVIEW_PATH = '/mobile/wrong-review';

interface WrongbookRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
  data?: unknown;
}

const DEFAULT_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 100;
const DETAIL_SCAN_PAGES = 10;

async function request<T>(config: WrongbookRequestConfig): Promise<T> {
  const response = await wrongbookClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

function normalizePageSize(size?: number): number {
  if (!size || size < 1) return DEFAULT_PAGE_SIZE;
  return Math.min(Math.floor(size), MAX_PAGE_SIZE);
}

export async function fetchWrongbookList(
  query: WrongbookListQuery = {}
): Promise<WrongbookListResult> {
  const page = query.page && query.page > 0 ? Math.floor(query.page) : 1;
  const pageSize = normalizePageSize(query.pageSize);
  const data = await request<{
    total?: number;
    page?: number;
    page_size?: number;
    items?: WrongQuestionItem[];
  }>({
    url: '/api/wrong-questions',
    method: 'GET',
    params: {
      page,
      page_size: pageSize,
      subject_id: query.subjectId ?? undefined,
      collection_type: query.collectionType ?? 'WRONG'
    }
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    pageSize: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}

export function fetchWrongbookDetail(
  id: string | number
): Promise<Record<string, unknown> | null> {
  return request<Record<string, unknown>>({
    url: `/api/wrong-questions/${id}/detail`,
    method: 'GET'
  }).catch(() => null);
}

/** 按 wrong_id 翻页查找列表项（详情弹窗之外的表单展示用）。 */
export async function findWrongbookItem(
  id: string | number
): Promise<WrongQuestionItem | null> {
  const target = Number(id);
  if (!Number.isFinite(target)) return null;

  for (let page = 1; page <= DETAIL_SCAN_PAGES; page += 1) {
    const result = await fetchWrongbookList({ page, pageSize: MAX_PAGE_SIZE });
    const hit = result.items.find((item) => item.wrong_id === target);
    if (hit) return hit;
    if (page * MAX_PAGE_SIZE >= result.total) return null;
  }
  return null;
}

export interface WrongbookReviewQueueQuery {
  mode?: 'knowledge' | 'time' | 'subject' | 'mixed';
  subjectId?: number;
  subcategory?: string;
  limit?: number;
}

export async function fetchWrongbookReviewQueue(
  query: WrongbookReviewQueueQuery = {}
): Promise<WrongQuestionItem[]> {
  const data = await request<{ total?: number; items?: WrongQuestionItem[] }>({
    url: '/api/wrong-questions/review/queue',
    method: 'GET',
    params: {
      mode: query.mode ?? 'mixed',
      subject_id: query.subjectId ?? undefined,
      subcategory: query.subcategory ?? undefined,
      limit: query.limit ?? 50
    }
  });
  return data.items ?? [];
}

export function updateWrongbookMastery(
  wrongId: number,
  masteryLevel: MasteryLevel
): Promise<{ mastery_level: MasteryLevel }> {
  return request<{ mastery_level: MasteryLevel }>({
    url: `/api/wrong-questions/${wrongId}/mastery`,
    method: 'PUT',
    data: { mastery_level: masteryLevel }
  });
}

export function chopWrongbook(
  wrongId: number
): Promise<{ wrong_id: number; auto_delete_time?: string }> {
  return request<{ wrong_id: number; auto_delete_time?: string }>({
    url: `/api/wrong-questions/${wrongId}/chop`,
    method: 'PUT'
  });
}

export function unchopWrongbook(wrongId: number): Promise<{ wrong_id: number }> {
  return request<{ wrong_id: number }>({
    url: `/api/wrong-questions/${wrongId}/unchop`,
    method: 'POST'
  });
}

export function submitWrongbookReview(
  answers: WrongbookReviewAnswer[],
  mode = 'mixed'
): Promise<WrongbookReviewResult> {
  return request<WrongbookReviewResult>({
    url: '/api/wrong-questions/review/submit',
    method: 'POST',
    data: { mode, answers }
  });
}

export function buildWrongbookRetryTarget(
  item: Pick<WrongQuestionItem, 'wrong_id' | 'subject_id'>
): WrongbookRetryTarget {
  const query: Record<string, string | number> = { wrong_id: item.wrong_id };
  if (item.subject_id != null) query.subject_id = item.subject_id;
  return { path: WRONGBOOK_REVIEW_PATH, query };
}

export function applyWrongbookFilters(
  items: WrongQuestionItem[],
  filters: WrongbookFilters = {}
): WrongQuestionItem[] {
  const keyword = filters.keyword?.trim().toLowerCase() ?? '';
  const mastery = filters.masteryLevel ?? 'all';
  return items.filter((item) => {
    if (filters.subjectId != null && item.subject_id !== filters.subjectId) {
      return false;
    }
    if (mastery !== 'all' && item.mastery_level !== mastery) {
      return false;
    }
    if (keyword) {
      const haystack =
        `${item.question_content} ${item.sub_category ?? ''}`.toLowerCase();
      if (!haystack.includes(keyword)) return false;
    }
    return true;
  });
}
