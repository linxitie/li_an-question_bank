/**
 * 论坛社区（community）域 API 封装。
 *
 * 后端端点挂在 `/api/forum`、`/api/quotes`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 * 全部请求走唯一 axios 实例，禁止自行 axios.create。
 */
import { apiClient } from '@/services/api/client';

export const communityClient = apiClient;

export const FORUM_SHARE_TYPES = [
  'EXPERIENCE',
  'RESOURCE',
  'DISCUSSION',
  'FEELING'
] as const;

export type ForumShareType = (typeof FORUM_SHARE_TYPES)[number];

export type ForumReactionCode = 'like' | 'love' | 'haha' | 'wow' | 'sad' | 'angry';

export type ForumSortOrder = 'asc' | 'desc';

export type ForumPostSortBy = 'time' | 'likes' | 'comments' | 'views';

export type ForumCommentSortBy = 'time' | 'likes' | 'replies';

export interface ReactionResult {
  myReaction: ForumReactionCode | null;
  reactions: Record<string, number>;
  reactionCount: number;
}

export interface ForumUserBrief {
  id: number | null;
  nickname: string;
  avatar: string;
  avatarFrame?: string | null;
  signature?: string | null;
  userType: string;
}

export interface ForumAttachment {
  name: string;
  url: string;
  size?: number;
  type?: string;
}

export interface ForumPostItem {
  id: number;
  title: string;
  content: string;
  shareType?: string;
  tags?: string[];
  attachments?: ForumAttachment[];
  isTop?: boolean;
  isEssence?: boolean;
  likeCount: number;
  commentCount: number;
  viewCount: number;
  createTime: string | null;
  userId?: number;
  liked: boolean;
  myReaction?: ForumReactionCode | null;
  reactions?: Record<string, number>;
  user?: ForumUserBrief;
}

export interface ForumCommentItem {
  id: number;
  content: string;
  likeCount: number;
  createTime: string | null;
  parentCommentId?: number | null;
  replyCount?: number;
  liked: boolean;
  myReaction?: ForumReactionCode | null;
  reactions?: Record<string, number>;
  user?: ForumUserBrief;
}

export interface ForumPostListQuery {
  shareType?: ForumShareType | '';
  sortBy?: ForumPostSortBy;
  order?: ForumSortOrder;
  limit?: number;
  offset?: number;
}

export interface ForumCommentListQuery {
  sortBy?: ForumCommentSortBy;
  order?: ForumSortOrder;
  limit?: number;
  offset?: number;
}

export interface ForumPostListResult {
  total: number;
  limit: number;
  offset: number;
  posts: ForumPostItem[];
}

export interface ForumCommentListResult {
  total: number;
  limit: number;
  offset: number;
  comments: ForumCommentItem[];
}

export interface ForumStats {
  posts: number;
  users: number;
  online: number;
}

export interface ForumUserPublic {
  id: number;
  nickname: string;
  avatar: string;
  userType: string;
  school?: string | null;
  department?: string | null;
  className?: string | null;
  createdAt?: string | null;
  postCount: number;
  likeReceived: number;
}

export interface ForumPostCreatePayload {
  title: string;
  content: string;
  shareType?: ForumShareType;
  tags?: string[];
  attachments?: ForumAttachment[];
}

export interface ForumCommentCreatePayload {
  content: string;
  parentCommentId?: number | null;
}

export interface LikeToggleResult {
  liked: boolean;
  likeCount: number;
}

export interface ForumSticker {
  id: number;
  name: string;
  url: string;
  category: string;
  ownerId?: number | null;
}

export interface QuoteItem {
  quote_id: number;
  obsidian_id?: string;
  content: string;
  source: string;
  category: string;
  author: string;
  favorited: boolean;
  source_type?: 'obsidian' | 'database';
  obsidian_source?: string;
  create_time?: string;
}

export interface QuoteListQuery {
  category?: string;
  page?: number;
  pageSize?: number;
}

export interface QuoteListResult {
  total: number;
  page: number;
  page_size: number;
  items: QuoteItem[];
}

