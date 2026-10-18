import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useAboutStore } from '../store';
import { fetchAboutProfile } from '../api';
import { PUBLISHED_EVENTS, SUBSCRIBED_EVENTS } from '../events';

vi.mock('../api', () => ({
  fetchAboutInfo: vi.fn(),
  fetchAboutContact: vi.fn(),
  fetchAboutProfile: vi.fn(),
  refreshAbout: vi.fn()
}));

const mockedFetchProfile = vi.mocked(fetchAboutProfile);

const PROFILE = {
  info: {
    status: 'healthy',
    service: '公安联考题库系统',
    version: '1.0.0'
  },
  contact: {
    email: 'service@lianzhi.com',
    hotline: '400-000-0000',
    copyright: '© 2025 砺安题库'
  }
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('about store 只读配置', () => {
  it('加载成功后写入版本号与联系方式', async () => {
    mockedFetchProfile.mockResolvedValue(PROFILE);

    const store = useAboutStore();
    await store.load();

    expect(mockedFetchProfile).toHaveBeenCalledTimes(1);
    expect(store.version).toBe('1.0.0');
    expect(store.service).toBe('公安联考题库系统');
    expect(store.info?.status).toBe('healthy');
    expect(store.contact?.email).toBe('service@lianzhi.com');
    expect(store.contact?.hotline).toBe('400-000-0000');
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('错误态：加载失败写入 error，版本号为空', async () => {
    mockedFetchProfile.mockRejectedValue(new Error('服务不可用'));

    const store = useAboutStore();
    await store.load();

    expect(store.error).toBe('服务不可用');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.info).toBeNull();
    expect(store.version).toBe('');
    expect(store.service).toBe('');
  });
});

describe('about store 重置与事件契约', () => {
  it('reset 清空配置并回到初始契约', async () => {
    mockedFetchProfile.mockResolvedValue(PROFILE);

    const store = useAboutStore();
    await store.load();
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.info).toBeNull();
    expect(store.contact).toBeNull();
    expect(store.version).toBe('');
  });

  it('events.ts 不导出任何事件常量（本域零事件）', () => {
    expect(Object.keys(PUBLISHED_EVENTS)).toEqual([]);
    expect(Object.keys(SUBSCRIBED_EVENTS)).toEqual([]);
  });
});
