/**
 * 平板首页「备考资料」入口（DOM 注入，遵守 R3：不改 `.vtj` 页面模板）
 *
 * 背景：`/tablet/home` 是 `.vtj/vue/tablet_home.vue`（VTJ 低代码页），按 R3 规定
 * AI 不得改其 `<template>`。因此运行时往首页的 `.quick-actions` 里追加一张
 * `.action-card`，与旁边「智能组卷 / 题库练习 / 错题本 / 模拟考试」同款：
 *
 *    📚 备考资料
 *       卡片 · 指南
 *
 * 与 `materialsCreateEntry.ts` / `profileBadgeEntry.ts` 同一套路：
 * 幂等标记 + MutationObserver 兜底（VTJ 重渲染把节点冲掉后补回）+ 路由切走时移除。
 * 只在平板设备、且当前路由是 /tablet/home 时生效，PC/手机零影响。
 */

const ENTRY_ID = 'tablet-materials-entry';
const STYLE_ID = 'tablet-materials-entry-style';
/** 平板首页的快捷功能容器（`.vtj/vue/tablet_home.vue:131`） */
const HOST_SELECTOR = '.quick-actions';
const HOME_HASH = '#/tablet/home';

export interface TabletEntryInput {
  hash: string;
  isTablet: boolean;
  isLoggedIn: boolean;
  role: string;
}

/** 是否应显示入口（纯函数，便于单测） */
export function shouldShowTabletMaterialsEntry({
  hash,
  isTablet,
  isLoggedIn,
  role
}: TabletEntryInput): boolean {
  if (!isTablet) return false;
  if (!isLoggedIn) return false;
  if (!['student', 'teacher', 'admin'].includes(role)) return false;
  const h = hash || '';
  return h === HOME_HASH || h === '' || h === '#/' || h.startsWith(HOME_HASH + '?');
}

const STYLE = `
/* 入口插进 .quick-actions（VTJ 页里是 repeat(4,1fr)）后正好 5 个 →
 * 有入口时改成 5 列，避免第 5 个孤零零掉到第二行。:has 不支持则回退 4 列（换行也能用）。 */
.quick-actions:has(#${ENTRY_ID}) { grid-template-columns: repeat(5, 1fr); }
#${ENTRY_ID} {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 96px;
  padding: 20px 12px;
  border-radius: 12px;
  background: #f8f9fc;
  cursor: pointer;
  user-select: none;
  transition: background 0.3s ease, transform 0.3s ease;
}
#${ENTRY_ID}:hover { background: #f0f2f5; transform: translateY(-2px); }
#${ENTRY_ID}:active { transform: translateY(0); }
#${ENTRY_ID} .tme-icon {
  font-size: 28px;
  line-height: 1;
}
#${ENTRY_ID} .tme-name {
  font-size: 14px;
  font-weight: 700;
  color: #1a2b5f;
}
#${ENTRY_ID} .tme-desc {
  font-size: 12px;
  color: #8a97ad;
}
@media (prefers-reduced-motion: reduce) {
  #${ENTRY_ID} { transition: none; }
}
`;

export function installTabletMaterialsEntry(win: Window = window): () => void {
  const doc = win.document;
  const auth = () => (win as any).__VTJ_AUTH__;

  const ensureStyle = () => {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = STYLE;
    doc.head.appendChild(style);
  };

  const buildEntry = (): HTMLDivElement => {
    const el = doc.createElement('div');
    el.id = ENTRY_ID;
    el.className = 'action-card';
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    el.innerHTML =
      '<span class="tme-icon">📚</span>' +
      '<span class="tme-name">备考资料</span>' +
      '<span class="tme-desc">卡片 · 指南</span>';
    const go = () => {
      win.location.hash = '#/tablet/materials';
    };
    el.addEventListener('click', go);
    el.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        go();
      }
    });
    return el;
  };

  const sync = () => {
    const a = auth();
    const logged = typeof a?.isLoggedIn === 'function' ? !!a.isLoggedIn() : false;
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    const isTablet = /ipad|tablet/i.test(win.navigator.userAgent) ||
      (win.innerWidth >= 768 && win.innerWidth <= 1024 &&
        (typeof win.navigator.maxTouchPoints === 'number'
          ? win.navigator.maxTouchPoints > 0
          : 'ontouchstart' in win));
    const visible = shouldShowTabletMaterialsEntry({
      hash: win.location.hash,
      isTablet,
      isLoggedIn: logged,
      role
    });
    const existing = doc.getElementById(ENTRY_ID);
    if (!visible) {
      existing?.remove();
      return;
    }
    const host = doc.querySelector(HOST_SELECTOR);
    if (!host) {
      existing?.remove();
      return;
    }
    // 已在位且仍在正确容器里 → 什么都不做（避免闪烁）
    if (existing && existing.parentElement === host) return;
    ensureStyle();
    existing?.remove();
    host.appendChild(buildEntry());
  };

  sync();
  win.addEventListener('hashchange', sync);
  win.addEventListener('resize', sync);
  const timer = win.setInterval(sync, 1200);
  // VTJ 重渲染会把注入节点冲掉：容器有变化且节点不在位时补回（500ms 节流）
  let lastFix = 0;
  const MO = (win as any).MutationObserver as
    | (new (cb: MutationCallback) => MutationObserver)
    | undefined;
  const observer =
    typeof MO === 'function'
      ? new MO(() => {
          if (doc.getElementById(ENTRY_ID)) return;
          const now = Date.now();
          if (now - lastFix < 500) return;
          lastFix = now;
          sync();
        })
      : null;
  if (observer) observer.observe(doc.body, { childList: true, subtree: true });

  return () => {
    win.removeEventListener('hashchange', sync);
    win.removeEventListener('resize', sync);
    win.clearInterval(timer);
    observer?.disconnect();
    doc.getElementById(ENTRY_ID)?.remove();
  };
}
