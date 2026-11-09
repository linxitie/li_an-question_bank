/**
 * 学生端「备考资料」页的纯函数（L2，2026-11-08）。
 *
 * 为什么抽出来：这些文案/判定要能被单测覆盖，且以后手机端（L3）复用同一套口径，
 * 避免"PC 说可考、手机说不可考"的双份实现（项目里已有 materialBatch.ts 的先例）。
 */
import type { LibraryMaterial, MaterialPaperMeta } from '@/modules/library/api';

/** 讲义那行「3 章 · 0.9 万字」；没有大纲返回空串（调用方据此不渲染该行） */
export function lectureMetaLine(it: Pick<LibraryMaterial, 'chapter_count' | 'word_count'>): string {
  const parts: string[] = [];
  const chapters = Number(it.chapter_count || 0);
  const words = Number(it.word_count || 0);
  if (chapters) parts.push(`${chapters} 章`);
  if (words) parts.push(`${words} 字`);
  return parts.join(' · ');
}

/** 试卷那行「2024 · 国考 · 题本 ｜ 100 题 · 100 分 · 120 分钟 ｜ GZ-2024-GK-T」 */
export function paperMetaLine(it: Pick<LibraryMaterial, 'paper'>): string {
  const p: MaterialPaperMeta | null | undefined = it.paper;
  if (!p) return '元数据待补';
  const head = [p.year ?? '—', p.region_name ?? '—', p.book_kind_label ?? '—'].join(' · ');
  const mid = [
    p.question_count != null ? `${p.question_count} 题` : '—',
    p.total_score != null ? `${p.total_score} 分` : '—',
    p.duration != null ? `${p.duration} 分钟` : '—'
  ].join(' · ');
  return `${head} ｜ ${mid} ｜ ${p.paper_code ?? '无编号'}`;
}

/** 能不能"去考试"：只有卷已发布（PUBLISHED）且投放位含考试页时才算 */
export function canExam(it: Pick<LibraryMaterial, 'paper' | 'placement'>): boolean {
  if (it.placement === 'library') return false;
  return Boolean(it.paper?.answerable);
}

/** 不可考的原因（按钮 title 与卡片说明共用一句，别让用户猜） */
export function examHint(it: Pick<LibraryMaterial, 'paper' | 'placement'>): string {
  if (it.placement === 'library') return '投放位=仅资料页：只给原卷，不开放作答。';
  if (!it.paper) return '这套卷还没建可作答卷，暂时不能在线作答。';
  if (!it.paper.exam_paper_id) return '这套卷还没建可作答卷，暂时不能在线作答。';
  if (!it.paper.question_count) return '可作答卷里还没有题目，导题后才能考。';
  return '试卷未发布（资料下架或投放位未含考试页）。';
}

/** 视频时长：90 → 1 分钟；3900 → 1 小时 5 分；0 → 时长未知 */
export function fmtDuration(sec: number | null | undefined): string {
  const s = Number(sec || 0);
  if (!s) return '时长未知';
  const m = Math.floor(s / 60);
  return m >= 60 ? `${Math.floor(m / 60)} 小时 ${m % 60} 分` : `${m} 分钟`;
}

/** 分区默认只露 4 条，其余折叠（页面与单测共用同一常量） */
export const COLLAPSED = 4;

/** 取某分区要渲染的条目 */
export function visibleItems<T>(arr: T[], folded: boolean): T[] {
  return folded ? arr.slice(0, COLLAPSED) : arr;
}

/**
 * 把一屏资料分成「讲义 / 试卷资料 / 其余」（L3 手机端用）。
 *
 * 为什么单独抽：手机页原来把 6 类资料混在一个纵向列表里，讲义与试卷点开只有空白
 * （详情只渲染 content/card_back）。L3 要给这两类单独做横滑区与专属按钮，
 * 就需要一个**可测**的分组口径，且 PC 与手机对"哪些进讲义区"的判断必须一致。
 */
export interface ShelfGroups<T> {
  lectures: T[];
  papers: T[];
  rest: T[];
}

export function groupShelfItems<
  T extends { type: string; paper?: MaterialPaperMeta | null; placement?: string }
>(items: T[]): ShelfGroups<T> {
  const lectures: T[] = [];
  const papers: T[] = [];
  const rest: T[] = [];
  for (const it of items || []) {
    if (it.type === 'lecture') lectures.push(it);
    else if (it.type === 'paper') papers.push(it);
    else rest.push(it);
  }
  return { lectures, papers, rest };
}
