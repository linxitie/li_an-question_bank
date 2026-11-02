/**
 * 平板首页「备考资料」入口的显示判定（纯函数）
 * 背景：入口是 DOM 注入（守 R3 不改 .vtj 模板），判定逻辑必须单测，
 * 否则「PC 首页也冒出一个入口」这类回归只能靠肉眼发现。
 */
import { describe, expect, it } from 'vitest';
import { shouldShowTabletMaterialsEntry } from '../tabletMaterialsEntry';

const base = {
  hash: '#/tablet/home',
  isTablet: true,
  isLoggedIn: true,
  role: 'student'
};

describe('shouldShowTabletMaterialsEntry', () => {
  it('平板 + 已登录 + 学生 + 平板首页 → 显示', () => {
    expect(shouldShowTabletMaterialsEntry(base)).toBe(true);
  });

  it('非平板（PC/手机）→ 不显示', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, isTablet: false })).toBe(false);
  });

  it('未登录 → 不显示', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, isLoggedIn: false })).toBe(false);
  });

  it('非学生/教师/管理员角色 → 不显示', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, role: 'guest' })).toBe(false);
    expect(shouldShowTabletMaterialsEntry({ ...base, role: '' })).toBe(false);
  });

  it('不在平板首页（其它路由）→ 不显示', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, hash: '#/tablet/materials' })).toBe(false);
    expect(shouldShowTabletMaterialsEntry({ ...base, hash: '#/tablet/profile' })).toBe(false);
  });

  it('平板首页带 query（如 ?tab=1）→ 仍显示', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, hash: '#/tablet/home?tab=1' })).toBe(true);
  });

  it('空白 hash（刚启动还没跳路由）→ 视为首页显示', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, hash: '' })).toBe(true);
    expect(shouldShowTabletMaterialsEntry({ ...base, hash: '#/' })).toBe(true);
  });

  it('教师/管理员同样可见（与建卡入口口径一致）', () => {
    expect(shouldShowTabletMaterialsEntry({ ...base, role: 'teacher' })).toBe(true);
    expect(shouldShowTabletMaterialsEntry({ ...base, role: 'admin' })).toBe(true);
  });
});
