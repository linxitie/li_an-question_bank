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
  titleColor?: string | null;
  content: string;
  /** 正文格式（2026-11-03）：TEXT 纯文本 / HTML 富文本 */
  contentFormat?: 'TEXT' | 'HTML' | string;
  /** 标题是否由 AI 生成（2026-11-03 第 3 轮） */
  aiTitle?: boolean;
  status: string;
  author?: string;
  authorAvatar?: string;
  authorClass?: string | null;
  authorType?: string | null;
  canDelete?: boolean;
  deletedReason?: string | null;
  moderationStatus?: string | null;
  commentCount?: number;
  likeCount?: number;
  liked?: boolean;
  favoriteCount?: number;
  favorited?: boolean;
  /** 置顶 / 精华 / 浏览（后端 _serialize_post 已输出） */
  isTop?: boolean;
  isEssence?: boolean;
  viewCount?: number;
  createTime?: string | null;
  attachments?: Array<{ name: string; url: string; size?: number; type?: string }>;
  user?: {
    id?: number;
    nickname?: string;
    avatar?: string;
    userType?: string;
    className?: string | null;
  } | null;
}

export interface ModerationComment {
  id: number;
  content: string;
  /** 正文格式（2026-11-03）：TEXT 纯文本 / HTML 富文本 */
  contentFormat?: 'TEXT' | 'HTML' | string;
  status: number;
  user?: { id?: number; nickname?: string; avatar?: string; className?: string | null; userType?: string };
  author?: string;
  authorAvatar?: string;
  canDelete?: boolean;
  deletedReason?: string | null;
  moderationStatus?: string | null;
  attachments?: Array<{ name: string; url: string; size?: number; type?: string }>;
  // 2026-11-07：教师端评论与学生端互动字段合并后新增（typecheck 需要）
  createTime?: string | null;
  liked?: boolean;
  likeCount?: number;
  favorited?: boolean;
  favoriteCount?: number;
  replyCount?: number;
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
    get<{ total: number; classes: string[]; items: ModerationPost[] }>('/api/admin/forum/posts', params),
  comments: (postId: number) =>
    get<{ items: ModerationComment[] }>('/api/admin/forum/comments', { post_id: postId }),
  deletePost: (postId: number, reason?: string) =>
    del<{ success: boolean }>(`/api/admin/forum/posts/${postId}`, { reason }),
  deleteComment: (commentId: number, reason?: string) =>
    del<{ success: boolean }>(`/api/admin/forum/comments/${commentId}`, { reason }),
  /** 管理员隐藏（status=BLOCKED，直接生效，不进待复核队列） */
  hidePost: (postId: number, reason?: string) =>
    post<{ success: boolean; status: string }>(`/api/admin/forum/posts/${postId}/hide`, { reason }),
  unhidePost: (postId: number) =>
    post<{ success: boolean; status: string }>(`/api/admin/forum/posts/${postId}/unhide`),
  /** 置顶 / 取消置顶 */
  pinPost: (postId: number, pinned: boolean) =>
    post<{ success: boolean; isTop: boolean }>(`/api/admin/forum/posts/${postId}/pin`, { pinned }),
  /** 批量操作：hide / unhide / delete / restore / purge，单条失败只跳过 */
  batchPosts: (action: 'hide' | 'unhide' | 'delete' | 'restore' | 'purge', ids: number[], reason?: string) =>
    post<{ success: boolean; affected: number; skipped: number[] }>('/api/admin/forum/posts/batch', {
      action,
      ids,
      reason
    }),
  moderation: (status = 'PENDING') =>
    get<{ items: ModerationRecord[] }>('/api/admin/forum/moderation', { status }),
  approve: (id: number, note?: string) =>
    post<{ success: boolean }>(`/api/admin/forum/moderation/${id}/approve`, { note }),
  reject: (id: number, note?: string) =>
    post<{ success: boolean }>(`/api/admin/forum/moderation/${id}/reject`, { note }),
  /** 回收站：支持 kind / status / keyword / offset / limit，返回各自 total */
  recycle: (params: Record<string, unknown> = {}) =>
    get<{
      posts: ModerationPost[];
      comments: ModerationComment[];
      totalPosts: number;
      totalComments: number;
      offset: number;
      limit: number;
    }>('/api/admin/forum/recycle', params),
  recycleAudit: () =>
    get<{
      deleted_posts: number;
      hidden_posts: number;
      deleted_comments: number;
      hidden_comments: number;
      pending_moderation: number;
      stale_pending: number;
    }>('/api/admin/forum/recycle/audit'),
  /** 数据看板（P3b）：窗口内统计、趋势、班级、关键词、科目热度、违规处理、风险提示 */
  dashboard: (days: number) =>
    get<{
      range: { days: number; from: string; to: string };
      kpi: {
        posts: number;
        postsDelta: number | null;
        comments: number;
        commentsDelta: number | null;
        pending: number;
        hidden: number;
        deleted: number;
        classes: number;
      };
      trend: { labels: string[]; posts: number[]; comments: number[] };
      classes: Array<{ name: string; value: number }>;
      keywords: Array<{ word: string; count: number }>;
      subjects: Array<{ name: string; value: number; ratio: number }>;
      violations: { labels: string[]; deleted: number[]; hidden: number[] };
      risks: Array<{ level: string; text: string; count: number; tab: string }>;
    }>('/api/admin/forum/dashboard', { days }),
  restorePost: (postId: number) =>
    post<{ success: boolean }>(`/api/admin/forum/posts/${postId}/restore`),
  restoreComment: (commentId: number) =>
    post<{ success: boolean }>(`/api/admin/forum/comments/${commentId}/restore`),
  purgePost: (postId: number) =>
    del<{ success: boolean }>(`/api/admin/forum/posts/${postId}/purge`),
  purgeComment: (commentId: number) =>
    del<{ success: boolean }>(`/api/admin/forum/comments/${commentId}/purge`)
};

