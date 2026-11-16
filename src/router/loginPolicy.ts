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

/* ==========================================================================
 * 设备 × 界面一致性（D-28，2026-11-16）
 *
 * 实测缺陷：`/#/tablet/home`、`/#/mobile/teacher/papers` 在**电脑**上直接渲染成了
 * 平板/手机界面；`/#/teacher/dashboard` 在**手机/平板**上直接渲染成了电脑版教师端。
 * 原因：守卫只有「PC 路径 → 设备路径」单向映射，没有反向校验。
 *
 * 本段只提供**纯映射函数**，是否跳转由 `src/router/index.ts` 的守卫决定
 * （守卫要结合登录态与角色，纯函数不掺业务）。
 * ========================================================================== */

/** 设备端路径 → 电脑端等价路径；没有等价页返回 null（调用方兜底到 '/'） */
const DEVICE_TO_PC: Record<string, string> = {
  '/tablet/login': '/login',
  '/mobile/login': '/login',
  '/tablet/home': '/home',
  '/mobile/home': '/home',
  '/tablet/question-bank': '/question-bank',
  '/mobile/question-bank': '/question-bank',
  '/tablet/forum': '/forum',
  '/mobile/forum': '/forum',
  '/tablet/practice': '/practice',
  '/mobile/practice': '/practice',
  '/tablet/profile': '/profile',
  '/mobile/profile': '/profile',
  '/tablet/news': '/news',
  '/mobile/news': '/news',
  '/tablet/quotes': '/quotes',
  '/mobile/quotes': '/quotes',
  '/tablet/recruit': '/recruit',
  '/mobile/recruit': '/recruit',
  '/tablet/materials': '/materials/xingce',
  '/mobile/materials': '/materials/xingce',
  '/tablet/teacher/home': '/teacher/dashboard',
  '/mobile/teacher/home': '/teacher/dashboard',
  '/tablet/teacher/questions': '/teacher/questions',
  '/mobile/teacher/questions': '/teacher/questions',
  '/tablet/teacher/papers': '/teacher/papers',
  '/mobile/teacher/papers': '/teacher/papers',
  '/tablet/teacher/scores': '/teacher/scores',
  '/mobile/teacher/scores': '/teacher/scores',
}

function normalizePath(path: string): string {
  const clean = String(path || '/').split('?')[0].replace(/\/+$/, '')
  return clean || '/'
}

/** 设备端路径 → 电脑端等价路径（无等价返回 null） */
export function pcPathForDevicePath(path: string): string | null {
  return DEVICE_TO_PC[normalizePath(path)] ?? null
}

/** 换个设备前缀：/tablet/a → /mobile/a，/mobile/a → /tablet/a；无前缀返回 null */
export function swapDevicePrefix(path: string, target: DevicePrefix): string | null {
  const clean = normalizePath(path)
  const current = deviceOfPathPrefix(clean)
  if (!current || current === target) return null
  return `/${target}${clean.slice(current.length + 1)}`
}

/** 电脑端路径 → 设备端等价路径（教师端为主；无对应设备页返回 null） */
export function devicePathForPcPath(
  path: string,
  prefix: DevicePrefix
): string | null {
  const clean = normalizePath(path)
  const exact: Record<string, string> = {
    '/teacher/dashboard': `/${prefix}/teacher/home`,
    '/teacher': `/${prefix}/teacher/home`,
    '/teacher/questions': `/${prefix}/teacher/questions`,
    '/teacher/papers': `/${prefix}/teacher/papers`,
    '/teacher/scores': `/${prefix}/teacher/scores`,
    '/teacher/forum': `/${prefix}/forum`,
    '/question-import': `/${prefix}/teacher/questions`,
  }
  if (exact[clean]) return exact[clean]
  // 教师端其它 PC 页（班级/消息/个人/分析）在设备端没有对应页 →
  // 回教师设备端首页，避免把电脑版界面塞进手机/平板
  if (clean === '/teacher' || clean.startsWith('/teacher/')) {
    return `/${prefix}/teacher/home`
  }
  return null
}

/**
 * 设备无关页：两种设备形态下都可以停（登录页已在各自端实现，这里只列跨端通用页，
 * 避免把「未授权页 / 帮助页 / 资料预览页」也跳走）。
 */
export const DEVICE_AGNOSTIC_PATHS: readonly string[] = [
  '/unauthorized',
  '/login',
  '/help',
  '/materials-preview',
  '/about',
]

export function isDeviceAgnosticPath(path: string): boolean {
  return DEVICE_AGNOSTIC_PATHS.includes(normalizePath(path))
}

