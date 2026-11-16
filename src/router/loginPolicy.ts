/**
 * 三端登录准入 · 前端镜像（P2，2026-11-16）
 *
 * 口径来源：后端 `backend/app/core/device_policy.py`（**唯一真源**）。
 * 本文件只做两件事：
 *   1) 路由守卫里判定「这个角色能不能待在设备端」——用于把管理员挡在 /tablet、/mobile 之外；
 *   2) 教师登录后该落到哪个设备端首页（`/tablet|/mobile/teacher/home`）。
 *
 * 为什么前端也要有一份：守卫必须能**同步**决定跳转目标（不能等接口返回），
 * 但真正拒绝登录仍发生在后端；若两边漂移，最坏结果是"多跳一次 / 被后端 403"，
 * 不会造成越权（接口权限没放宽）。改矩阵时**两边同步改**，并跑两侧测试。
 */

export type LoginDevice = 'web' | 'tablet' | 'mobile'
export type DevicePrefix = 'tablet' | 'mobile'

/** 设备端允许的角色（与后端 MOBILE_TABLET_ROLES 默认值一致） */
export const MOBILE_TABLET_ROLES: readonly string[] = ['student', 'teacher']

/** 永久只允许电脑端的角色（后端硬约束，前端只用于跳转/文案） */
export const PC_ONLY_ROLES: readonly string[] = ['admin']

/** 未授权页 reason：管理员在设备端 */
export const REASON_ADMIN_PC_ONLY = 'admin_pc_only'
/** 未授权页 reason：历史"仅学生可用"（保留兼容，学生分支不再使用） */
export const REASON_STUDENT_ONLY = 'mobile_student_only'

export function deviceOfPathPrefix(path: string): DevicePrefix | null {
  if (path.startsWith('/tablet')) return 'tablet'
  if (path.startsWith('/mobile')) return 'mobile'
  return null
}

/** 该角色能否在设备端停留（admin 恒 false；student/teacher 默认 true） */
export function canRoleUseDevice(role: string | null | undefined): boolean {
  const name = String(role || '').toLowerCase()
  if (!name) return false
  if (PC_ONLY_ROLES.includes(name)) return false
  return MOBILE_TABLET_ROLES.includes(name)
}

/** 设备端被拒时给未授权页的 reason；不该拒就返回 null */
export function unauthorizedReasonForDevice(role: string | null | undefined): string | null {
  const name = String(role || '').toLowerCase()
  if (PC_ONLY_ROLES.includes(name)) return REASON_ADMIN_PC_ONLY
  return null
}

/** 教师在各端的首页 */
export function teacherDeviceHome(prefix: DevicePrefix): string {
  return `/${prefix}/teacher/home`
}

/**
 * 教师在设备端访问"学生首页"时改投教师首页。
 * 只映射明确的入口，避免把教师随意浏览的页面（论坛/金句等）也劫持走。
 */
const TEACHER_HOME_ALIASES: Record<DevicePrefix, string[]> = {
  tablet: ['/tablet/home', '/tablet', '/tablet/teacher', '/tablet/teacher/'],
  mobile: ['/mobile/home', '/mobile', '/mobile/teacher', '/mobile/teacher/'],
}

export function resolveTeacherDevicePath(path: string, prefix: DevicePrefix): string | null {
  const aliases = TEACHER_HOME_ALIASES[prefix] || []
  const clean = path.replace(/\/+$/, '') || '/'
  const hit = aliases.some((a) => a.replace(/\/+$/, '') === clean)
  return hit ? teacherDeviceHome(prefix) : null
}

/** 登录失败文案是否属于"设备准入被拒"（后端 detail / 前端兜底文案都覆盖） */
export function isDeviceDeniedMessage(message: string | null | undefined): boolean {
  const text = String(message || '')
  if (!text) return false
  return text.includes('电脑端') || text.includes('仅支持学生') || text.includes('平板端')
}

/** 电脑端登录地址（登录页弹窗引导用） */
export const PC_LOGIN_PATH = '/#/login'
