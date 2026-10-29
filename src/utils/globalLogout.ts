/**
 * 学生端全局「退出登录」按钮（方案 B）
 *
 * 背景：学生端 PC 首页（.vtj/vue/home_page.vue）没有任何退出入口，
 * `src/layouts` 里只有 AdminLayout / TeacherLayout 才有退出按钮。
 * 因 R3 禁止改动 `.vtj/` 页面的 `<template>`，这里用「DOM 注入」在学生端
 * 全站提供一个固定入口，不改动任何 VTJ 模板。
 *
 * 设计约束（见 docs/plans/学生端退出登录_方案B_设计与效果图_v1.md）：
 * - 仅 student 角色显示（管理端/教师端布局已有退出，避免重复）
 * - 登录页 / 扫码页 / 未授权页不显示
 * - 位置：左下角（右下角已被 AI 助手悬浮球占用）
 * - z-index 9998，低于 Element 弹窗遮罩
 */

const HIDDEN_PREFIXES = ['#/login', '#/scan', '#/unauthorized'];
const BTN_ID = 'global-logout-btn';
const STYLE_ID = 'global-logout-style';

export interface LogoutVisibilityInput {
  /** 当前 hash，如 '#/home' 或 '#/login?logout=1' */
  hash: string;
  /** 是否已登录 */
  isLoggedIn: boolean;
  /** 用户角色：student / teacher / admin */
  role: string;
}

/** 是否应该显示全局退出按钮（纯函数，便于单测） */
export function shouldShowLogout({ hash, isLoggedIn, role }: LogoutVisibilityInput): boolean {
  if (!isLoggedIn) return false;
  if (role !== 'student') return false;
  const h = hash || '';
  return !HIDDEN_PREFIXES.some((p) => h.startsWith(p));
}

const STYLE = `
#${BTN_ID} {
  position: fixed;
  left: 16px;
  bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  z-index: 9998;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid #dde5f2;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  color: #5c6b80;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  opacity: 0.72;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 14px rgba(22, 35, 59, 0.08);
  transition: opacity 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
#${BTN_ID}:hover,
#${BTN_ID}:focus-visible {
  opacity: 1;
  color: #d93b3b;
  border-color: #f3c9c9;
  box-shadow: 0 8px 22px rgba(217, 59, 59, 0.18);
  outline: none;
}
#${BTN_ID} .gl-icon { font-size: 14px; line-height: 1; }
@media (max-width: 767px) {
  #${BTN_ID} {
    width: 48px;
    height: 48px;
    padding: 0;
    border-radius: 50%;
    justify-content: center;
  }
  #${BTN_ID} .gl-label { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  #${BTN_ID} { transition: none; }
}
`;

const ICON_SVG =
  '<svg class="gl-icon" width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">' +
  '<path d="M9.5 2.5H4a1.5 1.5 0 0 0-1.5 1.5v8A1.5 1.5 0 0 0 4 13.5h5.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' +
  '<path d="M10.5 8h4m0 0-1.8-1.8M14.5 8l-1.8 1.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>' +
  '</svg>';

/**
 * 安装全局退出按钮。返回卸载函数（便于测试或热更新时清理）。
 */
export function installGlobalLogout(win: Window = window): () => void {
  const doc = win.document;
  const auth = () => (win as any).__VTJ_AUTH__;

  const ensureStyle = () => {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = STYLE;
    doc.head.appendChild(style);
  };

  const doLogout = () => {
    const a = auth();
    try {
      a?.logout?.();
    } catch (e) {
      // 退出失败也要把用户带回登录页，避免卡死
      console.warn('[global-logout] logout failed:', e);
    }
    win.location.hash = '#/login?logout=1';
  };

  const ensureButton = () => {
    ensureStyle();
    let btn = doc.getElementById(BTN_ID) as HTMLButtonElement | null;
    if (btn) return btn;
    btn = doc.createElement('button');
    btn.id = BTN_ID;
    btn.type = 'button';
    btn.setAttribute('aria-label', '退出登录');
    btn.title = '退出登录';
    btn.innerHTML = `${ICON_SVG}<span class="gl-label">退出登录</span>`;
    btn.addEventListener('click', () => {
      if (win.confirm('确定要退出登录吗？退出后需重新登录才能查看学习进度。')) {
        doLogout();
      }
    });
    doc.body.appendChild(btn);
    return btn;
  };

  const sync = () => {
    const a = auth();
    const logged = typeof a?.isLoggedIn === 'function' ? !!a.isLoggedIn() : false;
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    const visible = shouldShowLogout({ hash: win.location.hash, isLoggedIn: logged, role });
    const btn = doc.getElementById(BTN_ID);
    if (visible) {
      ensureButton();
      (doc.getElementById(BTN_ID) as HTMLElement).style.display = '';
    } else if (btn) {
      btn.style.display = 'none';
    }
  };

  // 初次同步 + 路由/跨标签页变化时同步；轮询兜底（登录/登出发生在路由之外时也能反应）
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
