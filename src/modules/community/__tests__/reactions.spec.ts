import { describe, expect, it } from 'vitest';
import {
  REACTION_ORDER,
  formatReactionSummary,
  reactionTotal
} from '../reactions';

describe('community reactions', () => {
  it('formats reactions in the fixed display order', () => {
    expect(
      formatReactionSummary({ angry: 1, like: 2, wow: 3, love: 1 })
    ).toBe('👍2 ❤️1 😮3 😠1');
  });

  it('skips zero and missing reactions', () => {
    expect(formatReactionSummary({ like: 0, love: 2, sad: 0 })).toBe('❤️2');
    expect(formatReactionSummary({})).toBe('');
    expect(formatReactionSummary(null)).toBe('');
  });

  it('counts only known reaction codes', () => {
    expect(reactionTotal({ like: 2, love: 1 })).toBe(3);
    expect(reactionTotal({ like: 2, unknown: 99 })).toBe(2);
    expect(reactionTotal(undefined)).toBe(0);
  });

  it('keeps the agreed order', () => {
    expect(REACTION_ORDER).toEqual([
      'like',
      'love',
      'haha',
      'wow',
      'sad',
      'angry'
    ]);
  });
});
