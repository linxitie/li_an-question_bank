// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useCommunityStore } from '@/modules/community/store';

import TabletForumDetail from '../tablet_forum_detail.vue';

const h = vi.hoisted(() => ({
  routeState: { id: '4' },
  back: vi.fn(),
  push: vi.fn()
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: h.routeState.id } }),
  useRouter: () => ({ back: h.back, push: h.push })
}));

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn() }
}));

const STUBS = {
  UserBadge: {
    name: 'UserBadge',
    props: ['src', 'name', 'userId', 'userType', 'size', 'avatarOnly', 'clickable'],
    template: '<span class="stub-user-badge" />'
  },
  ForumContent: { name: 'ForumContent', props: ['content'], template: '<div class="stub-content" />' },
  AttachmentList: {
    name: 'AttachmentList',
    props: ['attachments', 'mode'],
    template: '<div class="stub-attachments" />'
  },
  CommentSortBar: { name: 'CommentSortBar', props: ['sortBy', 'order'], template: '<div class="stub-sort" />' },
  FileUploader: { name: 'FileUploader', props: ['modelValue', 'maxDocs'], template: '<div class="stub-uploader" />' },
  EmojiStickerPicker: { name: 'EmojiStickerPicker', template: '<div class="stub-picker" />' }
};

const SAMPLE_POST = {
  id: 4,
  title: '测试标题',
  content: '帖子正文内容',
  titleColor: null,
  attachments: [
    { name: 'a.pdf', url: '/uploads/forum/x.pdf', size: 1024, type: 'application/pdf' }
  ],
  likeCount: 1,
  commentCount: 11,
  viewCount: 5,
  liked: false,
  createTime: '2026-10-25T11:02:29.272368',
  user: { id: 3, nickname: '闲者', avatar: '/uploads/avatars/avatar_3_aca778e0.jpg' }
};

const mountPage = () =>
  mount(TabletForumDetail, { global: { stubs: STUBS } });

describe('TabletForumDetail 骨架', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    h.routeState.id = '4';
    h.back.mockClear();
    h.push.mockClear();
  });

  it('渲染顶部栏、返回按钮与标题', async () => {
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('.topbar').exists()).toBe(true);
    expect(wrapper.find('.back-btn').exists()).toBe(true);
    expect(wrapper.find('h1.title').text()).toBe('帖子详情');
  });

  it('没有浏览历史时返回平板论坛列表', async () => {
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.find('.back-btn').trigger('click');

    expect(h.push).toHaveBeenCalledWith('/tablet/forum');
  });

  it('帖子不存在时显示错误态', async () => {
    const store = useCommunityStore();
    vi.spyOn(store, 'loadPost').mockResolvedValue(null);

    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('.state-error').text()).toContain('帖子不存在或已被删除');
  });

  it('帖子 id 非数字时显示错误态且不请求接口', async () => {
    h.routeState.id = 'abc';
    const store = useCommunityStore();
    const spy = vi.spyOn(store, 'loadPost').mockResolvedValue(null);

    const wrapper = mountPage();
    await flushPromises();

    expect(spy).not.toHaveBeenCalled();
    expect(wrapper.find('.state-error').text()).toContain('帖子不存在或已被删除');
  });
});

describe('TabletForumDetail 帖子区', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    h.routeState.id = '4';
    h.back.mockClear();
    h.push.mockClear();
  });

  it('渲染标题、作者头像与附件', async () => {
    const store = useCommunityStore();
    vi.spyOn(store, 'loadPost').mockResolvedValue(SAMPLE_POST as any);
    vi.spyOn(store, 'loadComments').mockResolvedValue(undefined);
    store.detail = SAMPLE_POST as any;

    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('.post-title').text()).toBe('测试标题');
    expect(wrapper.findComponent({ name: 'UserBadge' }).props('src')).toBe(
      '/uploads/avatars/avatar_3_aca778e0.jpg'
    );
    expect(wrapper.findComponent({ name: 'AttachmentList' }).props('mode')).toBe('post');
    expect(wrapper.find('.stub-content').exists()).toBe(true);
  });

  it('点赞按钮调用 reactToPost', async () => {
    const store = useCommunityStore();
    const spy = vi.spyOn(store, 'reactToPost').mockResolvedValue(undefined as any);
    vi.spyOn(store, 'loadPost').mockResolvedValue(SAMPLE_POST as any);
    vi.spyOn(store, 'loadComments').mockResolvedValue(undefined);
    store.detail = SAMPLE_POST as any;

    const wrapper = mountPage();
    await flushPromises();
    await wrapper.find('.like-btn').trigger('click');

    expect(spy).toHaveBeenCalledWith(4, 'like');
  });
});

