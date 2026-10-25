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
