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
/* 平板首页的 .quick-actions 是「中间窄栏」里的 4 列网格（实测每列 80px、整块仅 368 宽），
 * 再往里塞第 5 个会把整行挤扁 —— 所以入口放在 .quick-actions **下面**，
 * 作为独立一行（宽度跟随父容器）。 */
#${ENTRY_ID} {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 6px 10px;
  width: 100%;
  box-sizing: border-box;
  min-height: 56px;
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8f9fc;
  border: 1px solid #eef1f6;
  cursor: pointer;
  user-select: none;
  transition: background 0.3s ease, transform 0.3s ease;
}
#${ENTRY_ID}:hover { background: #f0f2f5; transform: translateY(-2px); }
#${ENTRY_ID}:active { transform: translateY(0); }
#${ENTRY_ID} .tme-icon {
  font-size: 22px;
  line-height: 1;
  flex: none;
}
#${ENTRY_ID} .tme-name {
  font-size: 14px;
  font-weight: 700;
  color: #1a2b5f;
  flex: none;
}
#${ENTRY_ID} .tme-desc {
  flex: 1 1 100%;
  order: 3;
  font-size: 12px;
  color: #8a97ad;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
#${ENTRY_ID} .tme-arrow {
  margin-left: auto;
  font-size: 13px;
  color: #1890ff;
  flex: none;
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
      '<span class="tme-desc">卡片 · 视频 · 指南</span>' +
      '<span class="tme-arrow">›</span>';
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
    const parent = host?.parentElement;
    if (!host || !parent) {
      existing?.remove();
      return;
    }
    // 已挂在同一个父容器里（且紧跟 quick-actions）→ 什么都不做（避免闪烁）
    if (existing && existing.parentElement === parent) return;
    ensureStyle();
    existing?.remove();
    parent.insertBefore(buildEntry(), host.nextSibling);
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
