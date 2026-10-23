/**
 * 论坛社区（community）域 Store。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * 帖子、评论、金句收藏为本域业务状态，全部只驻留内存，不写 localStorage。
 * 事件只做加速器，页面 onMounted 仍须主动 load()。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  clearForumCommentReaction,
  clearForumPostReaction,
  createForumComment,
  createForumPost,
  deleteForumPost as deletePostRequest,
  fetchDailyQuote,
  fetchForumComments,
  fetchForumPostDetail,
  fetchForumPosts,
  fetchForumStats,
  fetchForumUserPublic,
  fetchMyForumPosts,
  fetchQuoteFavorites,
  fetchQuotes,
  fetchRandomQuote,
  setForumCommentReaction,
  setForumPostReaction,
  toggleForumCommentLike,
  toggleForumPostLike,
  toggleObsidianQuoteFavorite,
  toggleQuoteFavorite,
  type ForumCommentCreatePayload,
  type ForumCommentItem,
  type ForumCommentSortBy,
  type ForumPostCreatePayload,
  type ForumPostItem,
  type ForumPostListQuery,
  type ForumPostSortBy,
  type ForumReactionCode,
  type ForumShareType,
  type ForumSortOrder,
  type ForumStats,
  type ForumUserPublic,
  type LikeToggleResult,
  type ReactionResult,
  type QuoteFavoriteResult,
  type QuoteItem,
  type QuoteListQuery
} from './api';

export interface CommunityState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export const MAX_POST_TITLE_LENGTH = 200;
export const MAX_POST_CONTENT_LENGTH = 10000;
export const MAX_COMMENT_LENGTH = 2000;

export const FORUM_SHARE_TYPE_OPTIONS: ReadonlyArray<{
  key: ForumShareType;
  name: string;
}> = [
  { key: 'EXPERIENCE', name: '经验分享' },
  { key: 'RESOURCE', name: '资料分享' },
  { key: 'DISCUSSION', name: '学习讨论' },
  { key: 'FEELING', name: '心情打卡' }
];

export function createCommunityInitialState(): CommunityState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export function validatePostDraft(draft: {
  title: string;
  content: string;
}): string | null {
  const title = (draft.title ?? '').trim();
  const content = (draft.content ?? '').trim();
  if (!title) return '请输入标题';
  if (title.length > MAX_POST_TITLE_LENGTH) {
    return `标题不能超过 ${MAX_POST_TITLE_LENGTH} 字`;
  }
  if (!content) return '请输入内容';
  if (content.length > MAX_POST_CONTENT_LENGTH) {
    return `内容不能超过 ${MAX_POST_CONTENT_LENGTH} 字`;
  }
  return null;
}

export function validateCommentText(text: string): string | null {
  const value = (text ?? '').trim();
  if (!value) return '评论内容不能为空';
  if (value.length > MAX_COMMENT_LENGTH) {
    return `评论不能超过 ${MAX_COMMENT_LENGTH} 字`;
  }
  return null;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (error && typeof error === 'object' && 'message' in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === 'string' && message) return message;
  }
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

export const useCommunityStore = defineStore('community', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const posts = ref<ForumPostItem[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(8);
  const shareType = ref<ForumShareType | ''>('');
  const postSortBy = ref<ForumPostSortBy>('time');
  const postSortOrder = ref<ForumSortOrder>('desc');
  const commentSortBy = ref<ForumCommentSortBy>('time');
  const commentSortOrder = ref<ForumSortOrder>('asc');

  const myPosts = ref<ForumPostItem[]>([]);
  const myPostsTotal = ref(0);

  const detail = ref<ForumPostItem | null>(null);
  const detailLoading = ref(false);

  const comments = ref<ForumCommentItem[]>([]);
  const commentsTotal = ref(0);

  const stats = ref<ForumStats | null>(null);

  const quotes = ref<QuoteItem[]>([]);
  const quotesTotal = ref(0);
  const quotesPage = ref(1);
  const quotesPageSize = ref(20);
  const quotesCategory = ref('');

  const quoteFavorites = ref<QuoteItem[]>([]);
  const quoteFavoritesTotal = ref(0);
  const dailyQuote = ref<QuoteItem | null>(null);

  const submitting = ref(false);
  const pendingWrites = new Set<string>();

  const ready = computed(() => initialized.value && error.value === null);
  const isEmpty = computed(
    () => initialized.value && !loading.value && posts.value.length === 0
  );
  const hasMore = computed(() => posts.value.length < total.value);
  const offset = computed(() => posts.value.length);
  const totalPages = computed(() =>
    Math.max(1, Math.ceil(total.value / Math.max(1, pageSize.value)))
  );
  const favoriteCount = computed(() => quoteFavorites.value.length);

  function clearError(): void {
    error.value = null;
  }

  function beginWrite(key: string): boolean {
    if (pendingWrites.has(key)) return false;
    pendingWrites.add(key);
    submitting.value = true;
    return true;
  }

  function endWrite(key: string): void {
    pendingWrites.delete(key);
    submitting.value = pendingWrites.size > 0;
  }

  function applyLikeResult(
    target: { liked: boolean; likeCount: number } | null | undefined,
    result: LikeToggleResult
  ): void {
    if (!target) return;
    target.liked = result.liked;
    target.likeCount = result.likeCount;
  }

  function applyReactionResult(
    target:
      | { liked: boolean; likeCount: number; myReaction?: ForumReactionCode | null; reactions?: Record<string, number> }
      | null
      | undefined,
    result: ReactionResult
  ): void {
    if (!target) return;
    target.myReaction = result.myReaction;
    target.reactions = result.reactions;
    target.likeCount = result.reactionCount;
    target.liked = result.myReaction !== null;
  }

  async function load(query: ForumPostListQuery = {}): Promise<void> {
    if (query.shareType !== undefined) shareType.value = query.shareType;
    if (query.sortBy) postSortBy.value = query.sortBy;
    if (query.order) postSortOrder.value = query.order;
    if (query.limit) pageSize.value = query.limit;
    page.value = 1;

    loading.value = true;
    error.value = null;
    try {
      const result = await fetchForumPosts({
        shareType: shareType.value,
        sortBy: postSortBy.value,
        order: postSortOrder.value,
        limit: pageSize.value,
        offset: 0
      });
      posts.value = result.posts;
      total.value = result.total;
    } catch (e) {
      error.value = errorMessage(e);
      posts.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadPage(pageNo: number, limit?: number): Promise<void> {
    if (limit) pageSize.value = limit;
    const safePage = pageNo > 0 ? Math.floor(pageNo) : 1;

    loading.value = true;
    error.value = null;
    try {
      const result = await fetchForumPosts({
        shareType: shareType.value,
        sortBy: postSortBy.value,
        order: postSortOrder.value,
        limit: pageSize.value,
        offset: (safePage - 1) * pageSize.value
      });
      posts.value = result.posts;
      total.value = result.total;
      page.value = safePage;
    } catch (e) {
      error.value = errorMessage(e);
      posts.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadMore(): Promise<void> {
    if (loading.value || !hasMore.value) return;

    loading.value = true;
    error.value = null;
    try {
      const result = await fetchForumPosts({
        shareType: shareType.value,
        sortBy: postSortBy.value,
        order: postSortOrder.value,
        limit: pageSize.value,
        offset: offset.value
      });
      posts.value = [...posts.value, ...result.posts];
      total.value = result.total;
      page.value += 1;
    } catch (e) {
      error.value = errorMessage(e);
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadStats(): Promise<void> {
    try {
      stats.value = await fetchForumStats();
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function loadPost(postId: number): Promise<ForumPostItem | null> {
    detailLoading.value = true;
    error.value = null;
    try {
      detail.value = await fetchForumPostDetail(postId);
      return detail.value;
    } catch (e) {
      error.value = errorMessage(e);
      detail.value = null;
      return null;
    } finally {
      detailLoading.value = false;
      initialized.value = true;
    }
  }

  async function loadComments(
    postId: number,
    options: { sortBy?: ForumCommentSortBy; order?: ForumSortOrder } = {}
  ): Promise<void> {
    if (options.sortBy) commentSortBy.value = options.sortBy;
    if (options.order) commentSortOrder.value = options.order;
    try {
      const result = await fetchForumComments(postId, {
        sortBy: commentSortBy.value,
        order: commentSortOrder.value,
        limit: 100,
        offset: 0
      });
      comments.value = result.comments;
      commentsTotal.value = result.total;
    } catch (e) {
      error.value = errorMessage(e);
      comments.value = [];
      commentsTotal.value = 0;
    }
  }

  async function createPost(
    payload: ForumPostCreatePayload
  ): Promise<ForumPostItem | null> {
    const validation = validatePostDraft(payload);
    if (validation) {
      error.value = validation;
      throw new Error(validation);
    }

    const key = 'create-post';
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const post = await createForumPost({
        ...payload,
        title: payload.title.trim(),
        content: payload.content.trim()
      });
      posts.value = [post, ...posts.value];
      total.value += 1;
      return post;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function deletePost(postId: number): Promise<void> {
    const key = `delete-post:${postId}`;
    if (!beginWrite(key)) return;

    const snapshot = posts.value.slice();
    const snapshotTotal = total.value;
    posts.value = posts.value.filter((item) => item.id !== postId);
    total.value = Math.max(0, snapshotTotal - 1);
    error.value = null;
    try {
      await deletePostRequest(postId);
      if (detail.value && detail.value.id === postId) detail.value = null;
    } catch (e) {
      posts.value = snapshot;
      total.value = snapshotTotal;
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function togglePostLike(postId: number): Promise<LikeToggleResult | null> {
    const key = `like-post:${postId}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const result = await toggleForumPostLike(postId);
      const post = posts.value.find((item) => item.id === postId);
      applyLikeResult(post, result);
      if (detail.value && detail.value.id === postId) {
        applyLikeResult(detail.value, result);
      }
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function submitComment(
    postId: number,
    payload: ForumCommentCreatePayload
  ): Promise<ForumCommentItem | null> {
    const validation = validateCommentText(payload.content);
    if (validation) {
      error.value = validation;
      throw new Error(validation);
    }

    const key = `comment:${postId}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const comment = await createForumComment(postId, {
        ...payload,
        content: payload.content.trim()
      });
      comments.value = [...comments.value, comment];
      commentsTotal.value += 1;
      if (detail.value && detail.value.id === postId) {
        detail.value.commentCount = (detail.value.commentCount || 0) + 1;
      }
      const post = posts.value.find((item) => item.id === postId);
      if (post) post.commentCount = (post.commentCount || 0) + 1;
      return comment;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function toggleCommentLike(
    commentId: number
  ): Promise<LikeToggleResult | null> {
    const key = `like-comment:${commentId}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const result = await toggleForumCommentLike(commentId);
      applyLikeResult(
        comments.value.find((item) => item.id === commentId),
        result
      );
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function reactToPost(
    postId: number,
    reaction: ForumReactionCode
  ): Promise<ReactionResult | null> {
    const key = `react-post:${postId}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const current =
        detail.value?.id === postId
          ? detail.value.myReaction
          : posts.value.find((item) => item.id === postId)?.myReaction;
      const result =
        current === reaction
          ? await clearForumPostReaction(postId)
          : await setForumPostReaction(postId, reaction);

      applyReactionResult(
        posts.value.find((item) => item.id === postId),
        result
      );
      if (detail.value && detail.value.id === postId) {
        applyReactionResult(detail.value, result);
      }
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function reactToComment(
    commentId: number,
    reaction: ForumReactionCode
  ): Promise<ReactionResult | null> {
    const key = `react-comment:${commentId}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const target = comments.value.find((item) => item.id === commentId);
      const result =
        target?.myReaction === reaction
          ? await clearForumCommentReaction(commentId)
          : await setForumCommentReaction(commentId, reaction);
      applyReactionResult(target, result);
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function loadMyPosts(
    query: { limit?: number; offset?: number } = {}
  ): Promise<void> {
    try {
      const result = await fetchMyForumPosts(query);
      myPosts.value = result.posts;
      myPostsTotal.value = result.total;
      initialized.value = true;
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function loadUserPublic(userId: number): Promise<ForumUserPublic | null> {
    try {
      return await fetchForumUserPublic(userId);
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    }
  }

  async function loadQuotes(query: QuoteListQuery = {}): Promise<void> {
    if (query.category !== undefined) quotesCategory.value = query.category;
    if (query.page) quotesPage.value = query.page;
    if (query.pageSize) quotesPageSize.value = query.pageSize;

    error.value = null;
    try {
      const result = await fetchQuotes({
        category: quotesCategory.value || undefined,
        page: quotesPage.value,
        pageSize: quotesPageSize.value
      });
      quotes.value = result.items;
      quotesTotal.value = result.total;
      initialized.value = true;
    } catch (e) {
      error.value = errorMessage(e);
      quotes.value = [];
      quotesTotal.value = 0;
    }
  }

  async function loadQuoteFavorites(pageNo = 1): Promise<void> {
    try {
      const result = await fetchQuoteFavorites(pageNo, 100);
      quoteFavorites.value = result.items;
      quoteFavoritesTotal.value = result.total;
      initialized.value = true;
    } catch (e) {
      error.value = errorMessage(e);
      quoteFavorites.value = [];
      quoteFavoritesTotal.value = 0;
    }
  }

  async function loadDailyQuote(): Promise<void> {
    try {
      dailyQuote.value = await fetchDailyQuote();
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function loadRandomQuote(exclude?: string): Promise<QuoteItem | null> {
    try {
      return await fetchRandomQuote(exclude);
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    }
  }

  async function toggleFavorite(quote: QuoteItem): Promise<QuoteFavoriteResult | null> {
    const key = `quote-favorite:${quote.obsidian_source ?? quote.quote_id}`;
    if (!beginWrite(key)) return null;

    const sameQuote = (item: QuoteItem): boolean =>
      quote.obsidian_source
        ? item.obsidian_source === quote.obsidian_source
        : item.quote_id === quote.quote_id;

    error.value = null;
    try {
      const result = quote.obsidian_source
        ? await toggleObsidianQuoteFavorite(quote.obsidian_source)
        : await toggleQuoteFavorite(quote.quote_id);

      quotes.value = quotes.value.map((item) =>
        sameQuote(item) ? { ...item, favorited: result.favorited } : item
      );
      if (dailyQuote.value && sameQuote(dailyQuote.value)) {
        dailyQuote.value = { ...dailyQuote.value, favorited: result.favorited };
      }
      if (result.favorited) {
        if (!quoteFavorites.value.some(sameQuote)) {
          quoteFavorites.value = [
            { ...quote, favorited: true },
            ...quoteFavorites.value
          ];
          quoteFavoritesTotal.value += 1;
        }
      } else {
        quoteFavorites.value = quoteFavorites.value.filter(
          (item) => !sameQuote(item)
        );
        quoteFavoritesTotal.value = Math.max(0, quoteFavoritesTotal.value - 1);
      }
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  function setShareType(type: ForumShareType | ''): void {
    shareType.value = type;
    page.value = 1;
  }

  function setPostSort(
    sortBy: ForumPostSortBy,
    order: ForumSortOrder = 'desc'
  ): void {
    postSortBy.value = sortBy;
    postSortOrder.value = order;
    page.value = 1;
  }

  function setCommentSort(
    sortBy: ForumCommentSortBy,
    order: ForumSortOrder = 'asc'
  ): void {
    commentSortBy.value = sortBy;
    commentSortOrder.value = order;
  }

  function reset(): void {
    const initial = createCommunityInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    posts.value = [];
    total.value = 0;
    page.value = 1;
    shareType.value = '';
    postSortBy.value = 'time';
    postSortOrder.value = 'desc';
    commentSortBy.value = 'time';
    commentSortOrder.value = 'asc';
    myPosts.value = [];
    myPostsTotal.value = 0;
    detail.value = null;
    detailLoading.value = false;
    comments.value = [];
    commentsTotal.value = 0;
    stats.value = null;
    quotes.value = [];
    quotesTotal.value = 0;
    quotesPage.value = 1;
    quotesCategory.value = '';
    quoteFavorites.value = [];
    quoteFavoritesTotal.value = 0;
    dailyQuote.value = null;
    submitting.value = false;
    pendingWrites.clear();
  }

  return {
    loading,
    error,
    initialized,
    ready,
    isEmpty,
    hasMore,
    offset,
    totalPages,
    favoriteCount,
    posts,
    total,
    page,
    pageSize,
    shareType,
    postSortBy,
    postSortOrder,
    commentSortBy,
    commentSortOrder,
    myPosts,
    myPostsTotal,
    detail,
    detailLoading,
    comments,
    commentsTotal,
    stats,
    quotes,
    quotesTotal,
    quotesPage,
    quotesPageSize,
    quotesCategory,
    quoteFavorites,
    quoteFavoritesTotal,
    dailyQuote,
    submitting,
    clearError,
    reset,
    load,
    loadPage,
    loadMore,
    loadStats,
    loadPost,
    loadComments,
    createPost,
    deletePost,
    togglePostLike,
    reactToPost,
    submitComment,
    toggleCommentLike,
    reactToComment,
    loadMyPosts,
    loadUserPublic,
    loadQuotes,
    loadQuoteFavorites,
    loadDailyQuote,
    loadRandomQuote,
    toggleFavorite,
    setShareType,
    setPostSort,
    setCommentSort
  };
});
