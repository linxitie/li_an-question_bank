import { describe, expect, it } from 'vitest';
import {
  BADGE_TIERS,
  SHAPE_LABELS,
  TIER_THRESHOLDS,
  needToNext,
  nextBadgeUid,
  tierByIndex,
  tierByScore
} from '../badgePalette';

/**
 * S3-a 徽章调色板 / 档位换算
 * 阈值必须与后端 badge_service.TIERS 完全一致，否则前端徽章与积分进度会错位。
 */
describe('BADGE_TIERS 常量', () => {
  it('五档且阈值与后端一致', () => {
    expect(BADGE_TIERS).toHaveLength(5);
    expect(TIER_THRESHOLDS).toEqual([0, 200, 400, 600, 800]);
    expect(BADGE_TIERS.map((t) => t.label)).toEqual(['黑铁', '青铜', '白银', '黄金', '钻石']);
  });

  it('每档都有两组渐变端点', () => {
    for (const t of BADGE_TIERS) {
      expect(t.outer).toHaveLength(2);
      expect(t.inner).toHaveLength(2);
      for (const c of [...t.outer, ...t.inner, t.text]) {
        expect(c).toMatch(/^#[0-9a-f]{6}$/i);
      }
    }
  });

  it('只有钻石档标记 special', () => {
    expect(BADGE_TIERS.filter((t) => t.special).map((t) => t.code)).toEqual(['diamond']);
  });
});

describe('tierByScore 边界', () => {
  it.each([
    [0, '黑铁'], [199, '黑铁'],
    [200, '青铜'], [399, '青铜'],
    [400, '白银'], [599, '白银'],
    [600, '黄金'], [799, '黄金'],
    [800, '钻石'], [99999, '钻石']
  ])('%s 分 → %s', (score, label) => {
    expect(tierByScore(score as number).label).toBe(label);
  });

  it('负数与非法值按 0 处理', () => {
    expect(tierByScore(-100).label).toBe('黑铁');
    expect(tierByScore(null).label).toBe('黑铁');
    expect(tierByScore(undefined).label).toBe('黑铁');
    expect(tierByScore(NaN).label).toBe('黑铁');
  });
});

describe('tierByIndex 收敛', () => {
  it('正常索引', () => {
    expect(tierByIndex(0).label).toBe('黑铁');
    expect(tierByIndex(4).label).toBe('钻石');
  });

  it('越界收敛到 0–4', () => {
    expect(tierByIndex(-3).label).toBe('黑铁');
    expect(tierByIndex(9).label).toBe('钻石');
    expect(tierByIndex(null).label).toBe('黑铁');
  });

  it('小数四舍五入', () => {
    expect(tierByIndex(2.4).label).toBe('白银');
    expect(tierByIndex(2.6).label).toBe('黄金');
  });
});

describe('needToNext 进度', () => {
  it('780 分：黄金档，还差 20 分，约 90%', () => {
    const r = needToNext(780);
    expect(r.maxed).toBe(false);
    expect(r.need).toBe(20);
    expect(r.percent).toBeCloseTo(90, 1);
  });

  it('刚进档：百分比 0', () => {
    const r = needToNext(400);
    expect(r.percent).toBe(0);
    expect(r.need).toBe(200);
  });

  it('钻石档：maxed 且 100%', () => {
    expect(needToNext(800)).toEqual({ need: 0, maxed: true, percent: 100 });
    expect(needToNext(5000).maxed).toBe(true);
  });

  it('0 分：黑铁档，还差 200 分', () => {
    const r = needToNext(0);
    expect(r.need).toBe(200);
    expect(r.percent).toBe(0);
  });
});

describe('辅助函数', () => {
  it('SHAPE_LABELS 覆盖五类形状（v3 新增 star=准确率）', () => {
    expect(Object.keys(SHAPE_LABELS)).toEqual(['shield', 'ribbon', 'rosette', 'gem', 'star']);
  });

  it('nextBadgeUid 每次唯一（避免同页渐变 id 冲突）', () => {
    const ids = new Set(Array.from({ length: 50 }, () => nextBadgeUid('t')));
    expect(ids.size).toBe(50);
  });
});
