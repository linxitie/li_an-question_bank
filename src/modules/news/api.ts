/**
 * 每日新闻（news）域 API 封装（P2-33）。
 *
 * 所有请求复用 @/services/api/client 的唯一 axios 实例。
 * 后端新闻端点挂在 `/api/news`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 *
 * 阅读上报：详情端点 `GET /api/news/{id}` 本身即「阅读」动作，
 * 服务端按 (user_id, news_id) 去重后发布一次 E7 `news.read`；
 * 列表端点不发布任何事件。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用 */
export const newsClient = apiClient;

/** 新闻图片 */
export interface NewsImage {
  url?: string;
  order?: number;
}

/** 列表 / 详情共用的新闻条目 */
export interface NewsItem {
  id: number;
  title: string;
  url: string;
  source: string;
  category: string | null;
  publish_date: string | null;
  summary: string | null;
  content: string;
  images: NewsImage[];
  is_favorited: boolean;
  /** 后端权威已读标记（不来自 localStorage） */
  is_read: boolean;
}

/** 列表查询参数（page / pageSize 由 store 做客户端分页，不发给后端） */
export interface NewsListQuery {
  page?: number;
  pageSize?: number;
  source?: string;
  category?: string;
  /** 后端单次返回上限 1..50 */
  limit?: number;
}

export interface NewsListResult {
  items: NewsItem[];
  total: number;
}

interface NewsRequestConfig {
  url: string;
  method: 'GET';
  params?: Record<string, unknown>;
}

async function request<T>(config: NewsRequestConfig): Promise<T> {
  const response = await newsClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 查询新闻列表（只读，不上报阅读） */
export function fetchNewsList(
  query: NewsListQuery = {}
): Promise<NewsListResult> {
  return request<NewsListResult>({
    url: '/api/news',
    method: 'GET',
    params: {
      limit: query.limit ?? 20,
      source: query.source || undefined,
      category: query.category || undefined
    }
  });
}

/** 查询今日新闻（只读，不上报阅读） */
export function fetchTodayNews(
  limit = 20
): Promise<NewsListResult & { date?: string }> {
  return request<NewsListResult & { date?: string }>({
    url: '/api/news/today',
    method: 'GET',
    params: { limit }
  });
}

/**
 * 查询新闻详情。
 * 副作用：登录用户首次打开即由后端记录已读并发布一次 `news.read`；
 * 同篇再次请求不会再发事件。
 */
export function fetchNewsDetail(id: string | number): Promise<NewsItem> {
  return request<NewsItem>({
    url: `/api/news/${id}`,
    method: 'GET'
  });
}

/** 刷新新闻列表（等同重新拉取，供页面「刷新」入口复用） */
export function refreshNews(
  query: NewsListQuery = {}
): Promise<NewsListResult> {
  return fetchNewsList(query);
}
