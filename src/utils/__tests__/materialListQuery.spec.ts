import { describe, expect, it } from 'vitest';
import { hasListQuery, parseListQuery } from '../materialListQuery';

describe('parseListQuery（A4 补充：地址栏筛选）', () => {
  it('空 query → 全部不筛（默认视图）', () => {
    const empty = { subject: '', type: '', status: '', createdWithin: '',
                    paperYear: '', region: '', bookKind: '' };
    expect(parseListQuery({})).toEqual(empty);
    expect(parseListQuery(undefined)).toEqual(empty);
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
    expect(q).toEqual({ subject: '', type: '', status: '', createdWithin: '',
                        paperYear: '', region: '', bookKind: '' });
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

describe('C3 试卷筛选（year/region/book_kind）', () => {
  it('年份接受 4 位数字，越界/非数字忽略', () => {
    expect(parseListQuery({ year: '2019' }).paperYear).toBe('2019');
    expect(parseListQuery({ year: '1800' }).paperYear).toBe('');
    expect(parseListQuery({ year: '20x9' }).paperYear).toBe('');
    expect(parseListQuery({ year: '' }).paperYear).toBe('');
  });

  it('地区接受代码与中文名，其它忽略', () => {
    expect(parseListQuery({ region: 'BJ' }).region).toBe('BJ');
    expect(parseListQuery({ region: '北京' }).region).toBe('北京');
    expect(parseListQuery({ region: '火星' }).region).toBe('');
    // 代码按白名单精确匹配（后端会大写归一，前端不做隐式转换）
    expect(parseListQuery({ region: 'bj' }).region).toBe('');
  });

  it('卷别只接受 T/A/J', () => {
    expect(parseListQuery({ book_kind: 'T' }).bookKind).toBe('T');
    expect(parseListQuery({ book_kind: 'Z' }).bookKind).toBe('');
  });

  it('hasListQuery 把试卷筛选也算"有筛选"', () => {
    expect(hasListQuery(parseListQuery({ year: '2019' }))).toBe(true);
    expect(hasListQuery(parseListQuery({ region: '北京' }))).toBe(true);
  });

  it('试卷筛选可与 type=paper 组合（深链）', () => {
    const q = parseListQuery({ type: 'paper', year: '2019', region: 'BJ', book_kind: 'T' });
    expect(q).toMatchObject({ type: 'paper', paperYear: '2019', region: 'BJ', bookKind: 'T' });
  });

  it('空 query 时三个新字段都是空串', () => {
    expect(parseListQuery({})).toMatchObject({ paperYear: '', region: '', bookKind: '' });
  });
});
