/**
 * 认证与个人中心（identity）域 Store（P2-76）。
 *
 * 定位：
 *   - **登录态唯一事实来源仍是 `window.__VTJ_AUTH__` / `stores/auth.ts`**；
 *     本 store 只做只读桥接（isLoggedIn / username / role 等 computed），不重复存 token，
 *     也不写 localStorage；
 *   - 本 store 负责后端只读快照（profile / devices / notifications / faq / feedbacks），
 *     写操作（登录、设备移除、反馈提交）全部委托后端或 `__VTJ_AUTH__`；
 *   - 登录动作直接委托 `window.__VTJ_AUTH__.login()`，成功后调用 auth store 的 `refresh()`
 *     重新投影，避免出现第二套凭据状态。
 *
 * 跨域：不 import 其他域外壳；成就解锁事件仅用于刷新通知列表。
 */
import { computed, onScopeDispose, ref } from 'vue';
import { defineStore } from 'pinia';
import { useAuthStore } from '@/stores/auth';
import { useUserProfileStore } from '@/stores/user-profile';
import { EVENT_NAMES, onEvent } from '@/stores/event-bus';
import {
  changePassword as apiChangePassword,
  fetchDevices,
  fetchFaq,
  fetchMyFeedback,
  fetchNotifications,
  fetchProfile,
  removeDevice as apiRemoveDevice,
  revokeAllDevices as apiRevokeAllDevices,
  submitFeedback as apiSubmitFeedback,
  updateProfile as apiUpdateProfile,
  uploadAvatar as apiUploadAvatar,
  type IdentityDevice,
  type IdentityDeviceList,
  type IdentityFaqCategory,
  type IdentityFeedback,
  type IdentityFeedbackInput,
  type IdentityNotification,
  type IdentityProfileUpdate,
  type IdentityUser
} from './api';

export interface IdentityState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createIdentityInitialState(): IdentityState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export interface IdentityLoginInput {
  username: string;
  password: string;
  clientType?: 'web' | 'mobile' | 'tablet';
}

export interface IdentityLoginOutcome {
  success: boolean;
  message: string;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message?: unknown }).message);
  }
  return '请求失败，请稍后重试';
}

/** 读取全局认证模块（与 stores/auth.ts 同一来源） */
function getAuthGlobal(): Window['__VTJ_AUTH__'] | undefined {
  return typeof window === 'undefined' ? undefined : window.__VTJ_AUTH__;
}

