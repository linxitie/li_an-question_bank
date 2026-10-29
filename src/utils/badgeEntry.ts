/**
 * 学生端「我的徽章」入口（脚本注入，方案同全局退出按钮）
 *
 * 背景：学生端个人主页是 VTJ 页面，R3 禁止 AI 改其 `<template>`，
 * 因此用 DOM 注入一个固定入口，点击进入 /#/badges。
 *
 * 显示条件（与 badgeEntry.spec.ts 一致）：
 * - 已登录 且 role === 'student'
 * - 不在 登录/扫码/未授权/徽章页自身/预览页
 * 位置：左下角，位于「退出登录」按钮上方（16px + 40px 高 + 12px 间距）
 */

const HIDDEN_PREFIXES = ['#/login', '#/scan', '#/unauthorized', '#/badges', '#/badge-preview', '#/badges-demo'];
const BTN_ID = 'global-badge-entry';
const STYLE_ID = 'global-badge-entry-style';

export interface BadgeEntryVisibilityInput {
  hash: string;
  isLoggedIn: boolean;
  role: string;
}

/** 是否显示徽章入口（纯函数，便于单测） */
export function shouldShowBadgeEntry({ hash, isLoggedIn, role }: BadgeEntryVisibilityInput): boolean {
  if (!isLoggedIn) return false;
  if (role !== 'student') return false;
  const h = hash || '';
  return !HIDDEN_PREFIXES.some((p) => h.startsWith(p));
}

const STYLE = `
#${BTN_ID} {
  position: fixed;
  left: 16px;
  bottom: calc(68px + env(safe-area-inset-bottom, 0px));
  z-index: 9998;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid #dde5f2;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  color: #5c6b80;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  opacity: 0.78;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 14px rgba(22, 35, 59, 0.08);
  transition: opacity 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
#${BTN_ID}:hover,
#${BTN_ID}:focus-visible {
  opacity: 1;
  color: #2563eb;
  border-color: #c9d9f8;
  outline: none;
}
#${BTN_ID} .be-icon { font-size: 14px; line-height: 1; }
@media (max-width: 767px) {
  #${BTN_ID} {
    width: 48px;
    height: 48px;
    padding: 0;
    border-radius: 50%;
    justify-content: center;
  }
  #${BTN_ID} .be-label { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  #${BTN_ID} { transition: none; }
}
`;

/** 矢量盾牌小图标（避免 emoji 缺字） */
const ICON_SVG =
  '<svg class="be-icon" width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">' +
  '<path d="M8 1.6 14 4v4.2c0 2.9-2.5 5.1-6 6.2-3.5-1.1-6-3.3-6-6.2V4z" ' +
  'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>' +
  '<path d="M8 5.2v4.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>' +
  '</svg>';

export function installBadgeEntry(win: Window = window): () => void {
  const doc = win.document;
  const auth = () => (win as any).__VTJ_AUTH__;

  const ensureStyle = () => {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = STYLE;
    doc.head.appendChild(style);
  };

  const ensureButton = (): HTMLButtonElement => {
    ensureStyle();
    let btn = doc.getElementById(BTN_ID) as HTMLButtonElement | null;
    if (btn) return btn;
    btn = doc.createElement('button');
    btn.id = BTN_ID;
    btn.type = 'button';
    btn.setAttribute('aria-label', '我的徽章');
    btn.title = '我的徽章';
    btn.innerHTML = `${ICON_SVG}<span class="be-label">我的徽章</span>`;
    btn.addEventListener('click', () => {
      win.location.hash = '#/badges';
    });
    doc.body.appendChild(btn);
    return btn;
  };

  const sync = () => {
    const a = auth();
    const logged = typeof a?.isLoggedIn === 'function' ? !!a.isLoggedIn() : false;
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    const visible = shouldShowBadgeEntry({ hash: win.location.hash, isLoggedIn: logged, role });
    const btn = doc.getElementById(BTN_ID);
    if (visible) {
      ensureButton();
      (doc.getElementById(BTN_ID) as HTMLElement).style.display = '';
    } else if (btn) {
      btn.style.display = 'none';
    }
  };

  sync();
  win.addEventListener('hashchange', sync);
  win.addEventListener('storage', sync);
  const timer = win.setInterval(sync, 1500);

  return () => {
    win.removeEventListener('hashchange', sync);
    win.removeEventListener('storage', sync);
    win.clearInterval(timer);
    doc.getElementById(BTN_ID)?.remove();
  };
}
