import { describe, expect, it } from 'vitest';

import { paperDrift } from '../materialDrift';

describe('paperDrift（D1 上架一致性）', () => {
  it('卷已发布 + 资料未上架 → paper_public', () => {
    const r = paperDrift({ type: 'paper', status: 0, exam: { known: true, paper_type: 'PUBLISHED' } });
    expect(r.kind).toBe('paper_public');
    expect(r.label).toBe('上架不一致');
    expect(r.hint).toContain('上架');
  });

  it('资料已上架 + 卷未发布 → material_public', () => {
    const r = paperDrift({ type: 'paper', status: 1, exam: { known: true, paper_type: 'DRAFT' } });
    expect(r.kind).toBe('material_public');
    expect(r.label).toBe('上架不一致');
  });

  it('两边一致 → 空', () => {
    expect(paperDrift({ type: 'paper', status: 1, exam: { known: true, paper_type: 'PUBLISHED' } }).kind).toBe('');
    expect(paperDrift({ type: 'paper', status: 0, exam: { known: true, paper_type: 'DRAFT' } }).kind).toBe('');
  });

  it('ENDED 历史卷不参与判定（原卷仍可在资料库看）', () => {
    expect(paperDrift({ type: 'paper', status: 1, exam: { known: true, paper_type: 'ENDED' } }).kind).toBe('');
    expect(paperDrift({ type: 'paper', status: 0, exam: { known: true, paper_type: 'ENDED' } }).kind).toBe('');
  });

  it('非试卷 / 未建卷 → 空', () => {
    expect(paperDrift({ type: 'card', status: 1, exam: null }).kind).toBe('');
    expect(paperDrift({ type: 'article', status: 1 }).kind).toBe('');
    expect(paperDrift({ type: 'paper', status: 0, exam: { known: false } }).kind).toBe('');
  });
});
