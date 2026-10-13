import { createViteConfig } from '@vtj/cli';
import { createDevTools } from '@vtj/pro/vite';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Plugin } from 'vite';
import proxy from './proxy.config';

const DEV_PORT = 9527;
const workspaceRoot = dirname(fileURLToPath(import.meta.url));

function samePath(left: string, right: string): boolean {
  const normalize = (value: string) => resolve(value).toLowerCase();
  return normalize(left) === normalize(right);
}

if (!samePath(process.cwd(), workspaceRoot)) {
  throw new Error(
    `Vite 必须从配置所在工作区启动：expected ${workspaceRoot}, received ${process.cwd()}`
  );
}

const EXPECTED_SOCKET_CODES = new Set([
  'ECONNRESET',
  'EPIPE',
  'ECONNABORTED',
]);

function devRuntimeSafety(): Plugin {
  const routeBySocket = new WeakMap<object, string>();
  const lastLogAt = new Map<string, number>();

  return {
    name: 'dev-runtime-safety',
    apply: 'serve',

    configResolved(config) {
      config.logger.info(
        `[vite] workspace=${config.root} port=${config.server.port}`
      );
    },

    configureServer(server) {
      const httpServer = server.httpServer;
      if (!httpServer) return;

      const remember = (socket: object, url?: string) => {
        routeBySocket.set(socket, url?.split('?')[0] || 'unknown');
      };

      httpServer.prependListener('upgrade', (request, socket) => {
        remember(socket, request.url);
      });

      httpServer.on('request', (request, response) => {
        remember(response.socket, request.url);
      });

      httpServer.on('connection', (socket) => {
        socket.on('error', (error: NodeJS.ErrnoException) => {
          const code = error.code || 'UNKNOWN';
          const route = routeBySocket.get(socket) || 'http';

          if (EXPECTED_SOCKET_CODES.has(code)) {
            // 鉴权类正常关闭（后端 close(4001..4004)）在 TCP 层表现为 ECONNRESET，
            // 属预期行为，降为 debug，避免开发终端刷屏掩盖真实故障。
            // 网络类真实异常仍用 warn，便于及时发现。
            const isAuthClose = route === '/ws/connect' || route === '/';
            const level = isAuthClose ? 'debug' : 'warn';
            const key = `${route}:${code}`;
            const now = Date.now();

            if (now - (lastLogAt.get(key) || 0) > 10_000) {
              console[level](
                `[vite:socket] ${route} 客户端连接中断(${code})，已安全关闭`
              );
              lastLogAt.set(key, now);
            }
          } else {
            console.error(`[vite:socket] ${route} 非预期错误`, error);
          }

          if (!socket.destroyed) socket.destroy();
        });
      });
    },
  };
}

export default createViteConfig({
  port: DEV_PORT,
  host: '0.0.0.0',
  proxy,
  plugins: [
    devRuntimeSafety(),
    createDevTools({ hm: '' }),
  ],
  defineConfig(config) {
    config.root = workspaceRoot;
    config.server = {
      ...config.server,
      strictPort: true,
      cors: false,
      hmr: {
        clientPort: DEV_PORT,
      },
      watch: {
        ignored: ['**/.worktrees/**', '**/backend/**'],
      },
      fs: {
        deny: [
          '.env',
          '.env.*',
          '*.{crt,pem}',
          '**/.git/**',
          '**/.worktrees/**',
        ],
      },
    };
    return config;
  },
});
