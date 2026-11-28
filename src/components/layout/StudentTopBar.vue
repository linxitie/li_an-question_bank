<template>
  <!-- 无可见 UI：把铃铛/头像/下载按钮补丁挂到学生端导航栏上（R3：不改 .vtj 模板） -->
  <span class="la-topbar-patch" aria-hidden="true"></span>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue';
import { applyQuestionBankLayout } from '@/utils/questionBankLayoutPatch';
import { applyTabletQuestionBankPatch } from '@/utils/tabletQuestionBankPatch';
import { applyMobileHomeLayout } from '@/utils/mobileHomeLayoutPatch';

type AuthWin = Window & {
  __VTJ_AUTH__?: {
    apiFetch?: (input: RequestInfo, init?: RequestInit) => Promise<Response>;
    isLoggedIn?: () => boolean;
    getToken?: () => string | null;
  };
};

const BELL_SELECTOR = '[data-la-bell="1"]';
let observer: MutationObserver | null = null;
let avatarUrl = '';
let avatarLoading = false;
let avatarTries = 0;
let unread = 0;
let scanTimer = 0;

function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as AuthWin).__VTJ_AUTH__;
  return auth?.apiFetch ? auth.apiFetch(url, init) : fetch(url, init);
}

function isStudentArea(): boolean {
  const path = window.location.hash.replace(/^#/, '') || '/';
  return !path.startsWith('/admin') && !path.startsWith('/teacher');
}

function openBell() {
  window.dispatchEvent(new CustomEvent('la-open-bell'));
}

function makeBell(): HTMLButtonElement {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.dataset.laBell = '1';
  btn.title = '通知与复习提醒';
  btn.setAttribute('aria-label', '通知与复习提醒');
  btn.style.cssText =
    'position:relative;display:inline-flex;align-items:center;justify-content:center;' +
    'width:36px;height:36px;border:1px solid rgba(255,255,255,.28);border-radius:10px;' +
    'background:rgba(255,255,255,.08);color:#fff;cursor:pointer;margin-right:10px;flex:0 0 auto;';
  btn.innerHTML = '<span style="font-size:16px;line-height:1">🔔</span><span data-la-badge="1" style="position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;padding:0 4px;border-radius:999px;background:#dc2626;color:#fff;font-size:10px;line-height:16px;text-align:center;display:none;"></span>';
  btn.addEventListener('click', openBell);
  return btn;
}

function paintBell() {
  const host = document.querySelector(BELL_SELECTOR) as HTMLElement | null;
  const badge = host?.querySelector('[data-la-badge="1"]') as HTMLElement | null;
  if (!badge) return;
  const text = unread > 99 ? '99+' : String(unread);
  if (badge.textContent !== text) badge.textContent = text;
  const display = unread > 0 ? 'inline-block' : 'none';
  if (badge.style.display !== display) badge.style.display = display;
}

function ensurePcBell(actions: HTMLElement): void {
  if (actions.querySelector(BELL_SELECTOR)) return;
  const avatar = actions.querySelector('.user-avatar');
  if (!avatar) return;
  actions.insertBefore(makeBell(), avatar);
}

function ensureTabletBell(navRight: HTMLElement): void {
  // 平板 header 自带铃铛（第一个 nav-icon）：不重复加，改为拦截跳转 → 打开弹窗
  const first = navRight.querySelector('.nav-icon') as HTMLElement | null;
  if (first) {
    if (!first.dataset.laBound) {
      first.dataset.laBound = '1';
      first.addEventListener(
        'click',
        (e) => {
          e.stopPropagation();
          e.preventDefault();
          openBell();
        },
        true
      );
    }
    return;
  }
  if (!navRight.querySelector(BELL_SELECTOR)) navRight.insertBefore(makeBell(), navRight.firstChild);
}

function replaceAvatar(el: HTMLElement): void {
  if (!avatarUrl || el.dataset.laAvatar === avatarUrl) return;
  el.dataset.laAvatar = avatarUrl;
  el.innerHTML = '';
  const img = document.createElement('img');
  img.src = avatarUrl;
  img.alt = '头像';
  img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;';
  img.onerror = () => {
    el.dataset.laAvatar = '';
    el.innerHTML = '<span style="font-size:18px">👤</span>';
  };
  el.appendChild(img);
}

function scan(): void {
  if (!isStudentArea()) return;
  applyQuestionBankLayout();
  applyTabletQuestionBankPatch();
  applyMobileHomeLayout();
  // 注销下载客户端入口（需求 4；页面路由同步删除）
  document.querySelectorAll('.btn-download').forEach((el) => el.remove());

  const actions = document.querySelector('.navbar-actions') as HTMLElement | null;
  if (actions) {
    ensurePcBell(actions);
    const circle = actions.querySelector('.avatar-circle') as HTMLElement | null;
    if (circle) replaceAvatar(circle);
  }

  document.querySelectorAll('.top-nav .nav-right').forEach((nav) => {
    ensureTabletBell(nav as HTMLElement);
    const avatar = nav.querySelector('.user-avatar') as HTMLElement | null;
    if (avatar) replaceAvatar(avatar);
  });

  paintBell();
}

function scheduleScan(): void {
  window.clearTimeout(scanTimer);
  scanTimer = window.setTimeout(() => {
    scan();
    // 登录发生在 App 挂载之后：首次扫描拿不到 token，这里补拉（最多 3 次）。
    if (!avatarUrl && avatarTries < 3) void loadProfile();
  }, 60);
}

async function loadProfile(): Promise<void> {
  if (avatarLoading || avatarTries >= 3) return;
  const auth = (window as AuthWin).__VTJ_AUTH__;
  const token = auth?.getToken?.() || localStorage.getItem('token') || '';
  const loggedIn = auth?.isLoggedIn ? auth.isLoggedIn() : !!token;
  if (!loggedIn && !token) return;
  avatarLoading = true;
  avatarTries += 1;
  try {
    const res = await authFetch('/api/auth/profile');
    if (!res.ok) return;
    const data = await res.json();
    if (data?.avatar) {
      avatarUrl = data.avatar;
      scheduleScan();
    }
  } catch {
    /* 头像失败不影响导航 */
  } finally {
    avatarLoading = false;
  }
}

function onBadge(e: Event): void {
  const n = Number((e as CustomEvent).detail || 0);
  unread = Number.isFinite(n) ? n : 0;
  paintBell();
}

function onAvatarUpdated(e: Event): void {
  const url = String((e as CustomEvent).detail || '');
  if (url) {
    avatarUrl = url;
    scheduleScan();
  }
}

onMounted(() => {
  void loadProfile();
  window.setTimeout(() => void loadProfile(), 1500);
  window.setTimeout(() => void loadProfile(), 4000);
  observer = new MutationObserver(scheduleScan);
  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('la-bell-badge', onBadge as EventListener);
  window.addEventListener('la-avatar-updated', onAvatarUpdated as EventListener);
  window.addEventListener('hashchange', scheduleScan);
  scheduleScan();
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
  window.clearTimeout(scanTimer);
  window.removeEventListener('la-bell-badge', onBadge as EventListener);
  window.removeEventListener('la-avatar-updated', onAvatarUpdated as EventListener);
  window.removeEventListener('hashchange', scheduleScan);
});
</script>

<style scoped>
.la-topbar-patch {
  display: none;
}
</style>
