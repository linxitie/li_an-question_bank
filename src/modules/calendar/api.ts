/**
 * 考试日历（calendar）域 API 封装（P2-63）。
 *
 * 后端端点挂在 `/api/calendar`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 * 全部请求复用 @/services/api/client 的唯一 axios 实例。
 *
 * 本域只读：没有写接口，也不发布任何前端事件 / 行为 trigger_type。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用 */
export const calendarClient = apiClient;

/** 考试日历条目（与后端 `_serialize_exam` 对齐） */
export interface ExamCalendarItem {
  id: number;
  title: string;
  month: number | null;
  day: number | null;
  province: string;
  exam_type: string;
  exam_format: string;
  exam_date: string | null;
  registration_start: string;
  registration_end: string;
  url: string;
  description: string;
  content_html: string;
  recruitment_count: string | number;
  status: string;
  status_color: string;
}

/** 列表查询参数（后端 limit 1..50，offset 分页，province 筛选） */
export interface CalendarListQuery {
  limit?: number;
  offset?: number;
  province?: string;
  /** 可选取消信号（页面刷新内核传入） */
  signal?: AbortSignal;
  /** 可选破缓存时间戳（拼接到 `_ts` 查询参数） */
  ts?: number;
}

export interface CalendarListResult {
  total: number;
  items: ExamCalendarItem[];
  has_more: boolean;
}

export interface LatestExamResult {
  has_update: boolean;
  message: string;
  item: ExamCalendarItem | null;
}

interface CalendarRequestConfig {
  url: string;
  method: 'GET';
  params?: Record<string, unknown>;
  signal?: AbortSignal;
}

async function request<T>(config: CalendarRequestConfig): Promise<T> {
  const response = await calendarClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 查询考试日历列表（只读） */
export function fetchCalendarList(
  query: CalendarListQuery = {}
): Promise<CalendarListResult> {
  const params: Record<string, unknown> = {
    limit: query.limit ?? 20,
    offset: query.offset ?? 0
  };
  if (query.province) params.province = query.province;
  if (query.ts) params._ts = query.ts;

  return request<CalendarListResult>({
    url: '/api/calendar/exams',
    method: 'GET',
    params,
    signal: query.signal
  });
}

/** 查询最新一条考试信息（只读，用于「是否有更新」判断） */
export function fetchLatestExam(): Promise<LatestExamResult> {
  return request<LatestExamResult>({
    url: '/api/calendar/latest',
    method: 'GET'
  });
}

/** 刷新考试日历列表（等同重新拉取） */
export function refreshCalendar(
  query: CalendarListQuery = {}
): Promise<CalendarListResult> {
  return fetchCalendarList(query);
}
