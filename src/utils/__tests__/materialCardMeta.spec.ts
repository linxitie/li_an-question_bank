import { describe, expect, it } from 'vitest';
import {
  CHARS_PER_MINUTE,
  difficultyLabel,
  estimateMinutes,
  timeLabel,
  typeLabel
} from '../materialCardMeta';

/**
 * PC 详情页信息栏取值（对应 docs/plans/PC详情页外观v2_方案与效果图_v1.md 的 V3–V5）
 */
describe('typeLabel（题型）', () => {
  it('category 优先（用户确认的口径）', () => {
    expect(typeLabel({ category: '言语理解与表达', badge: '要点' })).toBe('言语理解与表达');
  });

  it('category 为空 → 回退 badge', () => {
    expect(typeLabel({ category: '', badge: '要点' })).toBe('要点');
    expect(typeLabel({ category: null, badge: '技巧' })).toBe('技巧');
  });

  it('都缺失 → 资料卡', () => {
    expect(typeLabel({})).toBe('资料卡');
    expect(typeLabel(null)).toBe('资料卡');
  });

  it('空白字符串视为缺失', () => {
    expect(typeLabel({ category: '   ', badge: '  ' })).toBe('资料卡');
  });
});

describe('difficultyLabel（难度）', () => {
  it.each([
    [1, '入门'],
    [2, '中等'],
    [3, '进阶']
  ])('level=%s → %s', (level, label) => {
    expect(difficultyLabel(level as number)).toBe(label);
  });

  it('缺失/非法按中等', () => {
    expect(difficultyLabel(null)).toBe('中等');
    expect(difficultyLabel(undefined)).toBe('中等');
    expect(difficultyLabel(NaN)).toBe('中等');
  });

  it('超界值收敛到 1–3', () => {
    expect(difficultyLabel(0)).toBe('入门');
    expect(difficultyLabel(9)).toBe('进阶');
  });
});

describe('estimateMinutes / timeLabel（建议用时）', () => {
  it('read_time 有真值 → 用真值且不带「估」', () => {
    expect(estimateMinutes({ read_time: 4 })).toBe(4);
    expect(timeLabel({ read_time: 4 })).toBe('约 4 分钟');
  });

  it('read_time = 0（当前库内全部如此）→ 估算并标注「估」', () => {
    const text = '字'.repeat(CHARS_PER_MINUTE * 2);
    expect(estimateMinutes({ card_front: text })).toBe(2);
    expect(timeLabel({ card_front: text })).toBe('约 2 分钟 · 估');
  });

  it('极短文本至少 1 分钟', () => {
    expect(estimateMinutes({ card_front: '短' })).toBe(1);
    expect(timeLabel({ card_front: '短' })).toBe('约 1 分钟 · 估');
  });

  it('空内容也给 1 分钟，不出现 0', () => {
    expect(estimateMinutes({})).toBe(1);
    expect(estimateMinutes(null)).toBe(1);
    expect(timeLabel({})).not.toContain('0 分钟');
  });

  it('估算忽略空白字符', () => {
    const spaced = '字 '.repeat(CHARS_PER_MINUTE);
    expect(estimateMinutes({ card_front: spaced })).toBe(1);
  });
});
