/**
 * 练习记录（records）域 API 封装。
 *
 * 记录由 ③ 答题练习写入，④ 只读展示；本域不参与判分。
 * 后端记录与统计端点挂在 `/api/...`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 */
import { apiClient } from '@/services/api/client';

export const recordsClient = apiClient;

export interface RecordsItem {
  record_id: number;
  question_id: number | null;
  subject_id: number | null;
  type_id: number | null;
  is_correct: boolean;
  time_spent: number;
  user_answer: string;
  question_content: string;
  correct_answer: string;
  practice_date: string | null;
  practice_time: string | null;
  source: string | null;
}

export interface RecordsDailyStat {
  date: string | null;
  total: number;
  correct: number;
  accuracy: number;
}

export interface RecordsListQuery {
  limit?: number;
  offset?: number;
  subjectId?: number;
}

export interface RecordsListResult {
  total: number;
  items: RecordsItem[];
  dailyStats: RecordsDailyStat[];
}

export interface RecordsFilters {
  subjectId?: number | null;
  isCorrect?: boolean | null;
  source?: string | null;
  keyword?: string;
}

export interface RecordsStats {
  todayQuestions: number;
  weeklyQuestions: number;
  monthlyQuestions: number;
  totalQuestions: number;
  accuracyRate: number;
  totalStudyHours: number;
  streak: number;
}

export interface RecordsTrendPoint {
  date: string;
  questionsDone: number;
  correctCount: number;
  accuracy: number;
  timeSpent: number;
}

interface RecordsRequestConfig {
  url: string;
  method: 'GET';
  params?: Record<string, unknown>;
}

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 50;
const DETAIL_SCAN_PAGES = 10;

interface RawRecordsList {
  total?: number;
  items?: RecordsItem[];
  daily_stats?: RecordsDailyStat[];
}

async function request<T>(config: RecordsRequestConfig): Promise<T> {
  const response = await recordsClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

function normalizeLimit(limit?: number): number {
  if (!limit || limit < 1) return DEFAULT_LIMIT;
  return Math.min(Math.floor(limit), MAX_LIMIT);
}

export async function fetchRecordsList(
  query: RecordsListQuery = {}
): Promise<RecordsListResult> {
  const data = await request<RawRecordsList>({
    url: '/api/practice/records',
    method: 'GET',
    params: {
      limit: normalizeLimit(query.limit),
      offset: query.offset ?? 0,
      subject_id: query.subjectId
    }
  });
  return {
    total: data.total ?? 0,
    items: data.items ?? [],
    dailyStats: data.daily_stats ?? []
  };
}

/**
 * 练习记录没有独立详情端点：列表项本身携带题目、答案与解析字段。
 * 这里按 record_id 翻页查找，找不到返回 null。
 */
export async function fetchRecordsDetail(
  id: string | number
): Promise<RecordsItem | null> {
  const target = Number(id);
  if (!Number.isFinite(target)) return null;

  for (let page = 0; page < DETAIL_SCAN_PAGES; page += 1) {
    const result = await fetchRecordsList({
      limit: MAX_LIMIT,
      offset: page * MAX_LIMIT
    });
    const hit = result.items.find((item) => item.record_id === target);
    if (hit) return hit;
    if (result.items.length < MAX_LIMIT) return null;
  }
  return null;
}

export function fetchRecordsStats(): Promise<RecordsStats> {
  return request<RecordsStats>({
    url: '/api/stats/',
    method: 'GET'
  });
}

export async function fetchRecordsTrend(days = 7): Promise<RecordsTrendPoint[]> {
  const data = await request<{ trend?: RecordsTrendPoint[] }>({
    url: '/api/stats/practice-trend',
    method: 'GET',
    params: { days }
  });
  return data.trend ?? [];
}

export async function refreshRecords(): Promise<RecordsListResult> {
  return fetchRecordsList();
}

export function applyRecordsFilters(
  items: RecordsItem[],
  filters: RecordsFilters = {}
): RecordsItem[] {
  const keyword = filters.keyword?.trim().toLowerCase() ?? '';
  return items.filter((item) => {
    if (filters.subjectId != null && item.subject_id !== filters.subjectId) {
      return false;
    }
    if (filters.isCorrect != null && item.is_correct !== filters.isCorrect) {
      return false;
    }
    if (filters.source && item.source !== filters.source) {
      return false;
    }
    if (keyword) {
      const haystack = `${item.question_content} ${item.source ?? ''}`.toLowerCase();
      if (!haystack.includes(keyword)) return false;
    }
    return true;
  });
}
