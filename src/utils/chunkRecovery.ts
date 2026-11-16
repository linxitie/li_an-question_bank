/**
 * 动态 import 失败自动恢复（2026-11-14）。
 *
 * 背景：dev server 重启/HMR 失效、或浏览器磁盘缓存损坏（ERR_CACHE_READ_FAILURE）时，
 * 路由懒加载会抛 "Failed to fetch dynamically imported module"，页面停在「模块加载失败」，
 * 用户必须手动刷新几次才能恢复。这里统一拦截并自动重载（带次数保护，避免死循环）。
 */

const RELOAD_KEY = 'dsh:chunk-reload';
const RELOAD_WINDOW_MS = 30_000;
const MAX_RELOADS = 2;

const CHUNK_ERROR_PATTERNS = [
  /Failed to fetch dynamically imported module/i,
  /Importing a module script failed/i,
  /error loading dynamically imported module/i,
  /Failed to load module script/i,
  /ERR_CACHE_READ_FAILURE/i,
  /ChunkLoadError/i
];

/** 判断异常是否属于「页面模块没加载下来」这一类（而不是业务代码报错）。 */
export function isChunkLoadError(error: unknown): boolean {
  const source = error as { message?: string } | null | undefined;
  const message = String(source?.message ?? error ?? '');
  return CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

/**
 * 自动重载一次当前页面；30 秒内最多 2 次，超出后交给错误边界提示。
 * 返回 true 表示已经发起重载。
 */
export function reloadForChunkError(): boolean {
  if (typeof window === 'undefined') return false;
  const now = Date.now();
  let lastAt = 0;
  let attempts = 0;
  try {
    const [prevAt, prevAttempts] = (sessionStorage.getItem(RELOAD_KEY) || '')
      .split(':')
      .map((value) => Number(value) || 0);
    lastAt = prevAt;
    attempts = prevAttempts;
  } catch {
    // 隐私模式下 sessionStorage 可能不可用：仍允许重载一次
  }
  attempts = now - lastAt < RELOAD_WINDOW_MS ? attempts + 1 : 1;
  if (attempts > MAX_RELOADS) return false;
  try {
    sessionStorage.setItem(RELOAD_KEY, now + ':' + attempts);
  } catch {
    // 忽略存储失败
  }
  // 带唯一参数重载，绕开可能已损坏的磁盘缓存条目
  const url = new URL(window.location.href);
  url.searchParams.set('__reload', String(now));
  window.location.replace(url.toString());
  return true;
}

/** 安装全局兜底：Vite 动态模块预加载失败事件。 */
export function installChunkRecovery(): void {
  if (typeof window === 'undefined') return;
  window.addEventListener('vite:preloadError', (event) => {
    if (reloadForChunkError()) event.preventDefault();
  });
}
