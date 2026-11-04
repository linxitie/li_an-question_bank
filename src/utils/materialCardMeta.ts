/**
 * 资料卡片详情页的「信息栏」取值逻辑（PC 详情页外观 v2）
 *
 * 抽成纯函数是为了可单测：这些规则一旦写错，界面会显示
 * 「题型：无」「难度：undefined」「建议用时：0 分钟」这类假信息。
 *
 * 规则（方案见 docs/plans/PC详情页外观v2_方案与效果图_v1.md）：
 * - 题型：category 优先（用户确认），缺失回退 badge，再回退「资料卡」
 * - 难度：1→入门 / 2→中等 / 3→进阶，缺省按 2 中等
 * - 建议用时：read_time > 0 用真值；否则按正面字数 ÷ 300 向上取整，并标注「估」
 */

/** 卡片信息栏需要的最小字段集合（列表接口 _item_brief 提供） */
export interface CardMetaInput {
  title?: string | null;
  category?: string | null;
  badge?: string | null;
  difficulty?: number | null;
  read_time?: number | null;
  card_front?: string | null;
}

/** 估算基准：每分钟阅读字数（保守值） */
export const CHARS_PER_MINUTE = 300;

const DIFFICULTY_LABELS: Record<number, string> = {
  1: '入门',
  2: '中等',
  3: '进阶'
};

/** 题型：category 优先 → badge → 「资料卡」 */
export function typeLabel(card: CardMetaInput | null | undefined): string {
  const c = card || {};
  const cat = (c.category || '').trim();
  if (cat) return cat;
  const badge = (c.badge || '').trim();
  if (badge) return badge;
  return '资料卡';
}

/** 难度文案：1 入门 / 2 中等 / 3 进阶；非法或缺失按 2（中等） */
export function difficultyLabel(level: number | null | undefined): string {
  // 注意：Number(null) === 0、Number('') === 0，若先转数字会把缺失误判成 1（入门）。
  // 因此必须先判空，再转数字。
  if (level === null || level === undefined || (level as unknown) === '') {
    return DIFFICULTY_LABELS[2];
  }
  const n = Number(level);
  if (!Number.isFinite(n)) return DIFFICULTY_LABELS[2];
  const key = Math.min(3, Math.max(1, Math.round(n)));
  return DIFFICULTY_LABELS[key];
}

/** 建议用时（分钟）。read_time 有真值用真值，否则按正面字数估算（至少 1 分钟） */
export function estimateMinutes(card: CardMetaInput | null | undefined): number {
  const c = card || {};
  const real = Number(c.read_time || 0);
  if (Number.isFinite(real) && real > 0) return Math.round(real);
  const text = `${c.card_front || ''}${c.title || ''}`.replace(/\s+/g, '');
  if (!text) return 1;
  return Math.max(1, Math.ceil(text.length / CHARS_PER_MINUTE));
}

/** 建议用时展示文案：真值不带「估」，估算值带「· 估」 */
export function timeLabel(card: CardMetaInput | null | undefined): string {
  const c = card || {};
  const real = Number(c.read_time || 0);
  if (Number.isFinite(real) && real > 0) {
    return `约 ${Math.round(real)} 分钟`;
  }
  return `约 ${estimateMinutes(c)} 分钟 · 估`;
}
