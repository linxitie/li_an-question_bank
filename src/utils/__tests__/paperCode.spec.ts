import { describe, expect, it } from 'vitest';

import { canBuildPaper, isValidPaperCode, paperCodeOf, suggestPaperCode } from '../paperCode';

/**
 * D10（2026-11-15）：今天那条死路的三个判定。
 * 真机：material 139 没有 `paper_code` → 列表里连「建卷」都不显示 → 入库被 400 打回。
 */
describe('paperCodeOf', () => {
  it('paper_code 优先（改信息补的编号写在这一列）', () => {
    expect(paperCodeOf({ paper_code: 'GZ-2025-LK-5P', badge: 'OLD-CODE' })).toBe('GZ-2025-LK-5P');
  });

  it('回落 badge（老数据把编号写在 badge）', () => {
    expect(paperCodeOf({ paper_code: null, badge: 'GZ-2024-GK-T' })).toBe('GZ-2024-GK-T');
  });

  it('都没有 → 空串（不是 undefined，模板里可直接当布尔用）', () => {
    expect(paperCodeOf({})).toBe('');
    expect(paperCodeOf({ paper_code: '  ', badge: null })).toBe('');
  });
});

describe('canBuildPaper', () => {
  it('试卷类 + 还没有卷 → 显示（没有编号也显示）', () => {
    expect(canBuildPaper({ id: 139, type: 'paper' })).toBe(true);
    expect(canBuildPaper({ id: 139, type: 'paper', paper_code: null })).toBe(true);
  });

  it('已有可作答卷 → 不显示', () => {
    expect(canBuildPaper({ id: 138, type: 'paper', exam: { known: true } })).toBe(false);
  });

  it('非试卷类（文章/讲义/卡片）→ 不显示', () => {
    expect(canBuildPaper({ id: 1, type: 'article' })).toBe(false);
    expect(canBuildPaper({ id: 2, type: 'video_intro' })).toBe(false);
  });
});

describe('suggestPaperCode', () => {
  it('后端给了建议值就用它（标题解析优先）', () => {
    expect(suggestPaperCode({ id: 139, paper_code_suggest: 'GZ-2025-LK' })).toBe('GZ-2025-LK');
  });

  it('没有建议值时本地兜底 MAT-YYYYMMDD-id', () => {
    expect(suggestPaperCode({ id: 139 }, new Date(2026, 10, 15))).toBe('MAT-20261115-139');
  });
});

describe('isValidPaperCode', () => {
  it('字母数字与 -_ 都行', () => {
    expect(isValidPaperCode('GZ-2025-LK-5P')).toBe(true);
    expect(isValidPaperCode('MAT_20261115_139')).toBe(true);
  });

  it('太短 / 带空格或中文 / 超 40 位 → 不合法', () => {
    expect(isValidPaperCode('AB')).toBe(false);
    expect(isValidPaperCode('GZ 2025')).toBe(false);
    expect(isValidPaperCode('公专-2025')).toBe(false);
    expect(isValidPaperCode('A'.repeat(41))).toBe(false);
  });
});
