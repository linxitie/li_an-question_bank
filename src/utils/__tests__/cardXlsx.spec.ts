import { describe, expect, it } from 'vitest';

import {
  guessXlsxMapping,
  isMappingReady,
  mappingPayload,
  mappingSummary
} from '../cardXlsx';

describe('guessXlsxMapping', () => {
  it('识别标准的「正面/背面/分类/考点/封面」五列表头', () => {
    const m = guessXlsxMapping(['正面', '背面', '分类', '考点', '封面']);
    expect(m).toEqual({ front: 0, back: 1, category: 2, point: 3, cover: 4 });
  });

  it('表头带空格/大小写/英文也能认', () => {
    const m = guessXlsxMapping([' Front ', 'BACK', 'Category']);
    expect(m.front).toBe(0);
    expect(m.back).toBe(1);
    expect(m.category).toBe(2);
    expect(m.point).toBeNull();
  });

  it('「答案」也算背面、「题干」也算正面（旧表头兼容）', () => {
    const m = guessXlsxMapping(['题干', '答案', '解析']);
    expect(m.front).toBe(0);
    expect(m.back).toBe(1);
  });

  it('同一列不会被两个字段抢走', () => {
    const m = guessXlsxMapping(['答案（背面）', '备注']);
    expect(m.back).toBe(0);
    expect(m.front).toBeNull();
    expect(m.cover).toBeNull();
  });

  it('认不出时全为 null，不瞎猜', () => {
    expect(guessXlsxMapping(['A', 'B', 'C'])).toEqual({
      front: null,
      back: null,
      category: null,
      point: null,
      cover: null
    });
  });
});

describe('isMappingReady', () => {
  it('正背面都选且不同列才算就绪', () => {
    expect(isMappingReady({ front: 0, back: 1, category: null, point: null, cover: null })).toBe(true);
    expect(isMappingReady({ front: 0, back: null, category: null, point: null, cover: null })).toBe(false);
    expect(isMappingReady({ front: 0, back: 0, category: null, point: null, cover: null })).toBe(false);
  });
});

describe('mappingPayload / mappingSummary', () => {
  it('只带填了的字段，列号原样（0 基）', () => {
    const payload = mappingPayload({ front: 0, back: 2, category: null, point: null, cover: 4 });
    expect(payload).toEqual({ front: 0, back: 2, cover: 4 });
  });

  it('摘要写清"第几列 + 表头名"，方便人眼核对', () => {
    const headers = ['正面', '背面', '分类'];
    const summary = mappingSummary({ front: 0, back: 1, category: 2, point: null, cover: null }, headers);
    expect(summary).toContain('正面=第1列「正面」');
    expect(summary).toContain('分类=第3列「分类」');
    expect(summary).not.toContain('考点');
  });
});
