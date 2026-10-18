/**
 * identity 域 store 测试（P2-80）。
 *
 * 覆盖：只读桥接 auth store、档案/设备/通知加载、登录委托 __VTJ_AUTH__、
 * 设备移除、反馈校验与防重、成就事件触发通知刷新、reset。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useAuthStore } from '@/stores/auth';
import { useIdentityStore } from '../store';
import {
  fetchDevices,
  fetchNotifications,
  fetchProfile,
  removeDevice as apiRemoveDevice,
  revokeAllDevices as apiRevokeAllDevices,
  submitFeedback as apiSubmitFeedback,
  updateProfile as apiUpdateProfile
} from '../api';
import { EVENT_NAMES, clearAllEvents, emitEvent } from '@/stores/event-bus';

vi.mock('../api', () => ({
  loginWithPassword: vi.fn(),
  refreshAccessToken: vi.fn(),
  fetchProfile: vi.fn(),
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
  uploadAvatar: vi.fn(),
  fetchDevices: vi.fn(),
  removeDevice: vi.fn(),
  revokeAllDevices: vi.fn(),
  fetchNotifications: vi.fn(),
  fetchFaq: vi.fn(),
  fetchMyFeedback: vi.fn(),
  submitFeedback: vi.fn()
}));

const mockedFetchProfile = vi.mocked(fetchProfile);
const mockedFetchDevices = vi.mocked(fetchDevices);
const mockedFetchNotifications = vi.mocked(fetchNotifications);
const mockedRemoveDevice = vi.mocked(apiRemoveDevice);
const mockedRevokeAll = vi.mocked(apiRevokeAllDevices);
const mockedSubmitFeedback = vi.mocked(apiSubmitFeedback);
const mockedUpdateProfile = vi.mocked(apiUpdateProfile);

function seedAuthGlobal(token = 'fake-token', userType = 'student') {
  const state = { token, user_type: userType, username: 'tester', user_id: 7 };
  (globalThis as Record<string, unknown>).window = {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    __VTJ_AUTH__: {
      getState: () => state,
      isLoggedIn: () => Boolean(token),
      parseUserInfo: () => ({ role: userType, userId: 7, username: 'tester' }),
      login: vi.fn(),
      logout: vi.fn(),
      ensureAuth: vi.fn()
    }
  };
  return state;
}

function seedProfile(overrides: Record<string, unknown> = {}) {
  return {
    user_id: 7,
    user_no: 'S000007',
    username: 'tester',
    user_type: 'student',
    role_level: 1,
    status: 1,
    total_coins: 0,
    phone: null,
    email: null,
    avatar: '',
    create_time: null,
    ...overrides
  } as unknown as import('../api').IdentityUser;
}

beforeEach(() => {
  vi.clearAllMocks();
  clearAllEvents();
  seedAuthGlobal();
  setActivePinia(createPinia());
  useAuthStore().refresh();
});

describe('会话派生（只读桥接 auth store）', () => {
  it('登录态/用户名/角色投影自 auth store', () => {
    const auth = useAuthStore();
    const store = useIdentityStore();
    expect(store.isLoggedIn).toBe(auth.isLoggedIn);
    expect(store.username).toBe('tester');
    expect(store.role).toBe('student');
    expect(store.userId).toBe(7);
  });
});

describe('load()', () => {
  it('已登录时并行拉取 profile/devices/notifications', async () => {
    mockedFetchProfile.mockResolvedValue(seedProfile());
    mockedFetchDevices.mockResolvedValue({ devices: [], max_devices: 3 });
    mockedFetchNotifications.mockResolvedValue([]);

    const store = useIdentityStore();
    await store.load();

    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.profile?.username).toBe('tester');
    expect(mockedFetchProfile).toHaveBeenCalledTimes(1);
    expect(mockedFetchDevices).toHaveBeenCalledTimes(1);
    expect(mockedFetchNotifications).toHaveBeenCalledTimes(1);
  });

  it('未登录时不发请求并直接置 initialized', async () => {
    seedAuthGlobal('');
    const store = useIdentityStore();
    await store.load();
    expect(mockedFetchProfile).not.toHaveBeenCalled();
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('部分失败时保留成功部分并记录错误', async () => {
    mockedFetchProfile.mockResolvedValue(seedProfile());
    mockedFetchDevices.mockRejectedValue(new Error('devices 500'));
    mockedFetchNotifications.mockResolvedValue([]);

    const store = useIdentityStore();
    await store.load();

    expect(store.profile?.username).toBe('tester');
    expect(store.error).toBe('devices 500');
    expect(store.initialized).toBe(true);
  });
});

describe('login / logout', () => {
  it('登录成功委托 __VTJ_AUTH__.login 并刷新 auth store + 拉档案', async () => {
    const auth = useAuthStore();
    const globalAuth = (globalThis as unknown as { window: { __VTJ_AUTH__: { login: ReturnType<typeof vi.fn> } } }).window.__VTJ_AUTH__;
    vi.mocked(globalAuth.login).mockResolvedValue({ success: true, message: 'ok' });
    mockedFetchProfile.mockResolvedValue(seedProfile());

    const store = useIdentityStore();
    const outcome = await store.login({ username: 'tester', password: 'pwd' });

    expect(outcome.success).toBe(true);
    expect(globalAuth.login).toHaveBeenCalledWith('tester', 'pwd', 'web');
    expect(auth.username).toBe('tester');
    expect(store.profile?.username).toBe('tester');
  });

  it('空用户名/空密码前置校验不发请求', async () => {
    const store = useIdentityStore();
    const r1 = await store.login({ username: '', password: 'pwd' });
    expect(r1.success).toBe(false);
    expect(r1.message).toBe('请输入用户名');
    const r2 = await store.login({ username: 'tester', password: '' });
    expect(r2.message).toBe('请输入密码');
  });

  it('登录失败透传后端消息', async () => {
    const globalAuth = (globalThis as unknown as { window: { __VTJ_AUTH__: { login: ReturnType<typeof vi.fn> } } }).window.__VTJ_AUTH__;
    vi.mocked(globalAuth.login).mockResolvedValue({ success: false, message: '密码错误' });
    const store = useIdentityStore();
    const outcome = await store.login({ username: 'tester', password: 'bad' });
    expect(outcome.success).toBe(false);
    expect(outcome.message).toBe('密码错误');
  });
});

describe('设备与档案写操作', () => {
  it('removeDevice 成功后刷新设备列表', async () => {
    mockedRemoveDevice.mockResolvedValue({ message: 'ok' });
    mockedFetchDevices.mockResolvedValue({ devices: [], max_devices: 3 });
    const store = useIdentityStore();
    const ok = await store.removeDevice('dev-1');
    expect(ok).toBe(true);
    expect(mockedFetchDevices).toHaveBeenCalledTimes(1);
  });

  it('revokeAllDevices 成功后清空列表', async () => {
    mockedRevokeAll.mockResolvedValue({ message: 'ok' });
    const store = useIdentityStore();
    store.devices.push({ device_id: 'd1' } as never);
    const ok = await store.revokeAllDevices();
    expect(ok).toBe(true);
    expect(store.devices).toHaveLength(0);
  });

  it('saveProfile 成功后回写档案并同步 user-profile 快照', async () => {
    mockedUpdateProfile.mockResolvedValue({
      success: true,
      user: seedProfile({ username: 'newname', avatar: '/a.png' })
    });
    const store = useIdentityStore();
    const ok = await store.saveProfile({ email: 'new@test.com' });
    expect(ok).toBe(true);
    expect(store.displayName).toBe('newname');
    expect(store.avatar).toBe('/a.png');
  });
});

describe('反馈提交', () => {
  it('空内容/超长内容前置拦截', async () => {
    const store = useIdentityStore();
    expect(await store.submitFeedback({ content: '  ', category: '功能异常' })).toBe(false);
    expect(store.error).toBe('请填写反馈内容');
    expect(await store.submitFeedback({ content: 'x'.repeat(1001), category: '功能异常' })).toBe(false);
    expect(mockedSubmitFeedback).not.toHaveBeenCalled();
  });

  it('提交成功后刷新我的反馈', async () => {
    mockedSubmitFeedback.mockResolvedValue({ feedback_id: 1, message: 'ok' });
    vi.mocked((await import('../api')).fetchMyFeedback).mockResolvedValue({ total: 1, page: 1, page_size: 10, items: [] });
    const store = useIdentityStore();
    const ok = await store.submitFeedback({ content: '页面有 bug', category: '功能异常' });
    expect(ok).toBe(true);
    expect(mockedSubmitFeedback).toHaveBeenCalledTimes(1);
  });
});

describe('成就解锁事件 → 通知刷新', () => {
  it('已登录且初始化后，收到成就解锁事件会刷新通知', async () => {
    mockedFetchNotifications.mockResolvedValue([]);
    const store = useIdentityStore();
    await store.load();
    mockedFetchNotifications.mockClear();

    emitEvent(EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED, { title: '新成就' });
    await Promise.resolve();
    await Promise.resolve();

    expect(mockedFetchNotifications).toHaveBeenCalledTimes(1);
  });
});

describe('reset', () => {
  it('恢复到初始状态', async () => {
    mockedFetchProfile.mockResolvedValue(seedProfile({ username: 'x' }));
    const store = useIdentityStore();
    await store.load();
    store.reset();
    expect(store.initialized).toBe(false);
    expect(store.profile).toBeNull();
    expect(store.devices).toHaveLength(0);
    expect(store.notifications).toHaveLength(0);
  });
});
