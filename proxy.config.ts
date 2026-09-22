/**
 * Vite 开发服务器代理配置
 *
 * 修复目标（ECONNRESET 崩溃）：
 * 后端（uvicorn）在热重载、强制重启、或连接超时被关闭时，会向所有已建立
 * 的 TCP 连接发送 RST 复位包。Vite 底层使用的 http-proxy 在 socket 收到
 * ECONNRESET / ECONNREFUSED 时，若未注册 'error' 监听器，会以
 * "throw er; // Unhandled 'error' event" 崩溃整个 dev server。
 *
 * 解决方案：为每个代理条目注册 configure() 回调，挂载 'error' 监听器，
 * 吞掉连接级错误并返回 502，保证 dev server 始终存活，下次请求自动重连。
 */

/** 可安全降级的连接级错误码（属于后端重启/宕机的正常现象，不应使进程崩溃） */
const RECOVERABLE_CODES = new Set([
  'ECONNRESET',
  'ECONNREFUSED',
  'ECONNABORTED',
  'EPIPE',
  'ETIMEDOUT',
  'EHOSTUNREACH',
]);

/**
 * 统一的代理错误处理函数
 * @param proxy http-proxy 实例
 */
function handleProxyError(proxy: any) {
  proxy.on('error', (err: any, _req: any, res: any) => {
    const code = err && err.code;

    // 后端重启/宕机导致的连接级错误：记录后返回 502，不抛异常，进程不崩溃
    if (code && RECOVERABLE_CODES.has(code)) {
      console.warn(`[vite-proxy] 后端连接异常(${code})，已容错处理，等待下次请求重试`);
      try {
        if (res && !res.headersSent && typeof res.writeHead === 'function') {
          res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
        }
        if (res && !res.finished && typeof res.end === 'function') {
          res.end(JSON.stringify({ detail: '后端服务暂不可用，请稍后重试' }));
        }
      } catch (e) {
        // 响应已关闭等边缘情况，忽略
      }
      return;
    }

    // 其他未知错误：仅记录，不中断进程（避免任何 socket error 导致 dev server 崩溃）
    console.warn('[vite-proxy] error:', code || (err && err.message) || err);
  });
}

export default {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    ws: true,
    configure: handleProxyError,
  },
  '/static': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    configure: handleProxyError,
  },
  '/uploads': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    configure: handleProxyError,
  },
};