export interface QuoteFavoriteListResult {
  total: number;
  page: number;
  page_size: number;
  items: QuoteItem[];
}

export interface QuoteFavoriteResult {
  favorited: boolean;
  message: string;
}

interface CommunityRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
  data?: unknown;
}

const DEFAULT_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 100;

async function request<T>(config: CommunityRequestConfig): Promise<T> {
  const response = await communityClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

function normalizePage(page?: number): number {
  return page && page > 0 ? Math.floor(page) : 1;
}

function normalizePageSize(size?: number): number {
  if (!size || size < 1) return DEFAULT_PAGE_SIZE;
  return Math.min(Math.floor(size), MAX_PAGE_SIZE);
}

function toFormData(payload: Record<string, unknown>): FormData {
  const form = new FormData();
  Object.entries(payload).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    form.append(key, typeof value === 'string' ? value : JSON.stringify(value));
  });
  return form;
}

export async function fetchForumPosts(
  query: ForumPostListQuery = {}
): Promise<ForumPostListResult> {
  const limit = normalizePageSize(query.limit);
  const offset = query.offset && query.offset > 0 ? Math.floor(query.offset) : 0;
  const params: Record<string, unknown> = { limit, offset };
  if (query.shareType) params.share_type = query.shareType;
  if (query.sortBy) params.sort_by = query.sortBy;
  if (query.order) params.order = query.order;

  const data = await request<Partial<ForumPostListResult>>({
    url: '/api/forum/posts',
    method: 'GET',
    params
  });
  return {
    total: data.total ?? 0,
    limit: data.limit ?? limit,
    offset: data.offset ?? offset,
    posts: data.posts ?? []
  };
}

export function fetchForumPostDetail(postId: number): Promise<ForumPostItem> {
  return request<ForumPostItem>({
    url: `/api/forum/posts/${postId}`,
    method: 'GET'
  });
}

export function fetchForumComments(
  postId: number,
  query: ForumCommentListQuery = {}
): Promise<ForumCommentListResult> {
  const limit = normalizePageSize(query.limit);
  const offset = query.offset && query.offset > 0 ? Math.floor(query.offset) : 0;
  const params: Record<string, unknown> = { limit, offset };
  if (query.sortBy) params.sort_by = query.sortBy;
  if (query.order) params.order = query.order;
  return request<ForumCommentListResult>({
    url: `/api/forum/posts/${postId}/comments`,
    method: 'GET',
    params
  });
}

export function fetchForumStats(): Promise<ForumStats> {
  return request<ForumStats>({ url: '/api/forum/stats', method: 'GET' });
}

export function fetchMyForumPosts(
  query: { limit?: number; offset?: number } = {}
): Promise<ForumPostListResult> {
  const limit = normalizePageSize(query.limit);
  const offset = query.offset && query.offset > 0 ? Math.floor(query.offset) : 0;
  return request<ForumPostListResult>({
    url: '/api/forum/my-posts',
    method: 'GET',
    params: { limit, offset }
  });
}

export function fetchForumUserPublic(userId: number): Promise<ForumUserPublic> {
  return request<ForumUserPublic>({
    url: `/api/forum/users/${userId}/public`,
    method: 'GET'
  });
}

export function createForumPost(
  payload: ForumPostCreatePayload
): Promise<ForumPostItem> {
  return request<ForumPostItem>({
    url: '/api/forum/posts',
    method: 'POST',
    data: toFormData({
      title: payload.title,
      content: payload.content,
      share_type: payload.shareType,
      tags: payload.tags?.length ? payload.tags.join(',') : undefined,
      attachments: payload.attachments?.length ? payload.attachments : undefined
    })
  });
}

export function deleteForumPost(postId: number): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>({
    url: `/api/forum/posts/${postId}`,
    method: 'DELETE'
  });
}

export function toggleForumPostLike(postId: number): Promise<LikeToggleResult> {
  return request<LikeToggleResult>({
    url: `/api/forum/posts/${postId}/like`,
    method: 'POST'
  });
}

