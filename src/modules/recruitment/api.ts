/**
 * 招考信息（recruitment）域 API 封装外壳 —— scripts/scaffold-module.mjs 生成（P1-13）
 *
 * 约束：
 *   1. 全域只允许使用 @/services/api/client 暴露的唯一 axios 实例，禁止自行 axios.create；
 *   2. 方法签名先按「列表 / 详情 / 刷新」三类占位，具体端点登记在 README「后端端点清单」；
 *   3. 方法体在 P2 阶段实现，当前调用会抛出明确的未实现错误。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用：P2 阶段所有请求都经由此实例发起 */
export const recruitmentClient = apiClient;

/** 分页查询参数（外壳占位，P2 阶段按真实端点收窄） */
export interface RecruitmentListQuery {
  page?: number;
  pageSize?: number;
  [key: string]: unknown;
}

/** 分页查询结果（外壳占位，P2 阶段按后端响应结构收窄） */
export interface RecruitmentListResult<T = unknown> {
  items: T[];
  total: number;
}

/**
 * 查询招考信息列表。
 * P2 阶段实现：经由 recruitmentClient 发起请求，端点见 README「后端端点清单」。
 */
export async function fetchRecruitmentList(
  query?: RecruitmentListQuery
): Promise<RecruitmentListResult> {
  throw new Error('fetchRecruitmentList 尚未实现（P2 阶段实现）');
}

/**
 * 查询招考信息详情。
 * P2 阶段实现：按 id 调用对应只读端点，并复用 store 中的缓存。
 */
export async function fetchRecruitmentDetail(
  id: string | number
): Promise<unknown> {
  throw new Error('fetchRecruitmentDetail 尚未实现（P2 阶段实现）');
}

/**
 * 刷新招考信息缓存。
 * P2 阶段实现：调用 store 的 load()，并处理强制刷新参数。
 */
export async function refreshRecruitment(): Promise<void> {
  throw new Error('refreshRecruitment 尚未实现（P2 阶段实现）');
}
