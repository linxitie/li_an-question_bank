/**
 * 认证 Pinia Store（P1-10）
 *
 * 定位：`window.__VTJ_AUTH__`（src/auth.ts）的**只读桥接层**。
 *   - 唯一凭据来源仍是 `window.__VTJ_AUTH__` / localStorage 的 `__VTJ_AUTH_STATE__`；
 *   - 本 store **不复制**登录、刷新、token 过期判断逻辑，也不做任何凭据写入；
 *   - 仅把全局认证状态投影为响应式的 Pinia state，供组件/computed 消费。
 *
 * 同步时机：store 首次创建、`refresh()` / `ensureAuth()` / `logout()` 调用后，
 * 以及浏览器跨标签页 `storage` 事件触发时。
 */
import { computed, onScopeDispose, ref } from 'vue';
import { defineStore } from 'pinia';

/** 从全局认证模块读取状态（可能尚未初始化） */
function getAuthGlobal(): Window['__VTJ_AUTH__'] | undefined {
  return typeof window === 'undefined' ? undefined : window.__VTJ_AUTH__;
}

export const useAuthStore = defineStore('auth', () => {
  // ===== 全局状态的响应式快照 =====
  const token = ref<string | null>(null);
  const username = ref<string | null>(null);
  const userId = ref<number | null>(null);
  const role = ref<string | null>(null);
  const roleLevel = ref(0);
  const permissions = ref<string[]>([]);
  /**
   * 是否已登录。
   * 判定口径 = 全局认证态中存在 token（真实过期拦截由 apiFetch / interceptors 负责），
   * 不在此重复实现 JWT 解析，避免与 src/auth.ts 产生第二套逻辑。
   */
  const isLoggedIn = ref(false);

  /** 语义别名（实施计划 P1-10 使用 isAuthenticated） */
  const isAuthenticated = computed(() => isLoggedIn.value);

  /** 角色便捷判断 */
  const isStudent = computed(() => role.value === 'student');
  const isTeacher = computed(() => role.value === 'teacher');
  const isAdmin = computed(() => role.value === 'admin');

  /** 从全局认证模块重新投影状态 */
  function refresh(): boolean {
    const auth = getAuthGlobal();
    if (!auth) {
      token.value = null;
      username.value = null;
      userId.value = null;
      role.value = null;
      roleLevel.value = 0;
      permissions.value = [];
      isLoggedIn.value = false;
      return false;
    }

    const state = auth.getState() ?? {};
    token.value = state.token ?? null;
    username.value = state.username ?? auth.getUsername?.() ?? null;

    let info: { role?: string | null; roleLevel?: number; permissions?: string[]; userId?: number | null } = {};
    try {
      info = auth.parseUserInfo?.() ?? {};
    } catch {
      info = {};
    }
    role.value = info.role ?? null;
    userId.value = info.userId ?? null;
    roleLevel.value = info.roleLevel ?? 0;
    permissions.value = info.permissions ?? [];
    isLoggedIn.value = !!token.value;

    return isLoggedIn.value;
  }

  /** 确保已认证（token 过期时由全局模块尝试 refresh） */
  async function ensureAuth(): Promise<boolean> {
    const auth = getAuthGlobal();
    if (!auth || typeof auth.ensureAuth !== 'function') {
      refresh();
      return isLoggedIn.value;
    }
    const ok = await auth.ensureAuth();
    refresh();
    return ok;
  }

  /** 退出登录（委托全局模块清理凭据与同步 socket） */
  function logout(): void {
    getAuthGlobal()?.logout();
    refresh();
  }

  /** 是否拥有指定角色（委托全局判定，不复制权限规则） */
  function hasRole(target: string): boolean {
    return getAuthGlobal()?.hasRole?.(target) ?? role.value === target;
  }

  /** 是否拥有指定权限 */
  function hasPermission(permission: string): boolean {
    return getAuthGlobal()?.hasPermission?.(permission) ?? permissions.value.includes(permission);
  }

  // ===== 与全局认证态保持同步 =====
  // 跨标签页登录/登出会改动 localStorage，借此刷新快照。
  if (typeof window !== 'undefined') {
    const onStorage = (event: StorageEvent) => {
      if (!event.key || event.key === '__VTJ_AUTH_STATE__') refresh();
    };
    window.addEventListener('storage', onStorage);
    onScopeDispose(() => window.removeEventListener('storage', onStorage));
  }

  // 首次创建即同步一次
  refresh();

  return {
    // state
    token,
    username,
    userId,
    role,
    roleLevel,
    permissions,
    isLoggedIn,
    // getters
    isAuthenticated,
    isStudent,
    isTeacher,
    isAdmin,
    // actions
    refresh,
    ensureAuth,
    logout,
    hasRole,
    hasPermission
  };
});