export function createForumComment(
  postId: number,
  payload: ForumCommentCreatePayload
): Promise<ForumCommentItem> {
  return request<ForumCommentItem>({
    url: `/api/forum/posts/${postId}/comments`,
    method: 'POST',
    data: toFormData({
      content: payload.content,
      parent_comment_id: payload.parentCommentId
    })
  });
}

export function toggleForumCommentLike(
  commentId: number
): Promise<LikeToggleResult> {
  return request<LikeToggleResult>({
    url: `/api/forum/comments/${commentId}/like`,
    method: 'POST'
  });
}

export function setForumPostReaction(
  postId: number,
  reaction: ForumReactionCode
): Promise<ReactionResult> {
  return request<ReactionResult>({
    url: `/api/forum/posts/${postId}/reactions/${reaction}`,
    method: 'POST'
  });
}

export function clearForumPostReaction(postId: number): Promise<ReactionResult> {
  return request<ReactionResult>({
    url: `/api/forum/posts/${postId}/reactions`,
    method: 'DELETE'
  });
}

export function setForumCommentReaction(
  commentId: number,
  reaction: ForumReactionCode
): Promise<ReactionResult> {
  return request<ReactionResult>({
    url: `/api/forum/comments/${commentId}/reactions/${reaction}`,
    method: 'POST'
  });
}

export function clearForumCommentReaction(commentId: number): Promise<ReactionResult> {
  return request<ReactionResult>({
    url: `/api/forum/comments/${commentId}/reactions`,
    method: 'DELETE'
  });
}

export function fetchForumStickers(): Promise<{ stickers: ForumSticker[] }> {
  return request<{ stickers: ForumSticker[] }>({
    url: '/api/forum/stickers',
    method: 'GET'
  });
}

export function uploadForumSticker(file: File, name?: string): Promise<ForumSticker> {
  const form = new FormData();
  form.append('file', file);
  if (name) form.append('name', name);
  return request<ForumSticker>({
    url: '/api/forum/stickers',
    method: 'POST',
    data: form
  });
}

export function deleteForumSticker(stickerId: number): Promise<{ success: boolean }> {
  return request<{ success: boolean }>({
    url: `/api/forum/stickers/${stickerId}`,
    method: 'DELETE'
  });
}

export async function fetchQuotes(query: QuoteListQuery = {}): Promise<QuoteListResult> {
  const page = normalizePage(query.page);
  const pageSize = normalizePageSize(query.pageSize);
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (query.category) params.category = query.category;

  const data = await request<Partial<QuoteListResult>>({
    url: '/api/quotes',
    method: 'GET',
    params
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}

export function fetchRandomQuote(exclude?: string): Promise<QuoteItem> {
  return request<QuoteItem>({
    url: '/api/quotes/random',
    method: 'GET',
    params: exclude ? { exclude } : undefined
  });
}

export function fetchDailyQuote(): Promise<QuoteItem> {
  return request<QuoteItem>({ url: '/api/quotes/quote/daily', method: 'GET' });
}

export function toggleQuoteFavorite(quoteId: number): Promise<QuoteFavoriteResult> {
  return request<QuoteFavoriteResult>({
    url: `/api/quotes/${quoteId}/favorite`,
    method: 'POST'
  });
}

export function toggleObsidianQuoteFavorite(
  obsidianSource: string
): Promise<QuoteFavoriteResult> {
  return request<QuoteFavoriteResult>({
    url: `/api/quotes/obsidian/${encodeURIComponent(obsidianSource)}/favorite`,
    method: 'POST'
  });
}

export async function fetchQuoteFavorites(
  page = 1,
  pageSize = DEFAULT_PAGE_SIZE
): Promise<QuoteFavoriteListResult> {
  const data = await request<Partial<QuoteFavoriteListResult>>({
    url: '/api/quotes/favorites',
    method: 'GET',
    params: { page: normalizePage(page), page_size: normalizePageSize(pageSize) }
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}
