/**
 * PC 学生端「创建卡片」入口（DOM 注入，遵守 R3：不改 `.vtj` 页面模板）
 *
 * 背景：`#/materials/{xingce,shenlun,gongzhuan}` 三个页面都在 `.vtj/vue/` 里
 * （VTJ 低代码页），按 R3 规定 AI 不得改其 `<template>`。因此运行时在
 * `.mat-page > .top-bar` 之后插入一行操作条：
 *
 *   [学生可自建卡片提示]            [Excel 批量导入] [＋ 创建卡片]
 *
 * 与「我的徽章」入口（`profileBadgeEntry.ts`）同一套路：hashchange + 定时兜底，
 * 路由切走时自动移除，页面重渲染后自动补回。
 */

const BAR_ID = 'materials-create-bar';
const STYLE_ID = 'materials-create-bar-style';

/** 出现入口的三个科目页 */
const SUBJECT_PATHS = ['#/materials/xingce', '#/materials/shenlun', '#/materials/gongzhuan'];

export interface MaterialsCreateInput {
  hash: string;
  isLoggedIn: boolean;
  role: string;
}

/** 是否应显示建卡入口（纯函数，便于单测） */
export function shouldShowMaterialsCreate({
  hash,
  isLoggedIn,
  role
}: MaterialsCreateInput): boolean {
  if (!isLoggedIn) return false;
  if (!['student', 'teacher', 'admin'].includes(role)) return false;
  const h = hash || '';
  return SUBJECT_PATHS.some((p) => h === p || h.startsWith(p + '?') || h.startsWith(p + '/'));
}

const STYLE = `
#${BAR_ID} {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  max-width: 1200px;
  margin: 12px auto 0;
  padding: 0 24px;
  box-sizing: border-box;
}
#${BAR_ID} .mce-hint {
  margin-right: auto;
  font-size: 12px;
  color: #8a97ad;
  line-height: 1.5;
}
#${BAR_ID} .mce-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  padding: 0 16px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}
#${BAR_ID} .mce-btn:active { transform: translateY(1px); }
#${BAR_ID} .mce-ghost {
  background: #fff;
  border: 1px solid #dfe6f2;
  color: #4b5c74;
}
#${BAR_ID} .mce-ghost:hover { border-color: #b9c8de; color: #1d4ed8; }
#${BAR_ID} .mce-primary {
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  color: #fff;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
}
#${BAR_ID} .mce-primary:hover { box-shadow: 0 6px 16px rgba(37, 99, 235, 0.36); }
@media (max-width: 760px) {
  #${BAR_ID} { padding: 0 14px; }
  #${BAR_ID} .mce-hint { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  #${BAR_ID} .mce-btn { transition: none; }
}
`;

export function installMaterialsCreateEntry(win: Window = window): () => void {
  const doc = win.document;
  const auth = () => (win as any).__VTJ_AUTH__;

  const ensureStyle = () => {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = STYLE;
    doc.head.appendChild(style);
  };

  const buildBar = (): HTMLDivElement => {
    const bar = doc.createElement('div');
    bar.id = BAR_ID;
    bar.innerHTML =
      '<span class="mce-hint">学生可自建卡片：逐张创建（免审，保存即公开）· Excel 批量（提交后待审核）</span>' +
      '<a class="mce-btn mce-ghost" role="button" tabindex="0">Excel 批量导入</a>' +
      '<a class="mce-btn mce-primary" role="button" tabindex="0">＋ 创建卡片</a>';
    const ghost = bar.querySelector('.mce-ghost') as HTMLElement | null;
    const primary = bar.querySelector('.mce-primary') as HTMLElement | null;
    ghost?.addEventListener('click', () => {
      win.location.hash = '#/materials/upload?tab=excel';
    });
    primary?.addEventListener('click', () => {
      win.location.hash = '#/materials/upload';
    });
    return bar;
  };

  const sync = () => {
    const a = auth();
    const logged = typeof a?.isLoggedIn === 'function' ? !!a.isLoggedIn() : false;
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    const visible = shouldShowMaterialsCreate({
      hash: win.location.hash,
      isLoggedIn: logged,
      role
    });
    const existing = doc.getElementById(BAR_ID);
    if (!visible) {
      existing?.remove();
      return;
    }
    if (existing) return; // 已在位，避免重复插入导致闪烁
    const topBar = doc.querySelector('.mat-page > .top-bar');
    if (!topBar) return;
    ensureStyle();
    topBar.insertAdjacentElement('afterend', buildBar());
  };

  sync();
  win.addEventListener('hashchange', sync);
  win.addEventListener('storage', sync);
  const timer = win.setInterval(sync, 1200);

  return () => {
    win.removeEventListener('hashchange', sync);
    win.removeEventListener('storage', sync);
    win.clearInterval(timer);
    doc.getElementById(BAR_ID)?.remove();
  };
}
