import { describe, expect, it } from 'vitest';

import { parseMissingQnos } from '../qnoMissing';

/**
 * Q3（2026-11-15，导题缺号定位）：抽屉里那条「题号缺号 N 个：[46, 86, 92]」的解析。
 * 解析失败必须返回 null —— 调用方要能"原文照旧显示"，不能把告警吞掉。
 */
describe('parseMissingQnos', () => {
  it('标准格式：中括号 + 半角逗号', () => {
    expect(parseMissingQnos('题号缺号 3 个：[46, 86, 92]')).toEqual({
      count: 3,
      nos: [46, 86, 92]
    });
  });

  it('容错：全角冒号/全角逗号/多余空格/乱序/重复', () => {
    expect(parseMissingQnos('题号缺号 4 个：［ 92，46 、 46  86 ］')).toEqual({
      count: 4,
      nos: [46, 86, 92]
    });
  });

  it('不是缺号告警 → null（原文照旧显示）', () => {
    expect(parseMissingQnos('选项不全 8 题：[39, 42]')).toBeNull();
    expect(parseMissingQnos('题号缺号 3 个：[]')).toBeNull();
    expect(parseMissingQnos('')).toBeNull();
  });
});
