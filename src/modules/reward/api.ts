/**
 * 金币商城（reward）域 API 封装（P2-41）
 *
 * 后端端点挂在 `/api/shop`、`/api/coins`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 * 兑换为写操作，事件由后端在事务提交后发布 E9 `shop.purchased`；
 * 前端兑换成功仅广播 `reward:coins-changed` 供余额快照消费。
 */
import { apiClient } from '@/services/api/client';

export const rewardClient = apiClient;

export interface RewardProduct {
  id: number;
  name: string;
  category: string;
  product_type: string;
  coin_price: number;
  stock: number;
  image_url: string;
  description: string;
  deliverable_type: string;
  deliverable_payload: unknown;
  status: string;
  sort_order: number;
}

export interface RewardListQuery {
  category?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}

export interface RewardListResult<T = RewardProduct> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface RewardCoinsOverview {
  balance: number;
  month_income: number;
  month_expense: number;
}

export interface RewardCoinRecord {
  record_id: number;
  coin_change: number;
  current_balance: number;
  transaction_type: string;
  source_type: string | null;
  description: string | null;
  transaction_time: string | null;
}

export interface RewardTransactionsResult {
  total: number;
  page: number;
  page_size: number;
  items: RewardCoinRecord[];
}

export interface RewardExchangeResult {
  exchange_id: number;
  balance: number;
  product_name: string;
  coin_cost: number;
  message: string;
}

interface RewardRequestConfig {
  url: string;
  method: 'GET' | 'POST';
  params?: Record<string, unknown>;
  data?: Record<string, unknown>;
}

async function request<T>(config: RewardRequestConfig): Promise<T> {
  const response = await rewardClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 查询在售商品列表（只读，不发布行为事件） */
export function fetchRewardList(
  query: RewardListQuery = {}
): Promise<RewardListResult> {
  return request<RewardListResult>({
    url: '/api/shop/products',
    method: 'GET',
    params: {
      category: query.category || undefined,
      search: query.search || undefined,
      page: query.page ?? 1,
      page_size: query.pageSize ?? 100
    }
  });
}

/** 查询商品详情（只读） */
export function fetchRewardDetail(
  id: string | number
): Promise<RewardProduct> {
  return request<RewardProduct>({
    url: `/api/shop/products/${id}`,
    method: 'GET'
  });
}

/** 金币兑换；成功后后端在同一事务内完成扣币、写流水与权益发放 */
export function exchangeRewardProduct(
  productId: number,
  requestId: string
): Promise<RewardExchangeResult> {
  return request<RewardExchangeResult>({
    url: '/api/shop/exchange',
    method: 'POST',
    data: { product_id: productId, request_id: requestId }
  });
}

/** 金币余额概览（只读；供 user-profile 快照刷新） */
export function fetchCoinsOverview(): Promise<RewardCoinsOverview> {
  return request<RewardCoinsOverview>({
    url: '/api/coins/overview',
    method: 'GET'
  });
}

/** 金币流水分页（只读） */
export function fetchCoinTransactions(
  page = 1,
  pageSize = 20
): Promise<RewardTransactionsResult> {
  return request<RewardTransactionsResult>({
    url: '/api/coins/transactions',
    method: 'GET',
    params: { page, page_size: pageSize }
  });
}

/** 刷新商品列表（等同重新拉取） */
export function refreshReward(
  query: RewardListQuery = {}
): Promise<RewardListResult> {
  return fetchRewardList(query);
}
