import { describe, expect, it } from 'vitest';
import { shouldShowMaterialsCreate } from '../materialsCreateEntry';

/**
 * PC 资料页「创建卡片」入口的显示条件。
 * 三个科目页才出现；未登录 / 未知角色 / 其它页面一律不出现（避免污染首页与后台）。
 */
describe('shouldShowMaterialsCreate', () => {
  const base = { isLoggedIn: true, role: 'student' };

  it('三科资料页都显示', () => {
    for (const p of ['xingce', 'shenlun', 'gongzhuan']) {
      expect(shouldShowMaterialsCreate({ ...base, hash: `#/materials/${p}` })).toBe(true);
    }
  });

  it('带查询参数也显示', () => {
    expect(shouldShowMaterialsCreate({ ...base, hash: '#/materials/xingce?tab=card' })).toBe(true);
  });

  it('未登录不显示', () => {
    expect(shouldShowMaterialsCreate({ ...base, isLoggedIn: false, hash: '#/materials/xingce' })).toBe(
      false
    );
  });

  it('未知角色不显示', () => {
    expect(shouldShowMaterialsCreate({ ...base, role: '', hash: '#/materials/xingce' })).toBe(false);
    expect(shouldShowMaterialsCreate({ ...base, role: 'guest', hash: '#/materials/xingce' })).toBe(
      false
    );
  });

  it('教师与管理员也显示（都能建卡）', () => {
    expect(shouldShowMaterialsCreate({ ...base, role: 'teacher', hash: '#/materials/shenlun' })).toBe(
      true
    );
    expect(shouldShowMaterialsCreate({ ...base, role: 'admin', hash: '#/materials/gongzhuan' })).toBe(
      true
    );
  });

  it('其它页面不显示', () => {
    for (const h of ['#/home', '#/materials/upload', '#/badges', '#/materials/detail?subject=xingce', '#/admin/materials']) {
      expect(shouldShowMaterialsCreate({ ...base, hash: h })).toBe(false);
    }
  });

  it('空 hash 不显示', () => {
    expect(shouldShowMaterialsCreate({ ...base, hash: '' })).toBe(false);
  });
});