export const useIdentityStore = defineStore('identity', () => {
  // ===== 会话派生状态：只读桥接 stores/auth.ts（不存 token） =====
  const authStore = useAuthStore();
  const isLoggedIn = computed(() => authStore.isLoggedIn);
  const username = computed(() => authStore.username ?? '');
  const role = computed(() => authStore.role);
  const userId = computed(() => authStore.userId);

  // ===== 后端只读快照 =====
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const profile = ref<IdentityUser | null>(null);
  const devices = ref<IdentityDevice[]>([]);
  const maxDevices = ref(3);
  const notifications = ref<IdentityNotification[]>([]);
  const faq = ref<IdentityFaqCategory[]>([]);
  const feedbacks = ref<IdentityFeedback[]>([]);
  const feedbackTotal = ref(0);
  const submitting = ref(false);

  const ready = computed(() => initialized.value && error.value === null);
  const displayName = computed(() => profile.value?.username || username.value);
  const avatar = computed(() => profile.value?.avatar ?? '');
  const unreadCount = computed(() => notifications.value.length);

  function applyProfile(next: IdentityUser): void {
    profile.value = next;
    // 昵称 / 头像同步到共享只读缓存（user-profile 不反向写本域）
    useUserProfileStore().applySnapshot({
      nickname: next.username,
      avatar: next.avatar ?? '',
      role: next.user_type
    });
  }

  async function loadProfile(): Promise<IdentityUser | null> {
    loading.value = true;
    error.value = null;
    try {
      const next = await fetchProfile();
      applyProfile(next);
      return next;
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadDevices(): Promise<IdentityDevice[]> {
    try {
      const result: IdentityDeviceList = await fetchDevices();
      devices.value = result.devices ?? [];
      maxDevices.value = result.max_devices ?? 3;
      return devices.value;
    } catch (e) {
      error.value = errorMessage(e);
      return devices.value;
    }
  }

  async function loadNotifications(): Promise<IdentityNotification[]> {
    try {
      notifications.value = await fetchNotifications();
      return notifications.value;
    } catch (e) {
      error.value = errorMessage(e);
      return notifications.value;
    }
  }

  async function loadFaq(): Promise<IdentityFaqCategory[]> {
    loading.value = true;
    error.value = null;
    try {
      faq.value = await fetchFaq();
      return faq.value;
    } catch (e) {
      error.value = errorMessage(e);
      return faq.value;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadMyFeedback(): Promise<IdentityFeedback[]> {
    loading.value = true;
    error.value = null;
    try {
      const result = await fetchMyFeedback();
      feedbacks.value = result.items ?? [];
      feedbackTotal.value = result.total ?? feedbacks.value.length;
      return feedbacks.value;
    } catch (e) {
      error.value = errorMessage(e);
      return feedbacks.value;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  /**
   * 登录：校验 → 委托 `__VTJ_AUTH__.login()` → 刷新 auth store → 拉取档案。
   * 本 store 不接触 token，也不写 localStorage。
   */
  async function login(input: IdentityLoginInput): Promise<IdentityLoginOutcome> {
    const account = (input.username || '').trim();
    const password = input.password || '';
    if (!account) {
      error.value = '请输入用户名';
      return { success: false, message: error.value };
    }
    if (!password) {
      error.value = '请输入密码';
      return { success: false, message: error.value };
    }

    const globalAuth = getAuthGlobal();
    if (!globalAuth || typeof globalAuth.login !== 'function') {
      error.value = '认证模块未就绪，请刷新页面重试';
      return { success: false, message: error.value };
    }

    loading.value = true;
    error.value = null;
    try {
      const result = await globalAuth.login(account, password, input.clientType ?? 'web');
      if (!result?.success) {
        error.value = result?.message || '登录失败，请检查用户名和密码';
        return { success: false, message: error.value };
      }
      // 唯一事实来源已更新：重新投影到 auth store
      authStore.refresh();
      await loadProfile();
      return { success: true, message: result.message || '登录成功' };
    } catch (e) {
      error.value = errorMessage(e);
      return { success: false, message: error.value };
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  /** 退出登录：委托 auth store（其内部清理 __VTJ_AUTH__ 凭据） */
  function logout(): void {
    authStore.logout();
    reset();
  }

  /** 移除设备后刷新列表 */
  async function removeDevice(deviceId: string): Promise<boolean> {
    try {
      await apiRemoveDevice(deviceId);
      await loadDevices();
      return true;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    }
  }

  /** 强制下线所有设备后清空列表 */
  async function revokeAllDevices(): Promise<boolean> {
    try {
      await apiRevokeAllDevices();
      devices.value = [];
      return true;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    }
  }

  async function saveProfile(payload: IdentityProfileUpdate): Promise<boolean> {
    try {
      const result = await apiUpdateProfile(payload);
      if (result?.user) applyProfile(result.user);
      return result?.success !== false;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    }
  }

  async function changePassword(newPassword: string, oldPassword?: string): Promise<boolean> {
    try {
      const result = await apiChangePassword(newPassword, oldPassword);
      return result?.success !== false;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    }
  }

  async function uploadAvatar(file: File): Promise<string | null> {
    try {
      const result = await apiUploadAvatar(file);
      if (result?.avatar_url && profile.value) {
        profile.value = { ...profile.value, avatar: result.avatar_url };
      }
      return result?.avatar_url ?? null;
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    }
  }

  /** 提交反馈（内容校验在前端先挡一次，后端仍会复核） */
  async function submitFeedback(input: IdentityFeedbackInput): Promise<boolean> {
    const content = (input.content || '').trim();
    if (!content) {
      error.value = '请填写反馈内容';
      return false;
    }
    if (content.length > 1000) {
      error.value = '反馈内容过长（最多1000字）';
      return false;
    }
    if (submitting.value) return false;

    submitting.value = true;
    error.value = null;
    try {
      await apiSubmitFeedback({ ...input, content });
      await loadMyFeedback();
      return true;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    } finally {
      submitting.value = false;
    }
  }

  /**
   * 首次加载：仅在已登录时拉取 profile / devices / notifications；
   * 未登录直接置 initialized，避免登录页触发 401 跳转。
   */
  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      authStore.refresh();
      if (!authStore.isLoggedIn) {
        profile.value = null;
        devices.value = [];
        notifications.value = [];
        return;
      }
      const results = await Promise.allSettled([
        fetchProfile(),
        fetchDevices(),
        fetchNotifications()
      ]);
      if (results[0].status === 'fulfilled') applyProfile(results[0].value);
      if (results[1].status === 'fulfilled') {
        devices.value = results[1].value.devices ?? [];
        maxDevices.value = results[1].value.max_devices ?? 3;
      }
      if (results[2].status === 'fulfilled') notifications.value = results[2].value ?? [];
      const rejected = results.find((item) => item.status === 'rejected');
      if (rejected && rejected.status === 'rejected') {
        error.value = errorMessage(rejected.reason);
      }
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  function reset(): void {
    const initial = createIdentityInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    profile.value = null;
    devices.value = [];
    maxDevices.value = 3;
    notifications.value = [];
    faq.value = [];
    feedbacks.value = [];
    feedbackTotal.value = 0;
    submitting.value = false;
  }

  // ===== 订阅：成就解锁后刷新通知（不 import 其他域） =====
  const offAchievement = onEvent(EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED, () => {
    if (initialized.value && authStore.isLoggedIn) {
      void loadNotifications();
    }
  });
  onScopeDispose(offAchievement);

  return {
    // 会话派生（只读桥接）
    isLoggedIn,
    username,
    role,
    userId,
    // 状态
    loading,
    error,
    initialized,
    profile,
    devices,
    maxDevices,
    notifications,
    faq,
    feedbacks,
    feedbackTotal,
    submitting,
    // getters
    ready,
    displayName,
    avatar,
    unreadCount,
    // actions
    load,
    loadProfile,
    loadDevices,
    loadNotifications,
    loadFaq,
    loadMyFeedback,
    login,
    logout,
    removeDevice,
    revokeAllDevices,
    saveProfile,
    changePassword,
    uploadAvatar,
    submitFeedback,
    reset
  };
});
