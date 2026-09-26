import type { ServerResponse } from 'node:http';
import type { ProxyOptions } from 'vite';

const DEFAULT_BACKEND_ORIGIN = 'http://127.0.0.1:8000';

function resolveBackendOrigin(): string {
  const raw = process.env.DEV_BACKEND_ORIGIN || DEFAULT_BACKEND_ORIGIN;
  const url = new URL(raw);

  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error(`DEV_BACKEND_ORIGIN 仅支持 http/https：${url.protocol}`);
  }

  return url.origin;
}

const backendOrigin = resolveBackendOrigin();

const RECOVERABLE_CODES = new Set([
  'ECONNRESET',
  'ECONNABORTED',
  'EPIPE',
  'ETIMEDOUT',
  'ECONNREFUSED',
  'EHOSTUNREACH',
  'ENETUNREACH',
  'ENETDOWN',
]);

function isServerResponse(value: unknown): value is ServerResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ServerResponse).writeHead === 'function' &&
    'headersSent' in value
  );
}

function statusForCode(code: string): number {
  if (code === 'ETIMEDOUT') return 504;
  if (
    code === 'ECONNREFUSED' ||
    code === 'EHOSTUNREACH' ||
    code === 'ENETUNREACH' ||
    code === 'ENETDOWN'
  ) {
    return 503;
  }
  return 502;
}

function createProxyConfigure(scope: string): NonNullable<ProxyOptions['configure']> {
  return (proxy) => {
    proxy.on('error', (error, _request, response) => {
      const code = (error as NodeJS.ErrnoException).code;

      if (!code || !RECOVERABLE_CODES.has(code)) {
        console.error(`[vite-proxy:${scope}] 非预期错误`, error);
        return;
      }

      if (
        isServerResponse(response) &&
        !response.headersSent &&
        !response.writableEnded
      ) {
        response.writeHead(statusForCode(code), {
          'Content-Type': 'application/json; charset=utf-8',
        });
        response.end(
          JSON.stringify({
            detail: '后端服务暂不可用，请稍后重试',
            code: 'BACKEND_UNAVAILABLE',
          })
        );
        return;
      }

      console.warn(`[vite-proxy:${scope}] 连接中断(${code})，已释放`);
    });
  };
}

const baseProxy = {
  target: backendOrigin,
  changeOrigin: true,
};

export default {
  '/api': {
    ...baseProxy,
    configure: createProxyConfigure('api'),
  },
  '/ws': {
    ...baseProxy,
    ws: true,
    configure: createProxyConfigure('ws'),
  },
  '/static': {
    ...baseProxy,
    configure: createProxyConfigure('static'),
  },
  '/uploads': {
    ...baseProxy,
    configure: createProxyConfigure('uploads'),
  },
};
