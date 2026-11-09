/**
 * 考试开关与定时的纯函数（P2，2026-11-09）。
 *
 * 为什么抽出来：管理端列表的「考试」列、定时弹层、学生端提示都要用同一套文案与判定。
 * 之前 `materialShelf.ts` 就是这么做的（L2/L3 复制粘贴过一次文案，两端口径差点漂移）。
 *
 * **铁律**：能不能考由后端 `reason` 决定，前端只负责翻译 —— 不自己拿浏览器时间推算。
 * 原因：判定用的是**服务器本地时间**（用户决策 S1），运维机与学生机时区可能不同。
 */
import type { LibraryExamState, LibraryMaterial } from '@/modules/library/api';

/** 原因码 → 列表上的短标签（学生/管理员看到的都是这个词） */
const STATUS_LABEL: Record<string, string> = {
  ready: '可进入',
  closed: '已关闭',
  draft: '未发布',
  no_questions: '无题',
  not_started: '未开始',
  expired: '已结束',
  no_paper: '未建卷'
};

/** 原因码 → 色调（AdminTag 的 tone；类型必须与 TagTone 一致，否则 vue-tsc 会拦） */
const STATUS_TONE: Record<string, 'ok' | 'warn' | 'danger' | 'muted'> = {
  ready: 'ok',
  closed: 'danger',
  draft: 'muted',
  no_questions: 'warn',
  not_started: 'warn',
  expired: 'muted',
  no_paper: 'muted'
};

export function examStatusLabel(exam: LibraryExamState | null | undefined): string {
  if (!exam || !exam.known) return STATUS_LABEL.no_paper;
  return STATUS_LABEL[exam.reason] || '不可进入';
}

export function examStatusTone(
  exam: LibraryExamState | null | undefined
): 'ok' | 'warn' | 'danger' | 'muted' {
  if (!exam || !exam.known) return STATUS_TONE.no_paper;
  return STATUS_TONE[exam.reason] || 'muted';
}

/** `2026-11-09 20:00:00` → `20:00`（列表摘要只要时分） */
function hhmm(value: string | null | undefined): string {
  const text = String(value || '').trim();
  if (text.length < 16) return text;
  return text.slice(11, 16);
}

/**
 * 定时摘要（mockup 第二行）：
 * `20:00-22:00 定时` / `从 20:00 起` / `22:00 前可考` / `手动开启` / `无题（0 题）不可开`。
 */
export function examTimingText(exam: LibraryExamState | null | undefined): string {
  if (!exam || !exam.known) return '未建可作答卷';
  // 0 题优先说"无题"：草稿卷 + 0 题（#128）时，"去导题"才是下一步该做的事；
  // 只说"资料未发布"会让人以为上架就能考。
  if (!exam.question_count) return '无题（0 题）不可开';
  if (!exam.published) return '资料未发布';
  const openAt = hhmm(exam.open_at);
  const closeAt = hhmm(exam.close_at);
  if (openAt && closeAt) return `${openAt}-${closeAt} 定时`;
  if (openAt) return `${openAt} 起可考`;
  if (closeAt) return `${closeAt} 前可考`;
  return exam.manual_open === 0 ? '已手动关闭' : '手动开启';
}

/**
 * 这一行要不要显示考试开关。
 * 只有「试卷 + 投放位含考试页」才有这回事：仅资料页的卷学生只能下载原卷。
 */
export function examSwitchVisible(
  row: Pick<LibraryMaterial, 'type' | 'placement'>
): boolean {
  if (row.type !== 'paper') return false;
  return (row.placement || 'both') !== 'library';
}

/**
 * 开关能不能动。
 * 0 题时**强制灰掉**（方案 §4.3）：打开也进不去，给学生一个"看起来能用"的开关更糟。
 */
export function examSwitchEnabled(exam: LibraryExamState | null | undefined): boolean {
  return Boolean(exam?.known && exam.question_count > 0);
}

/** 开关为什么点不动（按钮 title，别让管理员以为是 bug） */
export function examSwitchHint(exam: LibraryExamState | null | undefined): string {
  if (!exam || !exam.known) return '还没有可作答卷：先点「建卷」或直接用「上传试卷」自动建卷';
  if (!exam.question_count) return '这张卷还没有题目（0 题），打开后学生也进不去';
  return exam.ready ? '当前学生可以进入考试；关闭后不能再新开（进行中的仍可交卷）'
    : '打开后学生即可进入考试（资料还需已上架）';
}

/** `datetime-local` 输入框的值格式：`YYYY-MM-DDTHH:mm` */
export function toDatetimeLocal(value: string | null | undefined): string {
  const text = String(value || '').trim();
  if (!text) return '';
  return text.replace(' ', 'T').slice(0, 16);
}

/**
 * `datetime-local` 的值 → 后端要的 `YYYY-MM-DD HH:MM`。
 * 空串照实返回 null（= 该侧不限），后端 `parse_dt` 认这个格式。
 */
export function fromDatetimeLocal(value: string | null | undefined): string | null {
  const text = String(value || '').trim();
  if (!text) return null;
  return text.replace('T', ' ').slice(0, 16);
}

/** 「快速填：今晚」—— 以服务器时间为基准的今天 20:00 / 22:00（决策：服务器本地时间） */
export function tonightWindow(serverNow?: string | null): { open: string; close: string } {
  const now = String(serverNow || '').trim();
  const day = now.length >= 10 ? now.slice(0, 10) : new Date().toISOString().slice(0, 10);
  return { open: `${day}T20:00`, close: `${day}T22:00` };
}

/**
 * 弹层里的「当前状态」一句话：
 * `当前：可进入（服务器时间 20:41）` / `当前：已关闭（服务器时间 20:41）`。
 */
export function examNowLine(exam: LibraryExamState | null | undefined): string {
  if (!exam || !exam.known) return '当前：还没有可作答卷';
  const when = hhmm(exam.server_now);
  const suffix = when ? `（服务器时间 ${when}）` : '';
  return `当前：${examStatusLabel(exam)}${suffix}`;
}
