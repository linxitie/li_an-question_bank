import { describe, expect, it } from 'vitest';
import { shouldShowLogout } from '../globalLogout';

/**
 * 全局退出按钮的显示判定（纯函数）
 * 对应 docs/plans/学生端退出登录_方案B_设计与效果图_v1.md 的 V1–V3。
 */
describe('shouldShowLogout', () => {
  it('学生已登录 + 普通页面 → 显示', () => {
    expect(
      shouldShowLogout({ hash: '#/home', isLoggedIn: true, role: 'student' })
    ).toBe(true);
  });

  it('未登录 → 不显示', () => {
    expect(
      shouldShowLogout({ hash: '#/home', isLoggedIn: false, role: 'student' })
    ).toBe(false);
  });

  it('管理端不显示（布局已有退出，避免重复）', () => {
    expect(
      shouldShowLogout({ hash: '#/admin/materials', isLoggedIn: true, role: 'admin' })
    ).toBe(false);
  });

  it('教师端不显示', () => {
    expect(
      shouldShowLogout({ hash: '#/teacher/home', isLoggedIn: true, role: 'teacher' })
    ).toBe(false);
  });

  it.each([
    ['#/login', '#/login'],
    ['#/login?logout=1', '#/login?logout=1'],
    ['#/scan', '#/scan'],
    ['#/unauthorized?reason=mobile_student_only', '#/unauthorized']
  ])('登录/扫码/未授权页不显示：%s', (_label, hash) => {
    expect(shouldShowLogout({ hash, isLoggedIn: true, role: 'student' })).toBe(false);
  });

  it('手机端学生页面同样显示（移动端样式由 CSS 媒体查询处理）', () => {
    expect(
      shouldShowLogout({ hash: '#/mobile/home', isLoggedIn: true, role: 'student' })
    ).toBe(true);
  });

  it('hash 为空时按学生首页处理 → 显示', () => {
    expect(shouldShowLogout({ hash: '', isLoggedIn: true, role: 'student' })).toBe(true);
  });
});
