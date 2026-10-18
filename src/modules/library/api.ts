/**
 * 备考资料（library）域 API 封装（P2-37）。
 *
 * 后端端点挂在 `/api/materials`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 *
 * 学习行为：详情端点 `GET /api/materials/{id}` 本身即「打开」动作，
 * 登录用户首次打开由服务端发布一次 E8 `material.opened`（同资料幂等），
 * 列表 / 进度概览等只读端点不发布事件。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用 */
export const libraryClient = apiClient;

export type LibrarySubject = 'xingce' | 'shenlun' | 'gongzhuan';

export type LibraryMaterialType =
  | 'video_intro'
  | 'video_advanced'
  | 'article'
  | 'card';

/** 列表条目 */
export interface LibraryMaterial {
  id: number;
  subject: LibrarySubject;
  type: LibraryMaterialType;
  category: string | null;
  title: string;
  summary: string | null;
  badge: string | null;
  cover_image: string | null;
  duration: number;
  read_time: number;
  difficulty: number;
  view_count: number;
  card_front: string | null;
  sort_order: number;
  is_studied?: boolean;
  progress_percent?: number;
  is_favorite?: boolean;
}

/** 详情条目（在列表条目基础上多出正文与视频地址） */
export interface LibraryMaterialDetail extends LibraryMaterial {
  content: string;
  card_back: string;
  video_url: string;
}

export interface LibraryListQuery {
  subject: LibrarySubject;
  type?: LibraryMaterialType;
  page?: number;
  pageSize?: number;
}

export interface LibraryListResult {
  total: number;
  items: LibraryMaterial[];
}

export interface LibraryProgressSummary {
  studied: number;
  total: number;
  percentage: number;
}

export interface LibraryProgressResult {
  ok: boolean;
  completed: boolean;
  progress_percent: number;
}

export interface LibraryFavoriteResult {
  is_favorite: boolean;
}

interface LibraryRequestConfig {
  url: string;
  method: 'GET' | 'POST';
  params?: Record<string, unknown>;
  data?: Record<string, unknown>;
}

async function request<T>(config: LibraryRequestConfig): Promise<T> {
  const response = await libraryClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 查询资料列表（只读，不上报打开行为） */
export function fetchLibraryList(
  query: LibraryListQuery
): Promise<LibraryListResult> {
  return request<LibraryListResult>({
    url: '/api/materials',
    method: 'GET',
    params: {
      subject: query.subject,
      type: query.type || undefined,
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20
    }
  });
}

/**
 * 查询资料详情。
 * 副作用：登录用户首次打开即由后端记录打开并发布一次 `material.opened`；
 * 同资料再次请求不会再发事件。
 */
export function fetchLibraryDetail(
  id: string | number
): Promise<LibraryMaterialDetail> {
  return request<LibraryMaterialDetail>({
    url: `/api/materials/${id}`,
    method: 'GET'
  });
}

/** 查询科目学习进度概览（登录） */
export function fetchLibraryProgressSummary(
  subject: LibrarySubject
): Promise<LibraryProgressSummary> {
  return request<LibraryProgressSummary>({
    url: '/api/materials/progress-summary',
    method: 'GET',
    params: { subject }
  });
}

/** 上报学习进度（后端 UPSERT 幂等；进度只存后端） */
export function reportLibraryProgress(payload: {
  materialId: number;
  progressPercent?: number;
  completed?: boolean;
}): Promise<LibraryProgressResult> {
  return request<LibraryProgressResult>({
    url: '/api/materials/progress',
    method: 'POST',
    data: {
      material_id: payload.materialId,
      progress_percent: payload.progressPercent ?? 0,
      completed: Boolean(payload.completed)
    }
  });
}

/** 我的收藏（登录） */
export function fetchLibraryFavorites(): Promise<LibraryListResult> {
  return request<LibraryListResult>({
    url: '/api/materials/favorites',
    method: 'GET'
  });
}

/** 收藏切换（登录） */
export function toggleLibraryFavorite(
  id: string | number
): Promise<LibraryFavoriteResult> {
  return request<LibraryFavoriteResult>({
    url: `/api/materials/${id}/favorite`,
    method: 'POST'
  });
}

/** 刷新资料列表（等同重新拉取） */
export function refreshLibrary(
  query: LibraryListQuery
): Promise<LibraryListResult> {
  return fetchLibraryList(query);
}
