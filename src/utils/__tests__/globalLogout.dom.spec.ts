// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { installGlobalLogout } from '../globalLogout';

/**
 * 全局退出按钮的 DOM 行为（jsdom）
 * 对应验收标准：V1 学生可见 / V2 管理端不重复 / V3 登录页不出现 / V4 点击可退出并清会话 / V5 移动端样式存在
 */

function mockAuth(opts: { loggedIn: boolean; role: string }) {
  const logout = vi.fn();
  (window as any).__VTJ_AUTH__ = {
    isLoggedIn: () => opts.loggedIn,
    getUserRole: () => opts.role,
    logout
  };
  return { logout };
}

const btn = () => document.getElementById('global-logout-btn') as HTMLButtonElement | null;
const visible = () => {
  const b = btn();
  return !!b && b.style.display !== 'none';
};

describe('installGlobalLogout (DOM)', () => {
  let uninstall: (() => void) | null = null;

  beforeEach(() => {
    uninstall?.();
    uninstall = null;
    document.body.innerHTML = '';
    document.getElementById('global-logout-style')?.remove();
    window.location.hash = '#/home';
  });

  it('V1 学生已登录 → 注入按钮且文案为「退出登录」', () => {
    mockAuth({ loggedIn: true, role: 'student' });
    uninstall = installGlobalLogout(window);
    expect(visible()).toBe(true);
    expect(btn()?.textContent).toContain('退出登录');
    expect(btn()?.getAttribute('aria-label')).toBe('退出登录');
  });

  it('V2 管理员 → 不出现（布局已自带退出）', () => {
    mockAuth({ loggedIn: true, role: 'admin' });
    uninstall = installGlobalLogout(window);
    expect(visible()).toBe(false);
  });

  it('V3 登录页 → 不出现', () => {
    window.location.hash = '#/login';
    mockAuth({ loggedIn: false, role: 'student' });
    uninstall = installGlobalLogout(window);
    expect(visible()).toBe(false);
  });

  it('V4 点击 → 确认后调用 logout 并跳到登录页', () => {
    const { logout } = mockAuth({ loggedIn: true, role: 'student' });
    window.confirm = vi.fn(() => true);
    uninstall = installGlobalLogout(window);
    btn()!.click();
    expect(window.confirm).toHaveBeenCalled();
    expect(logout).toHaveBeenCalledTimes(1);
    expect(window.location.hash).toContain('/login');
  });

  it('V4 取消确认 → 不退出', () => {
    const { logout } = mockAuth({ loggedIn: true, role: 'student' });
    window.confirm = vi.fn(() => false);
    uninstall = installGlobalLogout(window);
    btn()!.click();
    expect(logout).not.toHaveBeenCalled();
  });

  it('V5 样式已注入且含移动端媒体查询与安全区', () => {
    mockAuth({ loggedIn: true, role: 'student' });
    uninstall = installGlobalLogout(window);
    const style = document.getElementById('global-logout-style');
    expect(style).toBeTruthy();
    expect(style!.textContent).toContain('safe-area-inset-bottom');
    expect(style!.textContent).toContain('max-width: 767px');
  });

  it('退出后（未登录）按钮隐藏', async () => {
    const { logout } = mockAuth({ loggedIn: true, role: 'student' });
    window.confirm = vi.fn(() => true);
    uninstall = installGlobalLogout(window);
    expect(visible()).toBe(true);
    btn()!.click();
    expect(logout).toHaveBeenCalled();
    // 模拟会话已清 + 路由变化触发同步
    (window as any).__VTJ_AUTH__.isLoggedIn = () => false;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(visible()).toBe(false);
  });

  it('卸载会移除按钮与监听', () => {
    mockAuth({ loggedIn: true, role: 'student' });
    const cleanup = installGlobalLogout(window);
    expect(btn()).toBeTruthy();
    cleanup();
    expect(btn()).toBeNull();
  });
});