describe('TabletForumDetail 评论区', () => {
  const SAMPLE_COMMENTS = [
    {
      id: 21,
      content: '.',
      parentCommentId: null,
      user: { id: 3, nickname: '闲者', avatar: '/uploads/avatars/avatar_3_aca778e0.jpg' },
      attachments: [],
      likeCount: 1,
      reactions: {},
      createTime: '2026-10-25T11:02:29.272368'
    },
    {
      id: 22,
      content: '回复内容',
      parentCommentId: 21,
      user: { id: 3, nickname: '闲者', avatar: '/uploads/avatars/avatar_3_aca778e0.jpg' },
      attachments: [],
      likeCount: 0,
      reactions: {},
      createTime: '2026-10-25T11:03:29.272368'
    }
  ];

  beforeEach(() => {
    setActivePinia(createPinia());
    h.routeState.id = '4';
    h.back.mockClear();
    h.push.mockClear();
  });

  const prepare = () => {
    const store = useCommunityStore();
    vi.spyOn(store, 'loadPost').mockResolvedValue(SAMPLE_POST as any);
    vi.spyOn(store, 'loadComments').mockResolvedValue(undefined);
    store.detail = SAMPLE_POST as any;
    store.comments = SAMPLE_COMMENTS as any;
    return store;
  };

  it('根评论与回复分两层渲染，评论头像透传', async () => {
    prepare();
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.findAll('.comment-list > .comment-item')).toHaveLength(1);
    expect(wrapper.findAll('.comment-replies .comment-item')).toHaveLength(1);
    expect(wrapper.find('.comment-item .stub-user-badge').exists()).toBe(true);
  });

  it('切换排序会重新加载评论', async () => {
    const store = prepare();
    const spy = vi.spyOn(store, 'loadComments').mockResolvedValue(undefined);
    const wrapper = mountPage();
    await flushPromises();

    wrapper.findComponent({ name: 'CommentSortBar' }).vm.$emit('update:sortBy', 'likes');
    await flushPromises();

    expect(spy).toHaveBeenLastCalledWith(4, { sortBy: 'likes', order: 'asc' });
  });

  it('评论点赞调用 reactToComment', async () => {
    const store = prepare();
    const spy = vi.spyOn(store, 'reactToComment').mockResolvedValue(undefined as any);
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.find('.comment-like').trigger('click');

    expect(spy).toHaveBeenCalledWith(21, 'like');
  });
});

describe('TabletForumDetail 评论输入栏', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    h.routeState.id = '4';
    h.back.mockClear();
    h.push.mockClear();
  });

  const prepare = () => {
    const store = useCommunityStore();
    vi.spyOn(store, 'loadPost').mockResolvedValue(SAMPLE_POST as any);
    vi.spyOn(store, 'loadComments').mockResolvedValue(undefined);
    store.detail = SAMPLE_POST as any;
    store.comments = [] as any;
    return store;
  };

  it('选择 emoji 写入输入框，表情包写 sticker 标记', async () => {
    prepare();
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.find('.emoji-btn').trigger('click');
    wrapper.findComponent({ name: 'EmojiStickerPicker' }).vm.$emit('select', { type: 'emoji', value: '🥰' });
    await flushPromises();
    expect((wrapper.find('.comment-input').element as HTMLInputElement).value).toBe('🥰');

    wrapper.findComponent({ name: 'EmojiStickerPicker' }).vm.$emit('select', {
      type: 'sticker',
      value: '/uploads/stickers/a.png'
    });
    await flushPromises();
    expect((wrapper.find('.comment-input').element as HTMLInputElement).value).toBe(
      '🥰[[sticker:/uploads/stickers/a.png]]'
    );
  });

  it('空内容不发送，有内容时提交', async () => {
    const store = prepare();
    const spy = vi.spyOn(store, 'submitComment').mockResolvedValue(undefined as any);
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.find('.send-btn').trigger('click');
    expect(spy).not.toHaveBeenCalled();

    await wrapper.find('.comment-input').setValue('你好');
    await wrapper.find('.send-btn').trigger('click');
    await flushPromises();

    expect(spy).toHaveBeenCalledWith(4, {
      content: '你好',
      parentCommentId: null,
      attachments: undefined
    });
  });

  it('发送失败时保留输入内容', async () => {
    const store = prepare();
    vi.spyOn(store, 'submitComment').mockRejectedValue(new Error('未登录'));
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.find('.comment-input').setValue('不能丢的内容');
    await wrapper.find('.send-btn').trigger('click');
    await flushPromises();

    expect((wrapper.find('.comment-input').element as HTMLInputElement).value).toBe('不能丢的内容');
  });
});
