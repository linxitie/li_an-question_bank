import { describe, expect, it } from 'vitest';
import { hasListQuery, parseListQuery } from '../materialListQuery';

describe('parseListQuery（A4 补充：地址栏筛选）', () => {
  it('空 query → 全部不筛（默认视图）', () => {
    expect(parseListQuery({})).toEqual({ subject: '', type: '', status: '', createdWithin: '' });
    expect(parseListQuery(undefined)).toEqual({ subject: '', type: '', status: '', createdWithin: '' });
  });

  it('?type=paper → 真的筛试卷（/admin/papers redirect 的落点）', () => {
    const q = parseListQuery({ type: 'paper' });
    expect(q.type).toBe('paper');
    expect(hasListQuery(q)).toBe(true);
  });

  it('?status=-1 → 直接进回收站', () => {
    expect(parseListQuery({ status: '-1' }).status).toBe('-1');
    expect(parseListQuery({ status: '-1' }).type).toBe('');
  });

  it('?subject + ?created_within 同时生效', () => {
    const q = parseListQuery({ subject: 'gongzhuan', created_within: '7d' });
    expect(q.subject).toBe('gongzhuan');
    expect(q.createdWithin).toBe('7d');
  });

  it('非法值一律忽略（不把列表刷空、不抛错）', () => {
    const q = parseListQuery({
      subject: 'yuwen',
      type: 'video_x',
      status: '9',
      created_within: '90d'
    });
    expect(q).toEqual({ subject: '', type: '', status: '', createdWithin: '' });
    expect(hasListQuery(q)).toBe(false);
  });

  it('数组值取第一个（vue-router 支持 ?type=paper&type=card）', () => {
    expect(parseListQuery({ type: ['paper', 'card'] }).type).toBe('paper');
  });

  it('空白与首尾空格容错', () => {
    expect(parseListQuery({ type: '  paper ' }).type).toBe('paper');
    expect(parseListQuery({ type: '   ' }).type).toBe('');
  });

  it('null 值不炸', () => {
    expect(parseListQuery({ type: null, status: undefined }).type).toBe('');
  });
});
