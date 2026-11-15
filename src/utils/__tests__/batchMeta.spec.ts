import { describe, expect, it } from 'vitest';

import {
  BATCH_META_EMPTY,
  buildBatchMetaPayload,
  hasBatchMetaChange
} from '../batchMeta';

/**
 * D7（2026-11-15）：批量改信息的纯函数。
 * 关键语义：三项"留空=不改"，只把改过的字段发出去；一项都没改 → null（别发空 body）。
 */
describe('hasBatchMetaChange', () => {
  it('全空 → false', () => {
    expect(hasBatchMetaChange({ ...BATCH_META_EMPTY })).toBe(false);
    expect(hasBatchMetaChange({ subject: '  ', category: ' ', placement: '' })).toBe(false);
  });

  it('任一项有值 → true', () => {
    expect(hasBatchMetaChange({ ...BATCH_META_EMPTY, subject: 'gongzhuan' })).toBe(true);
    expect(hasBatchMetaChange({ ...BATCH_META_EMPTY, placement: 'both' })).toBe(true);
  });
});

describe('buildBatchMetaPayload', () => {
  it('一项都没改 → null（调用方提示，不发请求）', () => {
    expect(buildBatchMetaPayload([1, 2], { ...BATCH_META_EMPTY })).toBeNull();
  });

  it('没有勾选 → null', () => {
    expect(buildBatchMetaPayload([], { ...BATCH_META_EMPTY, subject: 'xingce' })).toBeNull();
  });

  it('只带改过的字段（分类）', () => {
    expect(buildBatchMetaPayload([116, 117], { ...BATCH_META_EMPTY, category: '行测' }))
      .toEqual({ ids: [116, 117], category: '行测' });
  });

  it('科目 + 投放位，且去掉首尾空格', () => {
    expect(
      buildBatchMetaPayload([5], { subject: ' gongzhuan ', category: '', placement: ' both ' })
    ).toEqual({ ids: [5], subject: 'gongzhuan', placement: 'both' });
  });

  it('ids 复制一份，不改动入参', () => {
    const ids = [1, 2];
    const payload = buildBatchMetaPayload(ids, { ...BATCH_META_EMPTY, subject: 'xingce' });
    expect(payload?.ids).toEqual([1, 2]);
    expect(payload?.ids).not.toBe(ids);
  });
});
