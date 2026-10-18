import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import {
  useCommunityStore,
  validateCommentText,
  validatePostDraft
} from '../store';
import {
  createForumPost,
  fetchForumComments,
  fetchForumPostDetail,
  fetchForumPosts,
  fetchQuotes,
  toggleForumPostLike
} from '../api';
import type {
  ForumCommentItem,
  ForumPostItem,
  QuoteItem
} from '../api';

vi.mock('../api', () => ({
  createForumComment: vi.fn(),
  createForumPost: vi.fn(),
  deleteForumPost: vi.fn(),
  fetchDailyQuote: vi.fn(),
  fetchForumComments: vi.fn(),
  fetchForumPostDetail: vi.fn(),
  fetchForumPosts: vi.fn(),
  fetchForumStats: vi.fn(),
  fetchForumUserPublic: vi.fn(),
  fetchMyForumPosts: vi.fn(),
  fetchQuoteFavorites: vi.fn(),
  fetchQuotes: vi.fn(),
  fetchRandomQuote: vi.fn(),
  toggleForumCommentLike: vi.fn(),
  toggleForumPostLike: vi.fn(),
  toggleObsidianQuoteFavorite: vi.fn(),
  toggleQuoteFavorite: vi.fn()
}));

const mockedFetchPosts = vi.mocked(fetchForumPosts);
const mockedFetchDetail = vi.mocked(fetchForumPostDetail);
const mockedFetchComments = vi.mocked(fetchForumComments);
const mockedCreatePost = vi.mocked(createForumPost);
const mockedToggleLike = vi.mocked(toggleForumPostLike);
const mockedFetchQuotes = vi.mocked(fetchQuotes);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function makePost(id: number, overrides: Partial<ForumPostItem> = {}): ForumPostItem {
  return {
    id,
    title: `帖子${id}`,
    content: `内容${id}`,
    likeCount: 0,
    commentCount: 0,
    viewCount: 0,
    createTime: '2026-10-18T10:00:00',
    liked: false,
    ...overrides
  };
}

const commentItem: ForumCommentItem = {
  id: 1,
  content: '第一条评论',
  likeCount: 0,
  createTime: '2026-10-18T10:00:00',
  liked: false
};

const quoteItem: QuoteItem = {
  quote_id: 1,
  content: '为民者民必记之',
  source: '典籍',
  category: '治国',
  author: '古人',
  favorited: false
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('community 表单校验', () => {
  it('标题与内容为空时拒绝', () => {
    expect(validatePostDraft({ title: '  ', content: '内容' })).toBe('请输入标题');
    expect(validatePostDraft({ title: '标题', content: '  ' })).toBe('请输入内容');
  });

  it('评论为空时拒绝', () => {
    expect(validateCommentText('   ')).toBe('评论内容不能为空');
    expect(validateCommentText('正常评论')).toBeNull();
  });
});

describe('community store 列表与分页', () => {
  it('加载首页写入列表与总数', async () => {
    mockedFetchPosts.mockResolvedValue({
      total: 1,
      limit: 8,
      offset: 0,
      posts: [makePost(1)]
    });

    const store = useCommunityStore();
    await store.load({ limit: 8 });

    expect(mockedFetchPosts).toHaveBeenCalledWith({
      shareType: '',
      limit: 8,
      offset: 0
    });
    expect(store.posts).toHaveLength(1);
    expect(store.total).toBe(1);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.hasMore).toBe(false);
  });

  it('loadMore 以已有条数为游标追加下一页', async () => {
    mockedFetchPosts
      .mockResolvedValueOnce({
        total: 3,
        limit: 2,
        offset: 0,
        posts: [makePost(1), makePost(2)]
      })
      .mockResolvedValueOnce({
        total: 3,
        limit: 2,
        offset: 2,
        posts: [makePost(3)]
      });

    const store = useCommunityStore();
    await store.load({ limit: 2 });
    expect(store.hasMore).toBe(true);

    await store.loadMore();

    expect(mockedFetchPosts).toHaveBeenLastCalledWith({
      shareType: '',
      limit: 2,
      offset: 2
    });
    expect(store.posts.map((item) => item.id)).toEqual([1, 2, 3]);
    expect(store.total).toBe(3);
    expect(store.hasMore).toBe(false);
  });

  it('空态与加载失败', async () => {
    mockedFetchPosts.mockResolvedValueOnce({
      total: 0,
      limit: 8,
      offset: 0,
      posts: []
    });
    const store = useCommunityStore();
    await store.load();
    expect(store.isEmpty).toBe(true);

    mockedFetchPosts.mockRejectedValueOnce(new Error('网络连接失败'));
    await store.load();
    expect(store.error).toBe('网络连接失败');
    expect(store.posts).toEqual([]);
    expect(store.ready).toBe(false);
  });
});

