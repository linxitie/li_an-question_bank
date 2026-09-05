/**
 * API 错误处理工具
 *
 * 作用：封装 window.__VTJ_AUTH__.apiFetch，提供统一错误处理与用户反馈
 * 设计原则：
 *   1. 不修改 auth.ts 原有逻辑（向后兼容）
 *   2. 提供可选的错误提示（默认开启，可关闭）
 *   3. 统一处理 403/500/网络错误，减少组件内重复 try/catch
 *   4. 返回标准化结果，便于组件判断成功/失败
 *
 * 使用方式：
 *   import { safeApiCall } from '@/utils/api-helpers';
 *   const result = await safeApiCall('/api/notes/stats', { headers: ... });
 *   if (result.ok) { ... } else { result.error }
 */

// 错误类型枚举
export enum ApiErrorType {
  NETWORK = 'NETWORK',
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  SERVER = 'SERVER',
  UNKNOWN = 'UNKNOWN'
}

// 标准化错误信息
export interface ApiError {
  type: ApiErrorType;
  message: string;
  status?: number;
}

// 标准化响应结果
export interface ApiResult<T = any> {
  ok: boolean;
  data?: T;
  error?: ApiError;
  response?: Response;
}

// 错误类型映射
function classifyError(status: number, networkError: boolean): ApiErrorType {
  if (networkError) return ApiErrorType.NETWORK;
  if (status === 401) return ApiErrorType.UNAUTHORIZED;
  if (status === 403) return ApiErrorType.FORBIDDEN;
  if (status === 404) return ApiErrorType.NOT_FOUND;
  if (status >= 500) return ApiErrorType.SERVER;
  return ApiErrorType.UNKNOWN;
}

// 友好的错误提示文案
function getFriendlyMessage(type: ApiErrorType, status?: number): string {
  switch (type) {
    case ApiErrorType.NETWORK:
      return '网络连接失败，请检查网络后重试';
    case ApiErrorType.UNAUTHORIZED:
      return '登录已过期，请重新登录';
    case ApiErrorType.FORBIDDEN:
      return '没有权限执行此操作';
    case ApiErrorType.NOT_FOUND:
      return '请求的资源不存在';
    case ApiErrorType.SERVER:
      return `服务器错误(${status})，请稍后重试`;
    default:
      return `请求失败(${status})`;
  }
}

// 内部提示函数（使用 ElMessage，惰性导入避免循环依赖）
let _elMessage: any = null;
async function showMessage(message: string, type: 'error' | 'warning' = 'error') {
  try {
    if (!_elMessage) {
      const mod = await import('element-plus');
      _elMessage = mod.ElMessage;
    }
    _elMessage({ message, type, duration: 3000 });
  } catch (e) {
    // ElMessage 加载失败时降级到 console
    console.warn('[api-helpers]', message);
  }
}

/**
 * 安全 API 调用（推荐使用）
 *
 * @param url 请求 URL
 * @param options fetch 选项（与 apiFetch 一致）
 * @param opts 额外配置：{ silent?: boolean } silent=true 时不显示错误提示
 * @returns ApiResult 标准化结果
 */
export async function safeApiCall<T = any>(
  url: string,
  options?: any,
  opts?: { silent?: boolean }
): Promise<ApiResult<T>> {
  const silent = opts?.silent ?? false;
  const auth = (window as any).__VTJ_AUTH__;

  if (!auth || typeof auth.apiFetch !== 'function') {
    const error: ApiError = {
      type: ApiErrorType.UNKNOWN,
      message: '认证模块未初始化'
    };
    if (!silent) await showMessage(error.message);
    return { ok: false, error };
  }

  try {
    const response: Response = await auth.apiFetch(url, options);

    // 401 已由 apiFetch 内部处理（跳转登录），此处不重复提示
    if (response.status === 401) {
      return {
        ok: false,
        response,
        error: { type: ApiErrorType.UNAUTHORIZED, message: '登录已过期', status: 401 }
      };
    }

    // 403/404/5xx 等错误
    if (!response.ok && response.status >= 400) {
      const type = classifyError(response.status, false);
      const message = getFriendlyMessage(type, response.status);
      if (!silent) await showMessage(message);
      return {
        ok: false,
        response,
        error: { type, message, status: response.status }
      };
    }

    // 成功
    return { ok: true, response };
  } catch (e: any) {
    // 网络错误或 fetch 抛出的异常
    const type = ApiErrorType.NETWORK;
    const message = getFriendlyMessage(type);
    if (!silent) await showMessage(message);
    return {
      ok: false,
      error: { type, message: e?.message || message }
    };
  }
}

/**
 * 安全获取 JSON 数据
 *
 * @param url 请求 URL
 * @param options fetch 选项
 * @param opts 额外配置
 * @returns ApiResult，data 为解析后的 JSON
 */
export async function safeGetJson<T = any>(
  url: string,
  options?: any,
  opts?: { silent?: boolean }
): Promise<ApiResult<T>> {
  const result = await safeApiCall<T>(url, options, opts);
  if (result.ok && result.response) {
    try {
      const data = await result.response.json();
      return { ...result, data };
    } catch (e) {
      const error: ApiError = {
        type: ApiErrorType.UNKNOWN,
        message: '响应 JSON 解析失败'
      };
      if (!opts?.silent) await showMessage(error.message);
      return { ok: false, error };
    }
  }
  return result;
}
