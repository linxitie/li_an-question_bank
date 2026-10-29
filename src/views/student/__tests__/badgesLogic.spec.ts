import { describe, expect, it } from 'vitest';
import {
  DEFAULT_FILTERS,
  clampPage,
  filterBadges,
  filterByTier,
  maxPageOf,
  paginate,
  rarityText,
  dateOnly,
  sortByRecent,
  tierPercent,
  wallItems,
  type BadgeItem
} from '../badgesLogic';

const mk = (over: Partial<BadgeItem>): BadgeItem => ({
  kind: 'achievement',
  id: 1,
  name: '初来乍到',
  category: '坚持',
  shape: 'shield',
  owned: false,
  ...over
});

const ITEMS: BadgeItem[] = [
  mk({ id: 1, name: '初来乍到', category: '成长', owned: true }),
  mk({ id: 2, name: '连续学习7天', category: '坚持', owned: true }),
  mk({ id: 3, name: '百题斩', category: '数量', owned: false }),
  mk({ id: 4, name: '见习', category: '称号', kind: 'title', shape: 'ribbon', owned: false }),
  mk({ id: 5, name: '讲师之友', category: '社交', shape: 'ribbon', owned: false })
];

describe('filterBadges', () => {
  it('默认不过滤', () => {
    expect(filterBadges(ITEMS, DEFAULT_FILTERS)).toHaveLength(5);
  });

  it('按类型过滤', () => {
    expect(filterBadges(ITEMS, { kind: 'title' }).map((i) => i.id)).toEqual([4]);
    expect(filterBadges(ITEMS, { kind: 'achievement' })).toHaveLength(4);
  });

  it('按状态过滤', () => {
    expect(filterBadges(ITEMS, { state: 'owned' }).map((i) => i.id)).toEqual([1, 2]);
    expect(filterBadges(ITEMS, { state: 'unowned' }).map((i) => i.id)).toEqual([3, 4, 5]);
  });

  it('按类别过滤', () => {
    expect(filterBadges(ITEMS, { category: '坚持' }).map((i) => i.id)).toEqual([2]);
  });

  it('关键词匹配名称与类别（含描述）', () => {
    expect(filterBadges(ITEMS, { keyword: '百题' }).map((i) => i.id)).toEqual([3]);
    expect(filterBadges(ITEMS, { keyword: '社交' }).map((i) => i.id)).toEqual([5]);
    expect(filterBadges(ITEMS, { keyword: '  百题  ' }).map((i) => i.id)).toEqual([3]);
  });

  it('条件叠加后可能为空', () => {
    expect(filterBadges(ITEMS, { kind: 'title', state: 'owned' })).toEqual([]);
  });
});

describe('filterByTier', () => {
  it('all 不过滤', () => {
    expect(filterByTier(ITEMS, 'all', () => '黄金')).toHaveLength(5);
  });

  it('按中文档位过滤', () => {
    const labelOf = (i: BadgeItem) => (i.id === 2 ? '黄金' : '黑铁');
    expect(filterByTier(ITEMS, 'gold', labelOf).map((i) => i.id)).toEqual([2]);
    expect(filterByTier(ITEMS, 'diamond', labelOf)).toEqual([]);
  });
});

describe('分页', () => {
  it('总页数', () => {
    expect(maxPageOf(0, 15)).toBe(1);
    expect(maxPageOf(15, 15)).toBe(1);
    expect(maxPageOf(16, 15)).toBe(2);
    expect(maxPageOf(57, 15)).toBe(4);
  });

  it('clampPage 收敛越界', () => {
    expect(clampPage(0, 57, 15)).toBe(1);
    expect(clampPage(99, 57, 15)).toBe(4);
    expect(clampPage(-5, 57, 15)).toBe(1);
  });

  it('切片正确', () => {
    const arr = Array.from({ length: 20 }, (_, i) => i + 1);
    expect(paginate(arr, 1, 15)).toHaveLength(15);
    expect(paginate(arr, 2, 15)).toEqual([16, 17, 18, 19, 20]);
    expect(paginate(arr, 3, 15)).toEqual([16, 17, 18, 19, 20]); // 越界收敛到最后一页
  });

  it('空列表也能安全分页', () => {
    expect(paginate([], 1, 15)).toEqual([]);
    expect(paginate([], 5, 15)).toEqual([]);
  });
});

describe('tierPercent', () => {
  it('黑铁 100 分 → 50%', () => {
    expect(tierPercent(100, 0, 200)).toBe(50);
  });

  it('刚进档 → 0%', () => {
    expect(tierPercent(400, 400, 600)).toBe(0);
  });

  it('钻石档（无下一档）→ 100%', () => {
    expect(tierPercent(1200, 800, null)).toBe(100);
  });

  it('超出下一档也封顶 100%', () => {
    expect(tierPercent(900, 600, 800)).toBe(100);
  });
});

describe('sortByRecent / wallItems', () => {
  const data: BadgeItem[] = [
    mk({ id: 1, name: 'A', owned: true, obtained_at: '2026-10-01' }),
    mk({ id: 2, name: 'B', owned: false }),
    mk({ id: 3, name: 'C', owned: true, obtained_at: '2026-10-20' }),
    mk({ id: 4, name: 'D', owned: true, obtained_at: null })
  ];

  it('已获得按时间倒序在前，未获得在后', () => {
    expect(sortByRecent(data).map((i) => i.id)).toEqual([3, 1, 4, 2]);
  });

  it('徽章墙只取已获得且不超过 limit', () => {
    expect(wallItems(data, 2).map((i) => i.id)).toEqual([3, 1]);
    expect(wallItems(data, 6)).toHaveLength(3);
  });

  it('全部未获得时徽章墙为空', () => {
    expect(wallItems([mk({ id: 9, owned: false })])).toEqual([]);
  });
});

describe('rarityText / dateOnly', () => {
  it('正常稀有度', () => {
    expect(rarityText(1204, 37.5)).toBe('1204 人已获得（37.5%）');
    expect(rarityText(10, 0)).toBe('10 人已获得');
  });

  it('无统计数据返回空串（不编造）', () => {
    expect(rarityText(0, 0)).toBe('');
    expect(rarityText(null, null)).toBe('');
    expect(rarityText(undefined, undefined)).toBe('');
  });

  it('日期只显示前 10 位', () => {
    expect(dateOnly('2026-10-20T21:36:00')).toBe('2026-10-20');
    expect(dateOnly(null)).toBe('');
    expect(dateOnly(undefined)).toBe('');
  });
});
