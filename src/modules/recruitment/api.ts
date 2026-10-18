/**
 * 招考信息（recruitment）域 API 封装（P2-66）。
 *
 * 后端端点挂在 `/api/recruitment`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 * 全部请求复用 @/services/api/client 的唯一 axios 实例。
 *
 * 本域只读：没有写接口，也不发布任何前端事件 / 行为 trigger_type。
 * 列表端点按分类返回 `items: Record<分类, 条目[]>`，每类最多 `limit` 条。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用 */
export const recruitmentClient = apiClient;

/** 招考条目（与后端列表 / 详情响应对齐） */
export interface RecruitmentItem {
  id: number;
  title: string;
  url: string;
  category: string;
  organization: string;
  region: string;
  registration_start: string;
  registration_end: string;
  deadline: string;
  tag: string;
  tag_color: string;
  status_label: string;
  status_color: string;
  content: string;
  content_html: string;
  images: string[];
  exam_format: string;
  contact_info: string;
  requirements: string;
  view_count: number;
  publish_date: string;
  create_time: string | null;
}

/** 列表响应元信息 */
export interface RecruitmentMeta {
  last_updated: string | null;
  latest_publish_date: string;
  total: number;
  source: string;
  sort_by: string;
}

export interface RecruitmentListQuery {
  category?: string;
  /** 后端单次返回上限 1..50 */
  limit?: number;
  /** 可选取消信号（页面刷新内核传入） */
  signal?: AbortSignal;
  /** 可选破缓存时间戳（拼接到 `_ts` 查询参数） */
  ts?: number;
}

export interface RecruitmentListResult {
  categories: string[];
  items: Record<string, RecruitmentItem[]>;
  meta: RecruitmentMeta;
}

export interface RecruitmentCategoriesResult {
  categories: string[];
}

interface RecruitmentRequestConfig {
  url: string;
  method: 'GET';
  params?: Record<string, unknown>;
  signal?: AbortSignal;
}

async function request<T>(config: RecruitmentRequestConfig): Promise<T> {
  const response = await recruitmentClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 查询招考信息列表（按分类分组；只读） */
export function fetchRecruitmentList(
  query: RecruitmentListQuery = {}
): Promise<RecruitmentListResult> {
  const params: Record<string, unknown> = { limit: query.limit ?? 20 };
  if (query.category) params.category = query.category;
  if (query.ts) params._ts = query.ts;

  return request<RecruitmentListResult>({
    url: '/api/recruitment',
    method: 'GET',
    params,
    signal: query.signal
  });
}

/** 查询招考信息详情（只读；后端会累加 view_count） */
export function fetchRecruitmentDetail(
  id: string | number
): Promise<RecruitmentItem> {
  return request<RecruitmentItem>({
    url: `/api/recruitment/${id}`,
    method: 'GET'
  });
}

/** 查询招考分类列表 */
export function fetchRecruitmentCategories(): Promise<RecruitmentCategoriesResult> {
  return request<RecruitmentCategoriesResult>({
    url: '/api/recruitment/categories',
    method: 'GET'
  });
}

/** 刷新招考信息列表（等同重新拉取） */
export function refreshRecruitment(
  query: RecruitmentListQuery = {}
): Promise<RecruitmentListResult> {
  return fetchRecruitmentList(query);
}
