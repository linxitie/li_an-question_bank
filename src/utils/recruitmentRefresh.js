/**
 * 招考信息统一刷新内核
 * =====================
 * 背景：招考信息此前在 4 个页面各自 `mounted()` 里取数一次，且都不订阅后端的
 * WebSocket 广播。结果后端爬完并广播了「招考信息更新」，前端完全无感；
 * 页面常驻时也永不刷新。这是「多次修复无效」的结构性原因之一。
 *
 * 本内核把触发、节流、去重、破缓存、生命周期清理收敛到一处，5 处渲染点共用。
 *
 * 触发源（7 个）：
 *   1. __VTJ_SYNC__   后端爬取完成广播 → 防抖 1.5s 后刷新
 *   2. visibilitychange 标签页回到前台（距上次 > 阈值）
 *   3. focus          窗口重新获得焦点（距上次 > 阈值）
 *   4. 跨日           本地日期变化（保证「每日更新」语义在跨零点后生效）
 *   5. 定时轮询       默认 15 分钟，仅页面可见时计时
 *   6. 手动           调用返回值的 refresh('manual')
 *   7. 登录态变化     匿名 → 已登录（招考页无需登录，WS 仅登录后建立）
 *
 * 设计约束：
 *   - 不依赖 Vue，可同时用于 Options API（.vtj 手写页）与 <script setup>（src/views）
 *   - 不调用 useProvider，故不参与 VTJ 版本一致性校验，也不会被设计器覆盖
 *   - destroy() 必须清理全部监听器与定时器（招考页均为常驻页，泄漏会累积）
 */

const AUTH = () => (typeof window !== 'undefined' ? window.__VTJ_AUTH__ : null);

function isVisible() {
  return typeof document === 'undefined' || !document.hidden;
}

function isLoggedIn() {
  const a = AUTH();
  try {
    return !!(a && a.isLoggedIn && a.isLoggedIn());
  } catch (e) {
    return false;
  }
}

/** 本地日期字符串 YYYY-MM-DD，用于跨日检测 */
function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/**
 * @param {Object} options
 * @param {(ctx:{signal:AbortSignal, ts:number}) => Promise<any>} options.fetchFn
 *        实际取数函数。必须自行使用 ctx.signal 与 ctx.ts（破缓存）。
 * @param {(data:any, meta:any) => void} [options.onData] 数据回调
 * @param {(err:Error) => void} [options.onError]
 * @param {number} [options.pollMs=900000]   轮询间隔，默认 15 分钟
 * @param {number} [options.minIntervalMs=60000] 同源刷新最小间隔（防抖/聚焦节流）
 * @param {string} [options.syncMessage='招考信息更新'] 关注的广播消息名
 * @returns {{refresh:(reason?:string)=>void, destroy:()=>void, getLastLoaded:()=>number}}
 */
export function createRecruitmentRefresher(options) {
  const {
    fetchFn,
    onData,
    onError,
    pollMs = 15 * 60 * 1000,
    minIntervalMs = 60 * 1000,
    syncMessage = '招考信息更新',
  } = options || {};

  let destroyed = false;
  let inFlight = false;
  let controller = null;
  let pollTimer = null;
  let syncTimer = null;
  let loginTimer = null;
  let lastLoadedAt = 0;
  let lastDate = today();
  let lastWasLoggedIn = isLoggedIn();

  function log(...args) {
    if (typeof console !== 'undefined' && console.debug) {
      console.debug('[RecruitmentRefresh]', ...args);
    }
  }

  async function doRefresh(reason) {
    if (destroyed || inFlight || typeof fetchFn !== 'function') return;
    inFlight = true;
    if (controller) { try { controller.abort(); } catch (e) {} }
    controller = new AbortController();
    const ts = Date.now();
    try {
      const data = await fetchFn({ signal: controller.signal, ts });
      if (destroyed) return;
      lastLoadedAt = Date.now();
      lastDate = today();
      if (typeof onData === 'function') onData(data, data && data.meta);
    } catch (e) {
      // 用户主动取消不算错误
      if (e && (e.name === 'AbortError' || e.__aborted)) return;
      if (typeof onError === 'function') onError(e);
      else console.warn('[RecruitmentRefresh] 刷新失败:', e && e.message);
    } finally {
      inFlight = false;
    }
  }

  /** 带节流与在途去重的刷新 */
  function refresh(reason, immediate) {
    if (destroyed) return;
    if (inFlight) { log('跳过（正在请求）', reason); return; }
    if (!immediate && lastLoadedAt && Date.now() - lastLoadedAt < minIntervalMs) {
      log('跳过（节流窗口内）', reason);
      return;
    }
    doRefresh(reason);
  }

  // ---- 触发源 1：后端广播 ----
  function onSync(e) {
    const d = e && e.detail && e.detail.data;
    const msg = d && (d.message || d.msg);
    // 兼容：未带 message 的 sync 事件也刷新，避免漏事件
    if (msg && msg !== syncMessage) return;
    if (syncTimer) clearTimeout(syncTimer);
    syncTimer = setTimeout(() => { syncTimer = null; refresh('ws-sync', true); }, 1500);
  }

  // ---- 触发源 2：可见性 ----
  function onVisibility() {
    if (!document.hidden) refresh('visible');
  }

  // ---- 触发源 3：聚焦 ----
  function onFocus() { refresh('focus'); }

  // ---- 触发源 5：轮询（仅页面可见时计时）----
  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => {
      if (!isVisible()) return;      // 不可见不请求，省流量也省后端
      refresh('poll');
    }, pollMs);
  }
  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  // ---- 触发源 7：登录态变化（WS 仅登录后建立，匿名用户无广播）----
  function startLoginWatch() {
    loginTimer = setInterval(() => {
      const now = isLoggedIn();
      if (now && !lastWasLoggedIn) {
        lastWasLoggedIn = now;
        refresh('login', true);       // 登录后立即拉一次（此时 WS 才建立）
      } else {
        lastWasLoggedIn = now;
      }
    }, 15000);
  }

  // ---- 触发源 4：跨日 ----
  function checkDayRollover() {
    const now = today();
    if (now !== lastDate) {
      lastDate = now;
      refresh('new-day', true);
    }
  }
  const dayTimer = setInterval(checkDayRollover, 60 * 1000);

  // ---- 绑定 ----
  if (typeof window !== 'undefined') {
    window.addEventListener('__VTJ_SYNC__', onSync);
    window.addEventListener('focus', onFocus);
  }
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibility);
  }
  startPolling();
  startLoginWatch();

  // 首屏加载不受节流限制
  doRefresh('initial');

  return {
    refresh: (reason) => refresh(reason || 'manual', true),
    getLastLoaded: () => lastLoadedAt,
    destroy() {
      destroyed = true;
      stopPolling();
      if (syncTimer) { clearTimeout(syncTimer); syncTimer = null; }
      if (loginTimer) { clearInterval(loginTimer); loginTimer = null; }
      clearInterval(dayTimer);
      if (controller) { try { controller.abort(); } catch (e) {} controller = null; }
      if (typeof window !== 'undefined') {
        window.removeEventListener('__VTJ_SYNC__', onSync);
        window.removeEventListener('focus', onFocus);
      }
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility);
      }
    },
  };
}

export default createRecruitmentRefresher;