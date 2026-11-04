import { describe, expect, it } from 'vitest';

import { FORUM_CATEGORY_TABS, toShareTypeParam } from '../categories';

describe('forum categories', () => {
  it('按用户要求的顺序提供四个业务分类，并保留心情打卡', () => {
    expect(FORUM_CATEGORY_TABS.map((tab) => tab.name)).toEqual([
      '全部',
      '学习讨论',
      '经验分享',
      '答疑解惑',
      '资料分享',
      '心情打卡'
    ]);
  });

  it('全部与非法值不产生筛选参数', () => {
    expect(toShareTypeParam('all')).toBe('');
    expect(toShareTypeParam('')).toBe('');
    expect(toShareTypeParam(null)).toBe('');
    expect(toShareTypeParam('question')).toBe('');
    expect(toShareTypeParam('NOT_A_CATEGORY')).toBe('');
  });

  it('合法分类原样传给后端 share_type', () => {
    expect(toShareTypeParam('QUESTION')).toBe('QUESTION');
    expect(toShareTypeParam('DISCUSSION')).toBe('DISCUSSION');
    expect(toShareTypeParam('FEELING')).toBe('FEELING');
  });
});
