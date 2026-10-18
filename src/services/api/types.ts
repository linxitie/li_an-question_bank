/**
 * 统一 API 类型（P1-06）
 *
 * 只放跨模块通用的响应外壳、分页与错误类型；
 * 禁止在此文件引入任何业务类型（题目、试卷、金币等领域模型）。
 */

/** 通用响应外壳：`code/message/data` 约定 */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

/** 后端异常响应（backend/app/core/exceptions.py -> create_error_response） */
export interface ApiErrorBody {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  request_id?: string | null;
}

/** 兼容后端部分接口的 `{ success: true, ... }` 成功响应 */
export interface ApiSuccessBody<T = unknown> {
  success: true;
  data?: T;
  [key: string]: unknown;
}

/** 分页请求参数（后端常见默认值 page=1、page_size=20） */
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

/** 分页数据结构（backend/app/api/v1/reward/shop.py 等返回 { total, page, page_size, items }） */
export interface PaginatedData<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

/** 分页响应 */
export type PaginatedResponse<T> = ApiResponse<PaginatedData<T>>;

/**
 * 统一错误分类。
 * 取值与 src/utils/api-helpers.ts 的 ApiErrorType 保持一致，避免两套语义分裂。
 */
export enum ApiErrorType {
  NETWORK = 'NETWORK',
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  SERVER = 'SERVER',
  UNKNOWN = 'UNKNOWN'
}

/** 归一化后的错误对象：所有 apiClient 的 rejection 都长这样 */
export interface NormalizedApiError {
  type: ApiErrorType;
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, unknown>;
}
