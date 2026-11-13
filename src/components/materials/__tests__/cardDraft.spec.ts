import { describe, expect, it } from 'vitest';
import {
  BACK_MAX,
  FRONT_MAX,
  IMG_MAX,
  IMG_MAX_MB,
  checkImageFile,
  validateDraft
} from '../cardDraft';

/**
 * 「创建卡片」表单规则
 * 与后台表格导入规范保持一致（正面 ≤120 / 背面 ≤600 / 背面空须配图 / 配图 ≤2 张）。
 */
describe('validateDraft', () => {
  it('正面为空 → 提示填写正面', () => {
    expect(validateDraft({ front: '   ', back: '要点', imageCount: 0 })).toBe('请填写卡片正面');
  });

  it('背面为空且无配图 → 拒绝', () => {
    expect(validateDraft({ front: '基期量', back: '', imageCount: 0 })).toBe('背面和配图至少填一个');
  });

  it('背面为空但有配图 → 允许', () => {
    expect(validateDraft({ front: '基期量', back: '', imageCount: 1 })).toBe('');
  });

  it('正常正面 + 背面 → 允许', () => {
    expect(validateDraft({ front: '基期量', back: '基期 = 现期 /（1+增长率）', imageCount: 0 })).toBe('');
  });

  it(`正面超过 ${FRONT_MAX} 字 → 拒绝`, () => {
    const msg = validateDraft({ front: '字'.repeat(FRONT_MAX + 1), back: '要点', imageCount: 0 });
    expect(msg).toContain(String(FRONT_MAX));
  });

  it(`背面超过 ${BACK_MAX} 字 → 拒绝`, () => {
    const msg = validateDraft({ front: '正面', back: '字'.repeat(BACK_MAX + 1), imageCount: 0 });
    expect(msg).toContain(String(BACK_MAX));
  });
});

describe('checkImageFile', () => {
  const ok = { type: 'image/png', size: 1024 };

  it('png 且未超数量 → 通过', () => {
    expect(checkImageFile(ok, 0)).toBe('');
  });

  it('gif 被拒', () => {
    expect(checkImageFile({ type: 'image/gif', size: 1024 }, 0)).toContain('png');
  });

  it(`超过 ${IMG_MAX_MB}MB 被拒`, () => {
    expect(checkImageFile({ type: 'image/jpeg', size: (IMG_MAX_MB + 1) * 1024 * 1024 }, 0))
      .toContain(String(IMG_MAX_MB));
  });

  it(`已有 ${IMG_MAX} 张时再传被拒`, () => {
    expect(checkImageFile(ok, IMG_MAX)).toContain(String(IMG_MAX));
  });
});
