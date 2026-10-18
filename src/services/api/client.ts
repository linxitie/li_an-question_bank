/**
 * 唯一 axios 实例（P1-07）
 *
 * 约束：
 *   1. 全项目只允许本文件调用 `axios.create`，其他模块一律 `import { apiClient } from '@/services/api/client'`。
 *   2. `baseURL` 使用相对路径 `/api/v1`，开发环境由 vite proxy 转发（proxy.config.ts: /api -> 127.0.0.1:8000）。
 *   3. 认证头注入、响应解包、401 跳转与重试策略全部在 interceptors.ts 中实现。
 */
import axios, { type AxiosInstance } from 'axios';
import { setupInterceptors } from './interceptors';

/** API 前缀：相对路径，走 dev 代理 / 生产同源部署 */
export const API_BASE_URL = '/api/v1';

/** 单次请求超时（毫秒） */
export const API_TIMEOUT = 15000;

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: { Accept: 'application/json' }
});

setupInterceptors(apiClient);

export default apiClient;
