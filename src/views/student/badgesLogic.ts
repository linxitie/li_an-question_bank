/**
 * 「我的徽章」页的纯逻辑（S3-b）：筛选、分页、档位刻度。
 *
 * 抽出来的原因：筛选与分页是最容易写错的交互（空结果、页码越界、
 * 多条件叠加），用单测锁死比在页面上手点更可靠。
 */

export interface BadgeItem {
  badge_tier?: string;
  rarity_text?: string;
  is_first_owner?: boolean;

  kind: 'achievement' | 'title' | string;
  id: number;
  name: string;
  category: string;
  shape: string;
  icon?: string | null;
  condition_desc?: string;
  reward_coins?: number;
  threshold?: number;
  owned: boolean;
  obtained_at?: string | null;
  snapshot_tier?: string | null;
  snapshot_estimated?: boolean;
  pinned?: boolean;
  owned_count?: number;
  owned_percent?: number;
  current_tier?: string;
}

export type KindFilter = 'all' | 'achievement' | 'title';
export type StateFilter = 'all' | 'owned' | 'unowned';
export type TierFilter = 'all' | 'iron' | 'bronze' | 'silver' | 'gold' | 'diamond';

export interface BadgeFilters {
  kind: KindFilter;
  state: StateFilter;
  tier: TierFilter;
  category: string;
  keyword: string;
}

export const DEFAULT_FILTERS: BadgeFilters = {
  kind: 'all',
  state: 'all',
  tier: 'all',
  category: '',
  keyword: ''
};

/** 按 kind / state / category / keyword 过滤（tier 过滤依赖用户当前档位，见 filterByTier） */
export function filterBadges(items: BadgeItem[], f: Partial<BadgeFilters>): BadgeItem[] {
  const filters = { ...DEFAULT_FILTERS, ...f };
  const kw = filters.keyword.trim();
  return items.filter((it) => {
    if (filters.kind !== 'all' && it.kind !== filters.kind) return false;
    if (filters.state === 'owned' && !it.owned) return false;
    if (filters.state === 'unowned' && it.owned) return false;
    if (filters.category && it.category !== filters.category) return false;
    if (kw) {
      const hay = `${it.name}${it.category}${it.condition_desc || ''}`;
      if (!hay.includes(kw)) return false;
    }
    return true;
  });
}

/**
 * 品质筛选：徽章本身的档位来自「获得时快照」，未获得/无快照时用用户当前档位。
 * 因此这里需要调用方把"每项的档位中文"算好传进来。
 */
export function filterByTier(
  items: BadgeItem[],
  tierLabel: TierFilter,
  tierLabelOf: (it: BadgeItem) => string
): BadgeItem[] {
  if (tierLabel === 'all') return items;
  const map: Record<string, string> = {
    iron: '黑铁', bronze: '青铜', silver: '白银', gold: '黄金', diamond: '钻石'
  };
  const want = map[tierLabel];
  return items.filter((it) => tierLabelOf(it) === want);
}

/** 页码收敛到 [1, maxPage] */
export function clampPage(page: number, total: number, pageSize: number): number {
  const maxPage = Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  const p = Math.round(Number(page) || 1);
  return Math.min(Math.max(1, p), maxPage);
}

/** 分页切片 */
export function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const size = Math.max(1, pageSize);
  const p = clampPage(page, items.length, size);
  const start = (p - 1) * size;
  return items.slice(start, start + size);
}

/** 总页数 */
export function maxPageOf(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
}

/** 档位卡进度：返回 0–100 的百分比（钻石档固定 100） */
export function tierPercent(score: number, threshold: number, nextThreshold: number | null): number {
  const s = Math.max(0, Number(score) || 0);
  if (nextThreshold === null || nextThreshold === undefined) return 100;
  const span = nextThreshold - threshold;
  if (span <= 0) return 100;
  return Math.round(Math.min(100, Math.max(0, ((s - threshold) / span) * 100)) * 10) / 10;
}

/**
 * 最近获得排序：已获得按获得时间倒序在前，未获得保持原顺序在后。
 * 用于「我的徽章」按最近获得浏览，以及主页徽章墙取数。
 */
export function sortByRecent(items: BadgeItem[]): BadgeItem[] {
  const owned = items.filter((i) => i.owned);
  const rest = items.filter((i) => !i.owned);
  owned.sort((a, b) => String(b.obtained_at || "").localeCompare(String(a.obtained_at || "")));
  return [...owned, ...rest];
}

/** 主页徽章墙：只取已获得，最多 limit 枚（默认 6） */
export function wallItems(items: BadgeItem[], limit = 6): BadgeItem[] {
  return sortByRecent(items).filter((i) => i.owned).slice(0, Math.max(1, limit));
}

/** 稀有度文案：有统计才显示；0 人或无统计返回空串（不编造数字） */
export function rarityText(ownedCount?: number | null, ownedPercent?: number | null): string {
  const n = Number(ownedCount ?? 0);
  if (!Number.isFinite(n) || n <= 0) return "";
  const p = Number(ownedPercent ?? 0);
  const pct = Number.isFinite(p) && p > 0 ? `（${p.toFixed(1)}%）` : "";
  return `${n} 人已获得${pct}`;
}

/** 获得时间只显示日期部分 */
export function dateOnly(iso?: string | null): string {
  if (!iso) return "";
  return String(iso).slice(0, 10);
}
