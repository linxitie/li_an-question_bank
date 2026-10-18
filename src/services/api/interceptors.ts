/**
 * apiClient 请求/响应拦截器（P1-08）
 *
 * 职责：
 *   1. 请求拦截：从 `window.__VTJ_AUTH__` 注入 token（优先 `auth.getJsonHeaders()`）。
 *   2. 响应拦截：解包 `code/message/data` 外壳，直接返回 data。
 *   3. 401 处理：清理认证态并跳转 hash 路由 `#/login`，携带 redirect。
 *   4. 错误归一化：所有 rejection 统一为 NormalizedApiError。
 *   5. 幂等请求（GET/HEAD/OPTIONS）网络错误或 5xx 时最多重试一次。
 *
 * 禁止：在此文件保存业务状态、读写 localStorage 业务键。
 */
import type { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { ApiErrorType, type NormalizedApiError } from './types';

/** 登录页 hash 路由（src/router/index.ts: path '/login'，createWebHashHistory） */
const LOGIN_HASH = '#/login';

/** 幂等请求的最大重试次数 */
const MAX_RETRIES = 1;

/** 重试基础退避（毫秒） */
const RETRY_DELAY_MS = 300;

const RETRYABLE_METHODS = new Set(['get', 'head', 'options']);

type RetryableConfig = InternalAxiosRequestConfig & { __retryCount?: number };

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** 读取全局认证模块（可能尚未初始化） */
function getAuth(): Window['__VTJ_AUTH__'] | undefined {
  return typeof window === 'undefined' ? undefined : window.__VTJ_AUTH__;
}

/** 请求拦截：注入 Authorization，不覆盖调用方显式设置的头 */
function attachToken(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const auth = getAuth();
  if (!auth || typeof auth.getJsonHeaders !== 'function') return config;

  let headers: Record<string, string> = {};
  try {
    headers = auth.getJsonHeaders() || {};
  } catch {
    return config;
  }

  if (headers.Authorization && !config.headers.has('Authorization')) {
    config.headers.set('Authorization', headers.Authorization);
  }
  return config;
}

/** 跳转登录页（hash 路由，保留当前路径用于登录后回跳） */
export function redirectToLogin(): void {
  if (typeof window === 'undefined') return;

  const current = window.location.hash.replace(/^#/, '') || '/';
  const target = `${LOGIN_HASH}?redirect=${encodeURIComponent(current)}`;
  if (window.location.hash !== target) {
    window.location.hash = target;
  }
}

/** 状态码 -> 错误分类 */
function classifyStatus(status?: number): ApiErrorType {
  if (!status) return ApiErrorType.NETWORK;
  if (status === 401) return ApiErrorType.UNAUTHORIZED;
  if (status === 403) return ApiErrorType.FORBIDDEN;
  if (status === 404) return ApiErrorType.NOT_FOUND;
  if (status >= 500) return ApiErrorType.SERVER;
  return ApiErrorType.UNKNOWN;
}

/** 友好文案（与 api-helpers 保持一致口径） */
function friendlyMessage(type: ApiErrorType, status?: number): string {
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

/** 把 axios 错误归一化为 NormalizedApiError（优先取后端 error.code/message） */
export function normalizeApiError(error: AxiosError): NormalizedApiError {
  const status = error.response?.status;
  const body = error.response?.data as
    | { error?: { code?: string; message?: string; details?: Record<string, unknown> } }
    | undefined;
  const backend = body?.error;

  const type = classifyStatus(status);
  const isTimeout = error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT';
  const message = backend?.message || (isTimeout ? '请求超时，请稍后重试' : friendlyMessage(type, status));

  return {
    type,
    message,
    status,
    code: backend?.code,
    details: backend?.details
  };
}

/** 解包 `code/message/data` 外壳；不符合该结构时原样返回 */
function unwrapEnvelope(response: AxiosResponse): AxiosResponse {
  const body = response.data as Record<string, unknown> | null | undefined;

  if (
    body &&
    typeof body === 'object' &&
    typeof body.code === 'number' &&
    'data' in body &&
    !('success' in body)
  ) {
    return { ...response, data: body.data } as AxiosResponse;
  }
  return response;
}

/** 判断是否可重试：幂等请求 + 网络错误/超时/5xx */
function shouldRetry(error: AxiosError, config: RetryableConfig): boolean {
  const method = (config.method || 'get').toLowerCase();
  if (!RETRYABLE_METHODS.has(method)) return false;
  if ((config.__retryCount ?? 0) >= MAX_RETRIES) return false;

  const status = error.response?.status;
  if (!status) return true;
  return status >= 500;
}

/** 挂载拦截器（由 client.ts 调用，避免循环依赖） */
export function setupInterceptors(instance: AxiosInstance): void {
  instance.interceptors.request.use(attachToken);

  instance.interceptors.response.use(
    (response) => unwrapEnvelope(response),
    async (error: AxiosError) => {
      const config = error.config as RetryableConfig | undefined;

      if (config && shouldRetry(error, config)) {
        config.__retryCount = (config.__retryCount ?? 0) + 1;
        await sleep(RETRY_DELAY_MS * config.__retryCount);
        return instance.request(config);
      }

      const normalized = normalizeApiError(error);

      if (normalized.type === ApiErrorType.UNAUTHORIZED) {
        try {
          getAuth()?.logout();
        } catch {
          // 认证模块异常不应阻断跳转
        }
        redirectToLogin();
      }

      return Promise.reject(normalized);
    }
  );
}
