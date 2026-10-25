/** 教师端 / 管理员端论坛管理接口。 */
import { apiClient } from '@/services/api/client';

const client = apiClient;

async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await client.request<T>({ url, method: 'GET', params, baseURL: '' });
  return res.data;
}

async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = await client.request<T>({ url, method: 'POST', data, baseURL: '' });
  return res.data;
}

async function del<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await client.request<T>({ url, method: 'DELETE', params, baseURL: '' });
  return res.data;
}

export interface ModerationPost {
  id: number;
  title: string;
  content: string;
  status: string;
  author?: string;
  authorAvatar?: string;
  authorClass?: string | null;
  authorType?: string | null;
  canDelete?: boolean;
  deletedReason?: string | null;
  moderationStatus?: string | null;
  commentCount?: number;
  createTime?: string | null;
  attachments?: Array<{ name: string; url: string; size?: number; type?: string }>;
}

export interface ModerationComment {
  id: number;
  content: string;
  status: number;
  user?: { id?: number; nickname?: string; avatar?: string; className?: string | null; userType?: string };
  author?: string;
  authorAvatar?: string;
  canDelete?: boolean;
  deletedReason?: string | null;
  moderationStatus?: string | null;
  attachments?: Array<{ name: string; url: string; size?: number; type?: string }>;
}

export interface ModerationRecord {
  id: number;
  target_type: 'POST' | 'COMMENT';
  target_id: number;
  action: string;
  reason: string;
  status: string;
  created_at?: string | null;
  target?: ModerationPost | ModerationComment | null;
}

export const teacherForumApi = {
  posts: (params: Record<string, unknown>) =>
    get<{
      total: number;
      teacherClasses: string[];
      canModerate: boolean;
      items: ModerationPost[];
    }>('/api/teacher/forum/posts', params),
  comments: (postId: number) =>
    get<{ items: ModerationComment[] }>(`/api/teacher/forum/posts/${postId}/comments`),
  hidePost: (postId: number, reason: string) =>
    post<{ success: boolean }>(`/api/teacher/forum/posts/${postId}/hide`, { reason }),
  hideComment: (commentId: number, reason: string) =>
    post<{ success: boolean }>(`/api/teacher/forum/comments/${commentId}/hide`, { reason })
};

export const adminForumApi = {
  posts: (params: Record<string, unknown>) =>
    get<{ total: number; items: ModerationPost[] }>('/api/admin/forum/posts', params),
  comments: (postId: number) =>
    get<{ items: ModerationComment[] }>('/api/admin/forum/comments', { post_id: postId }),
  deletePost: (postId: number, reason?: string) =>
    del<{ success: boolean }>(`/api/admin/forum/posts/${postId}`, { reason }),
  deleteComment: (commentId: number, reason?: string) =>
    del<{ success: boolean }>(`/api/admin/forum/comments/${commentId}`, { reason }),
  moderation: (status = 'PENDING') =>
    get<{ items: ModerationRecord[] }>('/api/admin/forum/moderation', { status }),
  approve: (id: number, note?: string) =>
    post<{ success: boolean }>(`/api/admin/forum/moderation/${id}/approve`, { note }),
  reject: (id: number, note?: string) =>
    post<{ success: boolean }>(`/api/admin/forum/moderation/${id}/reject`, { note }),
  recycle: () =>
    get<{ posts: ModerationPost[]; comments: ModerationComment[] }>('/api/admin/forum/recycle'),
  recycleAudit: () =>
    get<{
      deleted_posts: number;
      hidden_posts: number;
      deleted_comments: number;
      hidden_comments: number;
      pending_moderation: number;
      stale_pending: number;
    }>('/api/admin/forum/recycle/audit'),
  restorePost: (postId: number) =>
    post<{ success: boolean }>(`/api/admin/forum/posts/${postId}/restore`),
  restoreComment: (commentId: number) =>
    post<{ success: boolean }>(`/api/admin/forum/comments/${commentId}/restore`),
  purgePost: (postId: number) =>
    del<{ success: boolean }>(`/api/admin/forum/posts/${postId}/purge`),
  purgeComment: (commentId: number) =>
    del<{ success: boolean }>(`/api/admin/forum/comments/${commentId}/purge`)
};
