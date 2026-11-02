/**
 * 平板首页「备考资料」入口（DOM 注入，遵守 R3：不改 `.vtj` 页面模板）
 *
 * 背景（2026-11-02 变更）：平板与电脑改为**同一套页面**，`/tablet/home` 现在渲染的是
 * 电脑首页组件 `$vtj/vue/home_page.vue`（内含 `navbar.vue`）。电脑首页本身没有「备考资料」
 * 入口（电脑用户从资源中心进），而平板用户需要一个显眼入口。
 *
 * 做法：运行时往顶部导航栏 `.navbar-menu` 追加一个 `.menu-item`「📚 备考资料」，
 * 与「首页 / 题库 / 关于砺安题库 / 论坛」同款；点击进 `/materials/xingce`。
 *
 * 约束：
 *  · 只在平板 + `/tablet/home` + 已登录 + student/teacher/admin 时注入（电脑首页不出现）；
 *  · 幂等：id 标记 + hashchange/resize/1.2s 定时 + MutationObserver(500ms 节流) 兜底；
 *  · 不改 `.vtj` 模板（R3），样式用 id 选择器自带。
 */

const ENTRY_ID = 'tablet-materials-entry';
const STYLE_ID = 'tablet-materials-entry-style';
/** 电脑首页顶部导航的菜单容器（`.vtj/vue/navbar.vue`） */
const HOST_SELECTOR = '.navbar-menu';
const HOME_HASH = '#/tablet/home';
const TARGET_HASH = '#/materials/xingce';

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
#${ENTRY_ID} {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  padding: 0 14px;
  color: rgba(255, 255, 255, 0.86);
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  border-radius: 8px;
  transition: color 0.2s ease, background 0.2s ease;
}
#${ENTRY_ID}:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}
#${ENTRY_ID}:active { background: rgba(255, 255, 255, 0.14); }
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

  const buildEntry = (): HTMLAnchorElement => {
    const el = doc.createElement('a');
    el.id = ENTRY_ID;
    el.className = 'menu-item';
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    el.innerHTML = '<span class="menu-text">📚 备考资料</span>';
    const go = () => {
      win.location.hash = TARGET_HASH;
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

  const detectTablet = () =>
    /ipad|tablet/i.test(win.navigator.userAgent) ||
    (win.innerWidth >= 768 &&
      win.innerWidth <= 1024 &&
      (typeof win.navigator.maxTouchPoints === 'number'
        ? win.navigator.maxTouchPoints > 0
        : 'ontouchstart' in win));

  const sync = () => {
    const a = auth();
    const logged = typeof a?.isLoggedIn === 'function' ? !!a.isLoggedIn() : false;
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    const visible = shouldShowTabletMaterialsEntry({
      hash: win.location.hash,
      isTablet: detectTablet(),
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
    if (existing && existing.parentElement === host) return;
    ensureStyle();
    existing?.remove();
    host.appendChild(buildEntry());
  };

  sync();
  win.addEventListener('hashchange', sync);
  win.addEventListener('resize', sync);
  const timer = win.setInterval(sync, 1200);
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
