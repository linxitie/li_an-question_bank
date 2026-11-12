/**
 * 补答案计数纯函数（2026-11-12 缺陷回归）。
 *
 * 事故：按钮「确认写入 N 题」用的是"有答案的题数"，不是"会写入的题数"；
 * 库里答案已一致时显示 97、实际写 0（保留 97），容易被当成"没写进去"。
 */
import { describe, expect, it } from 'vitest';
import { countAnswered, countDiffering, countIdentical, countWritable } from '@/utils/answerDraft';

const ITEMS = [
  { answer: 'A', current: '' },        // 空位 → 会写
  { answer: 'B', current: 'B' },       // 一致 → 不写
  { answer: 'C', current: 'A' },       // 不同 → 默认保留，勾覆盖才写
  { answer: '', current: 'D' },        // 没解析出答案 → 不写
  { answer: 'D', current: '' }
];

describe('countWritable', () => {
  it('只算"空位"（库里没答案）', () => {
    expect(countWritable(ITEMS)).toBe(2);           // A 与 D
  });
  it('勾「覆盖已有答案」后，把"不同"的也算进来', () => {
    expect(countWritable(ITEMS, true)).toBe(3);     // + C
  });
  it('答案为空的一律不算（没有答案可写）', () => {
    expect(countWritable([{ answer: '', current: '' }], true)).toBe(0);
  });
  it('大小写/空白不影响判定', () => {
    expect(countWritable([{ answer: ' a ', current: 'A' }])).toBe(0);
    expect(countWritable([{ answer: 'a', current: '' }])).toBe(1);
  });
  it('空列表返回 0', () => {
    expect(countWritable([])).toBe(0);
  });
});

describe('countIdentical / countAnswered / countDiffering', () => {
  it('一致 = 有答案且与 current 相同', () => {
    expect(countIdentical(ITEMS)).toBe(1);          // B
  });
  it('识别到答案的题数（用于上传成功提示）', () => {
    expect(countAnswered(ITEMS)).toBe(4);           // 除"没解析出答案"那题
  });
  it('与库里不同 = 有答案、有 current、且不相等（勾覆盖才写）', () => {
    expect(countDiffering(ITEMS)).toBe(1);          // C
    expect(countDiffering([{ answer: 'A', current: '' }])).toBe(0);
  });
});
