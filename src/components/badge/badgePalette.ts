/**
 * 徽章调色板与档位换算（S3-a）
 *
 * 与后端 `backend/app/services/badge_service.py` 的五档阈值保持一致：
 * <200 黑铁 ｜ 200–399 青铜 ｜ 400–599 白银 ｜ 600–799 黄金 ｜ ≥800 钻石（不封顶）
 *
 * 抽成纯函数 + 常量，便于单测，也便于 SVG 组件与后续页面共用同一份色值。
 */

export type BadgeTierCode = 'iron' | 'bronze' | 'silver' | 'gold' | 'diamond';
export type BadgeShape = 'shield' | 'ribbon' | 'rosette' | 'gem';

export interface BadgeTier {
  /** 0–4，与后端 tier_snapshot 对齐 */
  index: number;
  code: BadgeTierCode;
  label: string;
  /** 该档下界（累计积分） */
  threshold: number;
  /** 外轮廓渐变 */
  outer: [string, string];
  /** 内芯渐变 */
  inner: [string, string];
  /** 文字/描边用色 */
  text: string;
  /** 钻石档才有光晕与星芒 */
  special?: boolean;
}

export const BADGE_TIERS: BadgeTier[] = [
  {
    index: 0, code: 'iron', label: '黑铁', threshold: 0,
    outer: ['#33383f', '#6b7380'], inner: ['#4a5059', '#949cab'], text: '#4a5260'
  },
  {
    index: 1, code: 'bronze', label: '青铜', threshold: 200,
    outer: ['#7d4a1f', '#d08b45'], inner: ['#a8652a', '#e9b57c'], text: '#8a5324'
  },
  {
    index: 2, code: 'silver', label: '白银', threshold: 400,
    outer: ['#6f7a8c', '#cdd6e3'], inner: ['#8c98ab', '#eef3fa'], text: '#6b7689'
  },
  {
    index: 3, code: 'gold', label: '黄金', threshold: 600,
    outer: ['#9a6f08', '#f3cf5a'], inner: ['#c79a1c', '#fbe9a8'], text: '#a87b0c'
  },
  {
    index: 4, code: 'diamond', label: '钻石', threshold: 800,
    outer: ['#2ea8ff', '#a855f7'], inner: ['#8be9ff', '#dff8ff'], text: '#2563eb',
    special: true
  }
];

/** 五档阈值（供进度条刻度使用） */
export const TIER_THRESHOLDS = BADGE_TIERS.map((t) => t.threshold);

/** 按索引取档位；越界收敛到 0–4 */
export function tierByIndex(index: number | null | undefined): BadgeTier {
  const n = Number(index);
  if (!Number.isFinite(n)) return BADGE_TIERS[0];
  const i = Math.min(BADGE_TIERS.length - 1, Math.max(0, Math.round(n)));
  return BADGE_TIERS[i];
}

/** 按累计积分取档位（与后端 tier_of 同口径） */
export function tierByScore(score: number | null | undefined): BadgeTier {
  const s = Math.max(0, Number(score) || 0);
  let hit = BADGE_TIERS[0];
  for (const t of BADGE_TIERS) {
    if (s >= t.threshold) hit = t;
  }
  return hit;
}

/** 到下一档还差多少分；钻石档返回 0 且 maxed=true */
export function needToNext(score: number | null | undefined): { need: number; maxed: boolean; percent: number } {
  const s = Math.max(0, Number(score) || 0);
  const cur = tierByScore(s);
  const next = BADGE_TIERS[cur.index + 1];
  if (!next) return { need: 0, maxed: true, percent: 100 };
  const span = next.threshold - cur.threshold;
  const done = s - cur.threshold;
  return {
    need: Math.max(0, next.threshold - s),
    maxed: false,
    percent: Math.round(Math.min(100, Math.max(0, (done / span) * 100)) * 10) / 10
  };
}

/** 形状中文名（用于 aria-label / 提示） */
export const SHAPE_LABELS: Record<BadgeShape | 'star', string> = {
  shield: '成就',
  ribbon: '称号',
  rosette: '科目',
  gem: '稀有',
  star: '准确率'
};

/** 生成唯一渐变 id（同一页面多个徽章不能共用 id，否则渐变会互相覆盖） */
let uidSeq = 0;
export function nextBadgeUid(prefix = 'bdg'): string {
  uidSeq += 1;
  return `${prefix}-${uidSeq}`;
}

/** 未获得态配色：通体灰阶（比旧版更深，轮廓清楚），仍保留形状与花纹 */
export const LOCKED_PAINT = {
  outer: ['#c3c8d2', '#d1d5db'] as [string, string],
  inner: ['#eef0f4', '#d1d5db'] as [string, string],
  text: '#6b7280'
};

/**
 * 形状族映射（v3 定稿）：盾=坚持/成长，圆章=做题量/斩题，星=准确率，菱形=社交/综合。
 * 称号（kind=title）继续用 ribbon。
 */
export function shapeOfCategory(category: string | null | undefined): BadgeShape | 'star' {
  const c = String(category || '');
  if (/(坚持|连续|成长|学习|早|夜)/.test(c)) return 'shield';
  if (/(做题|刷题|斩题|题目|题量|练习)/.test(c)) return 'rosette';
  if (/(准确|正确|命中|精度)/.test(c)) return 'star';
  return 'gem';
}