describe('community store 帖子详情与评论', () => {
  it('加载详情与评论', async () => {
    mockedFetchDetail.mockResolvedValue(makePost(1, { content: '完整内容' }));
    mockedFetchComments.mockResolvedValue({
      total: 1,
      limit: 200,
      offset: 0,
      comments: [commentItem]
    });

    const store = useCommunityStore();
    await store.loadPost(1);
    await store.loadComments(1);

    expect(store.detail?.content).toBe('完整内容');
    expect(store.comments).toHaveLength(1);
    expect(store.commentsTotal).toBe(1);
  });

  it('点赞结果同步帖子与详情', async () => {
    mockedFetchDetail.mockResolvedValue(makePost(1));
    mockedFetchPosts.mockResolvedValue({
      total: 1,
      limit: 8,
      offset: 0,
      posts: [makePost(1)]
    });
    mockedToggleLike.mockResolvedValue({ liked: true, likeCount: 5 });

    const store = useCommunityStore();
    await store.load();
    await store.loadPost(1);
    await store.togglePostLike(1);

    expect(store.posts[0].liked).toBe(true);
    expect(store.posts[0].likeCount).toBe(5);
    expect(store.detail?.liked).toBe(true);
    expect(store.detail?.likeCount).toBe(5);
  });
});

describe('community store 发帖', () => {
  it('发帖成功插入列表头并递增总数', async () => {
    mockedCreatePost.mockResolvedValue(makePost(9, { title: '新帖' }));

    const store = useCommunityStore();
    const created = await store.createPost({
      title: ' 新帖 ',
      content: ' 新内容 '
    });

    expect(mockedCreatePost).toHaveBeenCalledWith({
      title: '新帖',
      content: '新内容'
    });
    expect(created?.id).toBe(9);
    expect(store.posts[0].id).toBe(9);
    expect(store.total).toBe(1);
    expect(store.submitting).toBe(false);
  });

  it('发帖失败写入错误提示并抛出', async () => {
    mockedCreatePost.mockRejectedValue(new Error('内容包含违规词, 请修改后发布'));

    const store = useCommunityStore();
    await expect(
      store.createPost({ title: '标题', content: '内容' })
    ).rejects.toThrow('内容包含违规词, 请修改后发布');

    expect(store.error).toBe('内容包含违规词, 请修改后发布');
    expect(store.posts).toEqual([]);
    expect(store.submitting).toBe(false);
  });

  it('校验失败不调用接口', async () => {
    const store = useCommunityStore();

    await expect(
      store.createPost({ title: '', content: '内容' })
    ).rejects.toThrow('请输入标题');

    expect(mockedCreatePost).not.toHaveBeenCalled();
    expect(store.error).toBe('请输入标题');
  });

  it('提交中重复发帖被拒绝', async () => {
    const pending = deferred<ForumPostItem>();
    mockedCreatePost.mockReturnValue(pending.promise);

    const store = useCommunityStore();
    const first = store.createPost({ title: '标题', content: '内容' });
    const second = await store.createPost({ title: '标题', content: '内容' });

    expect(second).toBeNull();
    expect(mockedCreatePost).toHaveBeenCalledTimes(1);
    expect(store.submitting).toBe(true);

    pending.resolve(makePost(1));
    await first;
    expect(store.submitting).toBe(false);
  });
});

describe('community store 金句', () => {
  it('金句列表按页加载', async () => {
    mockedFetchQuotes.mockResolvedValue({
      total: 1,
      page: 2,
      page_size: 10,
      items: [quoteItem]
    });

    const store = useCommunityStore();
    await store.loadQuotes({ page: 2, pageSize: 10, category: '治国' });

    expect(mockedFetchQuotes).toHaveBeenCalledWith({
      category: '治国',
      page: 2,
      pageSize: 10
    });
    expect(store.quotes).toHaveLength(1);
    expect(store.quotesTotal).toBe(1);
  });
});
