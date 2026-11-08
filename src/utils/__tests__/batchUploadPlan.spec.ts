import { describe, expect, it } from 'vitest';
import {
  ALLOWED_EXTS,
  MAX_BATCH_BYTES,
  MAX_BATCH_FILES,
  humanBytes,
  planUploadGroups,
  splitFileName,
  summarize,
  validateSelection
} from '../batchUploadPlan';

const f = (name: string, size = 1024) => ({ name, size });

describe('splitFileName', () => {
  it('拆分 base / 小写扩展名', () => {
    expect(splitFileName('2019 北京公专.DOCX')).toEqual({ base: '2019 北京公专', ext: 'docx' });
    expect(splitFileName('a.b.pdf')).toEqual({ base: 'a.b', ext: 'pdf' });
  });

  it('无扩展名 / 路径前缀', () => {
    expect(splitFileName('无扩展名')).toEqual({ base: '无扩展名', ext: '' });
    expect(splitFileName('C:\\tmp\\资料.pdf')).toEqual({ base: '资料', ext: 'pdf' });
  });
});

describe('validateSelection', () => {
  it('数量上限 50', () => {
    const files = Array.from({ length: MAX_BATCH_FILES + 1 }, (_, i) => f(`a${i}.docx`));
    const issues = validateSelection(files);
    expect(issues.some((i) => i.code === 'too_many')).toBe(true);
  });

  it('总量上限 2GB', () => {
    const issues = validateSelection([f('big.docx', MAX_BATCH_BYTES + 1)]);
    expect(issues.some((i) => i.code === 'too_large')).toBe(true);
  });

  it('扩展名白名单', () => {
    const issues = validateSelection([f('a.docx'), f('b.zip'), f('c.txt')]);
    const bad = issues.filter((i) => i.code === 'unsupported').map((i) => i.file);
    expect(bad).toEqual(['b.zip', 'c.txt']);
    expect(ALLOWED_EXTS).toContain('xlsx');
  });

  it('空选择给出提示', () => {
    expect(validateSelection([]).map((i) => i.code)).toEqual(['empty']);
  });

  it('合规选择无问题', () => {
    expect(validateSelection([f('a.docx'), f('b.pdf', 2048)])).toEqual([]);
  });
});

describe('planUploadGroups', () => {
  it('同名 docx + pdf 合并成一条（docx 主文件 / pdf 附件）', () => {
    const { groups, issues } = planUploadGroups([
      f('2019 北京公专.pdf', 900),
      f('2019 北京公专.docx', 1000)
    ]);
    expect(issues).toEqual([]);
    expect(groups).toHaveLength(1);
    const g = groups[0];
    expect(g.kind).toBe('pair');
    expect(g.primary.name).toBe('2019 北京公专.docx');
    expect(g.primaryExt).toBe('docx');
    expect(g.attachment?.name).toBe('2019 北京公专.pdf');
    expect(g.attachment?.ext).toBe('pdf');
  });

  it('大小写不同也算同名', () => {
    const { groups } = planUploadGroups([f('WeChat.DOCX'), f('wechat.PDF')]);
    expect(groups).toHaveLength(1);
    expect(groups[0].kind).toBe('pair');
  });

  it('只有 docx / 只有 pdf 各自单条', () => {
    const { groups } = planUploadGroups([f('a.docx'), f('b.pdf'), f('c.xlsx')]);
    expect(groups).toHaveLength(3);
    expect(groups.every((g) => g.kind === 'single')).toBe(true);
    expect(groups.map((g) => g.primaryExt)).toEqual(['docx', 'pdf', 'xlsx']);
  });

  it('同名同类型重复 → 只留第一个并报 repeated', () => {
    const { groups, issues } = planUploadGroups([f('x.docx'), f('x.docx')]);
    expect(groups).toHaveLength(1);
    expect(issues.map((i) => i.code)).toContain('repeated');
  });

  it('同名但第三个类型各自成组（pair + xlsx）', () => {
    const { groups } = planUploadGroups([f('y.docx'), f('y.pdf'), f('y.xlsx')]);
    expect(groups).toHaveLength(2);
    expect(groups[0].kind).toBe('pair');
    expect(groups[1].primaryExt).toBe('xlsx');
  });

  it('不支持的扩展名不进组、给出 issue', () => {
    const { groups, issues } = planUploadGroups([f('ok.docx'), f('bad.zip')]);
    expect(groups).toHaveLength(1);
    expect(issues[0]).toMatchObject({ code: 'unsupported', file: 'bad.zip' });
  });

  it('顺序稳定（按首次出现的 base 名）', () => {
    const { groups } = planUploadGroups([f('b.docx'), f('a.docx'), f('b.pdf')]);
    expect(groups.map((g) => g.label)).toEqual(['b', 'a']);
  });
});

describe('summarize / humanBytes', () => {
  it('统计资料数 / 文件数 / 字节 / 配对数', () => {
    const { groups } = planUploadGroups([
      f('p.docx', 100), f('p.pdf', 50), f('s.pdf', 20)
    ]);
    expect(summarize(groups)).toEqual({
      materials: 2, files: 3, bytes: 170, pairs: 1
    });
  });

  it('人读大小', () => {
    expect(humanBytes(900)).toBe('900 B');
    expect(humanBytes(2048)).toBe('2 KB');
    expect(humanBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });
});
