// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { installBadgeEntry, shouldShowBadgeEntry } from '../badgeEntry';

const btn = () => document.getElementById('global-badge-entry') as HTMLButtonElement | null;
const visible = () => {
  const b = btn();
  return !!b && b.style.display !== 'none';
};

function mockAuth(loggedIn: boolean, role: string) {
  (window as any).__VTJ_AUTH__ = {
    isLoggedIn: () => loggedIn,
    getUserRole: () => role
  };
}

describe('shouldShowBadgeEntry', () => {
  it('学生已登录 → 显示', () => {
    expect(shouldShowBadgeEntry({ hash: '#/home', isLoggedIn: true, role: 'student' })).toBe(true);
    expect(shouldShowBadgeEntry({ hash: '#/mobile/home', isLoggedIn: true, role: 'student' })).toBe(true);
  });

  it('未登录 / 非学生 → 不显示', () => {
    expect(shouldShowBadgeEntry({ hash: '#/home', isLoggedIn: false, role: 'student' })).toBe(false);
    expect(shouldShowBadgeEntry({ hash: '#/home', isLoggedIn: true, role: 'admin' })).toBe(false);
    expect(shouldShowBadgeEntry({ hash: '#/home', isLoggedIn: true, role: 'teacher' })).toBe(false);
  });

  it('登录/扫码/未授权/徽章页自身 → 不显示', () => {
    for (const hash of ['#/login', '#/login?logout=1', '#/scan', '#/unauthorized', '#/badges', '#/badges-demo']) {
      expect(shouldShowBadgeEntry({ hash, isLoggedIn: true, role: 'student' })).toBe(false);
    }
  });
});

describe('installBadgeEntry (DOM)', () => {
  let uninstall: (() => void) | null = null;

  beforeEach(() => {
    uninstall?.();
    uninstall = null;
    document.body.innerHTML = '';
    document.getElementById('global-badge-entry-style')?.remove();
    window.location.hash = '#/home';
  });

  it('学生登录后注入按钮，文案为「我的徽章」', () => {
    mockAuth(true, 'student');
    uninstall = installBadgeEntry(window);
    expect(visible()).toBe(true);
    expect(btn()?.textContent).toContain('我的徽章');
    expect(btn()?.getAttribute('aria-label')).toBe('我的徽章');
  });

  it('管理员不注入（管理端有自己入口）', () => {
    mockAuth(true, 'admin');
    uninstall = installBadgeEntry(window);
    expect(visible()).toBe(false);
  });

  it('在徽章页自身不显示（避免重复入口）', () => {
    window.location.hash = '#/badges';
    mockAuth(true, 'student');
    uninstall = installBadgeEntry(window);
    expect(visible()).toBe(false);
  });

  it('点击跳转到 #/badges', () => {
    mockAuth(true, 'student');
    uninstall = installBadgeEntry(window);
    btn()!.click();
    expect(window.location.hash).toContain('/badges');
  });

  it('登出后隐藏（hashchange 触发同步）', () => {
    mockAuth(true, 'student');
    uninstall = installBadgeEntry(window);
    expect(visible()).toBe(true);
    (window as any).__VTJ_AUTH__.isLoggedIn = () => false;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(visible()).toBe(false);
  });

  it('卸载后按钮被移除', () => {
    mockAuth(true, 'student');
    const cleanup = installBadgeEntry(window);
    expect(btn()).toBeTruthy();
    cleanup();
    expect(btn()).toBeNull();
  });
});
