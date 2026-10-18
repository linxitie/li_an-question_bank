/**
 * 题库浏览（catalog）域 API 封装（P2-71）。
 *
 * 只读接口：题目列表 / 筛选 / 详情。
 * 后端端点挂在 `/api/questions`（api_surface.json 冻结口径，questions.py 零变化），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 *
 * 边界：
 *   - 本域不负责答题落库（交 practice / records 域）；
 *   - 列表与详情均为只读 GET，不发布任何事件、不写用户行为；
 *   - ⑱⑲⑳（联考小智 / 院校联考机考系统 / 小模考）不在此实现。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用：所有请求都经由此实例发起 */
export const catalogClient = apiClient;

/** 选项结构（后端 QuestionOptionItem） */
export interface CatalogQuestionOption {
  key: string;
  value: string;
}

/** 题目列表 / 详情条目（后端 QuestionResponse） */
export interface CatalogQuestion {
  question_id: number;
  subject_id: number;
  type_id: number;
  question_content: string;
  options: CatalogQuestionOption[] | null;
  answer: string;
  answer_analysis: string | null;
  question_type_detail?: string | null;
  point_id: number | null;
  difficulty: number;
  score: number;
  year: number | null;
  source: string | null;
  tags: string | null;
  video_url: string | null;
  accuracy_rate: number;
  exam_frequency: number;
  creator_id: number;
  auditor_id: number | null;
  audit_status: number;
  create_time: string | null;
  update_time: string | null;
  status: number;
  version: number;
  [key: string]: unknown;
}

/**
 * 列表筛选参数（驼峰，内部映射为后端下划线参数）。
 * 与后端 `get_questions` 的 Query 参数一一对应。
 */
export interface CatalogListQuery {
  subjectId?: number;
  typeId?: number;
  pointId?: number;
  difficulty?: number;
  auditStatus?: number;
  year?: number;
  keyword?: string;
  page?: number;
  pageSize?: number;
}

/** 分页查询结果（后端 QuestionListResponse） */
export interface CatalogListResult {
  total: number;
  page: number;
  page_size: number;
  items: CatalogQuestion[];
}

interface CatalogRequestConfig {
  url: string;
  method: 'GET';
  params?: Record<string, unknown>;
}

async function request<T>(config: CatalogRequestConfig): Promise<T> {
  const response = await catalogClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 驼峰查询参数 → 后端下划线参数（空关键词不下发） */
export function buildCatalogParams(
  query: CatalogListQuery = {}
): Record<string, unknown> {
  const keyword = query.keyword?.trim();
  return {
    subject_id: query.subjectId,
    type_id: query.typeId,
    point_id: query.pointId,
    difficulty: query.difficulty,
    audit_status: query.auditStatus,
    year: query.year,
    keyword: keyword || undefined,
    page: query.page ?? 1,
    page_size: query.pageSize ?? 10
  };
}

/**
 * 查询题目列表（只读）。
 * 后端固定过滤 `status == 1`，返回服务端分页结构。
 */
export async function fetchCatalogList(
  query: CatalogListQuery = {}
): Promise<CatalogListResult> {
  const result = await request<CatalogListResult>({
    url: '/api/questions/',
    method: 'GET',
    params: buildCatalogParams(query)
  });
  return {
    total: result?.total ?? 0,
    page: result?.page ?? query.page ?? 1,
    page_size: result?.page_size ?? query.pageSize ?? 10,
    items: result?.items ?? []
  };
}

/**
 * 查询题目详情（只读）。
 * 注意：后端详情端点会自增 `exam_frequency`，但不发布任何用户行为事件。
 */
export function fetchCatalogDetail(
  id: string | number
): Promise<CatalogQuestion> {
  return request<CatalogQuestion>({
    url: `/api/questions/${id}`,
    method: 'GET'
  });
}

/** 刷新题目列表（等同重新拉取；不做强制缓存控制） */
export function refreshCatalog(
  query: CatalogListQuery = {}
): Promise<CatalogListResult> {
  return fetchCatalogList(query);
}
