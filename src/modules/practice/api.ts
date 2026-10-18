/**
 * 答题练习（practice）域 API 封装。
 *
 * 所有请求复用 @/services/api/client 的唯一 axios 实例。
 * 后端练习端点挂在 `/api/...`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 */
import { apiClient } from '@/services/api/client';

export const practiceClient = apiClient;

interface PracticeRequestConfig {
  url: string;
  method: 'GET' | 'POST';
  data?: unknown;
  params?: Record<string, unknown>;
}

export interface PracticeSubmitItem {
  question_id: number;
  user_answer?: string;
  is_correct?: boolean;
  time_spent?: number;
  subject_id?: number;
  source?: string;
}

export interface PracticeWrongStats {
  new: number;
  updated: number;
  skipped: number;
}

export interface PracticeSubmitResult {
  status: string;
  record_id?: number | null;
  newly_unlocked?: unknown[];
  count?: number;
  correct?: number;
  total?: number;
  accuracy?: number;
  wrong_question_stats?: PracticeWrongStats;
  has_new_wrong?: boolean;
}

export interface PracticeRecordItem {
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

export interface PracticeDailyStat {
  date: string | null;
  total: number;
  correct: number;
  accuracy: number;
}

export interface PracticeRecordsResult {
  total: number;
  items: PracticeRecordItem[];
  daily_stats: PracticeDailyStat[];
}

export interface PracticeRecordsQuery {
  limit?: number;
  offset?: number;
  subjectId?: number;
}

export interface PracticeStatsBucket {
  count: number;
  correct: number;
  accuracy: number;
  time_spent_minutes: number;
}

export interface PracticeStatsResult {
  today: PracticeStatsBucket;
  week: PracticeStatsBucket;
  total: PracticeStatsBucket;
  daily_trend: Array<{
    date: string;
    weekday: string;
    count: number;
    correct: number;
    accuracy: number;
  }>;
}

export interface PracticeTypeSummaryItem {
  subject_id: number;
  subject_name: string;
  subject_code: string;
  subcategory: string;
  total_questions: number;
  done_count: number;
  is_completed: boolean;
  completion_rate: number;
}

export interface PracticeTypeSummaryResult {
  total_types: number;
  types: PracticeTypeSummaryItem[];
}

async function request<T>(config: PracticeRequestConfig): Promise<T> {
  const response = await practiceClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

export function submitPracticeAnswer(
  payload: PracticeSubmitItem & { session_id?: string }
): Promise<PracticeSubmitResult> {
  return request<PracticeSubmitResult>({
    url: '/api/practice/record',
    method: 'POST',
    data: payload
  });
}

export function submitPracticeBatch(
  records: PracticeSubmitItem[],
  options: { subjectId?: number; sessionId?: string; source?: string } = {}
): Promise<PracticeSubmitResult> {
  return request<PracticeSubmitResult>({
    url: '/api/practice/batch-record',
    method: 'POST',
    data: {
      records,
      subject_id: options.subjectId,
      session_id: options.sessionId,
      source: options.source
    }
  });
}

export function submitQuickPractice(
  records: PracticeSubmitItem[],
  options: { subjectId?: number; sessionId?: string } = {}
): Promise<PracticeSubmitResult> {
  return request<PracticeSubmitResult>({
    url: '/api/quick-practice/submit',
    method: 'POST',
    data: {
      records,
      subject_id: options.subjectId,
      session_id: options.sessionId
    }
  });
}

export function fetchPracticeRecords(
  query: PracticeRecordsQuery = {}
): Promise<PracticeRecordsResult> {
  return request<PracticeRecordsResult>({
    url: '/api/practice/records',
    method: 'GET',
    params: {
      limit: query.limit,
      offset: query.offset,
      subject_id: query.subjectId
    }
  });
}

export function fetchPracticeStats(): Promise<PracticeStatsResult> {
  return request<PracticeStatsResult>({
    url: '/api/practice/stats-card',
    method: 'GET'
  });
}

export function fetchPracticeTypeSummary(): Promise<PracticeTypeSummaryResult> {
  return request<PracticeTypeSummaryResult>({
    url: '/api/practice/type-summary',
    method: 'GET'
  });
}

export async function refreshPractice(): Promise<PracticeRecordsResult> {
  return fetchPracticeRecords();
}
