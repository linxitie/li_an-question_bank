/**
 * 投放位登记表单测（L4，2026-11-09）。
 * 三个使用点（上传弹窗、列表徽标、改信息弹窗）文案与归一化必须同一套口径。
 */
import { describe, expect, it } from 'vitest';
import {
  MATERIAL_PLACEMENTS,
  normalizePlacement,
  placementLabel,
  placementTone
} from '@/modules/library/materialTypes';

describe('MATERIAL_PLACEMENTS', () => {
  it('三种投放位齐全且顺序稳定（上传弹窗按此渲染）', () => {
    expect(MATERIAL_PLACEMENTS.map((p) => p.key)).toEqual(['exam', 'library', 'both']);
    expect(MATERIAL_PLACEMENTS.map((p) => p.label)).toEqual(['仅考试页', '仅资料页', '都投']);
  });
  it('每项都有给人看的解释（避免只写代号）', () => {
    for (const p of MATERIAL_PLACEMENTS) {
      expect(p.hint.length).toBeGreaterThan(8);
    }
  });
});

describe('placementLabel / placementTone', () => {
  it('列表徽标用短文案', () => {
    expect(placementLabel('exam')).toBe('考试');
    expect(placementLabel('library')).toBe('资料');
    expect(placementLabel('both')).toBe('都投');
    expect(placementLabel(null)).toBe('—');
    expect(placementLabel('')).toBe('—');
  });
  it('色调：考试=info / 资料=muted / 其它=ok', () => {
    expect(placementTone('exam')).toBe('info');
    expect(placementTone('library')).toBe('muted');
    expect(placementTone('both')).toBe('ok');
    expect(placementTone(undefined)).toBe('ok');
  });
});

describe('normalizePlacement', () => {
  it('显式值原样返回', () => {
    expect(normalizePlacement('exam')).toBe('exam');
    expect(normalizePlacement('library', 'paper')).toBe('library');
    expect(normalizePlacement('both', 'lecture')).toBe('both');
  });
  it('NULL/脏值：试卷默认 both、其余 library（与后端一致）', () => {
    expect(normalizePlacement(null, 'paper')).toBe('both');
    expect(normalizePlacement(undefined, 'lecture')).toBe('library');
    expect(normalizePlacement('garbage', 'paper')).toBe('both');
    expect(normalizePlacement('garbage', 'article')).toBe('library');
  });
});
