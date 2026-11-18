/**
 * 教师设备端导航/功能卡配置（P3，2026-11-16）
 *
 * 为什么要单独抽配置文件：
 *   1) 平板/手机共用同一套功能卡（守 R12），配置集中一处避免两套文案；
 *   2) 设备端「写操作」按 D-19 统一显示「功能待开发」——文案只在这里定义一次，
 *      P4 再加页面时不会出现"一处写请去电脑端、另一处写待开发"的口径漂移；
 *   3) 预留「上传」位置：后续加文件上传/题目导入时只改这里 + 加一条路由，不动页面布局。
 *
 * 说明：`status='todo'` 的卡片**不提供任何写控件**，点击只弹说明；
 *       真正的写操作仍在电脑端（/teacher/*），后端权限未放宽（见方案 §13）。
 */

export type TeacherNavStatus = 'ready' | 'todo' | 'reserved'

export interface TeacherNavItem {
  key: string
  title: string
  desc: string
  status: TeacherNavStatus
  /** status=ready 时的设备端路径 */
  path?: string
  /** status=todo/reserved 时弹窗里的原因说明 */
  reason?: string
}

export const TEACHER_NAV_ITEMS: TeacherNavItem[] = [
  {
    key: 'questions',
    title: '📚 题目管理',
    desc: '浏览 / 搜索 / 预览',
    status: 'ready',
    path: '/teacher/questions',
  },
  {
    key: 'papers',
    title: '📝 试卷',
    desc: '查看列表与状态',
    // P4 起设备端有只读列表页（/tablet|/mobile/teacher/papers）
    status: 'ready',
    path: '/teacher/papers',
  },
  {
    key: 'scores',
    title: '📊 成绩分析',
    desc: '班级均分 / 分布 / 名单',
    // P4 起设备端有只读概览页（/tablet|/mobile/teacher/scores，D-21 选①）
    status: 'ready',
    path: '/teacher/scores',
  },
  {
    key: 'paper-edit',
    title: '✏️ 组卷 / 编辑试卷',
    desc: '需要键盘与双栏工作台',
    status: 'todo',
    reason: '设备端尚未开发：组卷/编辑需要在双栏工作台里拖拽与预览，电脑端已可用（/teacher/papers）。',
  },
  {
    key: 'grading',
    title: '✅ 批改作业 / 判分',
    desc: '需逐题打分',
    status: 'todo',
    reason: '设备端尚未开发：逐题判分需要批量键盘操作，电脑端已可用（/teacher/scores）。',
  },
  {
    key: 'import',
    title: '📤 批量导入题目',
    desc: '需上传文件与校验',
    status: 'todo',
    reason: '设备端尚未开发：导入需要文件上传 + 校验预览，电脑端已可用（/teacher/questions）。',
  },
  {
    key: 'upload',
    title: '⬆️ 上传资料 / 课件',
    desc: '文件上传（位置已预留）',
    status: 'reserved',
    reason: '该入口位置已预留，等上传功能在设备端落地后启用。',
  },
]

/** 卡片右上角标签文案（D-19：写操作统一显示「功能待开发」） */
export const TEACHER_NAV_STATUS_LABEL: Record<TeacherNavStatus, string> = {
  ready: '设备端可用',
  todo: '功能待开发',
  reserved: '位置预留',
}

export const TEACHER_NAV_STATUS_TONE: Record<TeacherNavStatus, 'ok' | 'warn' | 'gray'> = {
  ready: 'ok',
  todo: 'warn',
  reserved: 'gray',
}

/** 把配置里的电脑端路径换成设备端实际路由 */
export function deviceNavPath(prefix: 'tablet' | 'mobile', item: TeacherNavItem): string | null {
  if (item.status !== 'ready' || !item.path) return null
  // /teacher/questions → /tablet/teacher/questions
  const tail = item.path.replace(/^\/teacher/, '')
  return `/${prefix}/teacher${tail}`
}
