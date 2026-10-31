/**
 * 「我的」页里的「我的徽章」入口（DOM 注入，遵守 R3：不改 .vtj 模板）
 *
 * 背景：学生端「我的」页是 VTJ 页面（`.vtj/vue/mobile_profile.vue`），AI 不得改其
 * `<template>`。所以这里在运行时找到「我的成就」那一行，克隆出结构完全相同的
 * 「我的徽章」行插在它后面，点击进 `#/badges`。
 *
 * 附带作用：替代原先左下角的两个悬浮按钮（徽章入口 + 退出登录），避免与页面内
 * 既有入口重复。
 */

const ROW_ID = 'injected-badge-menu-item';
const TEXT = '我的徽章';
const ANCHOR_TEXT = '我的成就';

export interface ProfileEntryInput {
  hash: string;
  isLoggedIn: boolean;
  role: string;
}

/** 是否应该注入（纯函数，便于单测） */
export function shouldInjectBadgeMenu({ hash, isLoggedIn, role }: ProfileEntryInput): boolean {
  if (!isLoggedIn) return false;
  if (role !== 'student') return false;
  const h = hash || '';
  return h.startsWith('#/mobile/profile') || h.startsWith('#/tablet/profile');
}

function findRowByText(doc: Document, text: string): HTMLElement | null {
  const names = Array.from(doc.querySelectorAll<HTMLElement>('.menu-name'));
  const hit = names.find((n) => (n.textContent || '').trim() === text);
  return (hit?.closest('.menu-item') as HTMLElement) || null;
}

export function installProfileBadgeEntry(win: Window = window): () => void {
  const doc = win.document;
  const auth = () => (win as any).__VTJ_AUTH__;

  const inject = () => {
    if (doc.getElementById(ROW_ID)) return;
    const a = auth();
    const logged = typeof a?.isLoggedIn === 'function' ? !!a.isLoggedIn() : false;
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    if (!shouldInjectBadgeMenu({ hash: win.location.hash, isLoggedIn: logged, role })) return;

    const anchor = findRowByText(doc, ANCHOR_TEXT);
    if (!anchor || !anchor.parentElement) return;

    const row = anchor.cloneNode(true) as HTMLElement;
    row.id = ROW_ID;
    row.setAttribute('data-injected', 'badge-entry');
    const name = row.querySelector('.menu-name');
    if (name) name.textContent = TEXT;
    // 图标换成盾形（避免和成就的奖杯重复）
    const icon = row.querySelector('.menu-icon');
    if (icon) {
      icon.innerHTML =
        '<svg width="20" height="20" viewBox="0 0 16 16" fill="none" aria-hidden="true">' +
        '<path d="M8 1.6 14 4v4.2c0 2.9-2.5 5.1-6 6.2-3.5-1.1-6-3.3-6-6.2V4z" ' +
        'stroke="#2a5298" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<path d="M8 5.2v4.4" stroke="#2a5298" stroke-width="1.3" stroke-linecap="round"/>' +
        '</svg>';
    }
    row.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      win.location.hash = '#/badges';
    });
    anchor.insertAdjacentElement('afterend', row);
  };

  inject();
  win.addEventListener('hashchange', inject);
  const timer = win.setInterval(inject, 1200);

  return () => {
    win.removeEventListener('hashchange', inject);
    win.clearInterval(timer);
    doc.getElementById(ROW_ID)?.remove();
  };
}
