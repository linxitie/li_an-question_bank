/**
 * 路由访问判定。
 *
 * 规则：
 * - `meta.roles` 与 `meta.permissions` 同时存在时，两者都要满足；
 * - admin 角色可绕过 roles 限制（保持既有行为），但 permissions 仍需满足；
 * - 没有 roles/permissions 的路由默认放行。
 */
export interface RouteAccessMeta {
  roles?: string[];
  permissions?: string[];
}

export function canAccess(
  meta: RouteAccessMeta | undefined | null,
  role: string | null | undefined,
  permissions: string[] | null | undefined
): boolean {
  const granted = permissions ?? [];

  if (meta?.permissions?.length) {
    const missing = meta.permissions.some((p) => !granted.includes(p));
    if (missing) return false;
  }

  if (meta?.roles?.length) {
    if (role === 'admin') return true;
    if (!role || !meta.roles.includes(role)) return false;
  }

  return true;
}
