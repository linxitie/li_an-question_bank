import { createViteConfig } from '@vtj/cli';
import { execSync } from 'node:child_process';
import { createDevTools } from '@vtj/pro/vite';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Plugin } from 'vite';
import proxy from './proxy.config';

const DEV_PORT = 9527;

/**
 * 构建版本号：写入前端产物，用于与后端 /health 的 revision 比对。
 * 为什么用 git 短 SHA 而不是时间戳：前后端同一次提交必须得到同一个值，
 * 时间戳每次构建都不同，会把「同一版本」误判成「版本不一致」。
 */
function resolveBuildSha(): string {
  try {
    return execSync('git rev-parse --short HEAD', {
      cwd: workspaceRoot,
      encoding: 'utf8',
      timeout: 3000,
    }).trim();
  } catch {
    return 'unknown';
  }
}

const BUILD_SHA = resolveBuildSha();
const BUILD_TIME = new Date().toISOString();
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

/**
 * 构建版本注入插件。
 * 为什么用 transform 而不是 config.define：@vtj/cli 的 createViteConfig 会先构造完整 config、
 * 再调用 defineConfig 回调并直接把返回值交给 Vite，dev 下 define 未生效（实测 serve 的 main.ts
 * 仍保留未替换的标识符），因此改为在 transform 阶段做字面量替换，dev/build 行为一致。
 */
function buildStamp(): Plugin {
  return {
    name: 'build-stamp',
    enforce: 'pre',
    transform(code) {
      if (!code.includes('__BUILD_SHA__') && !code.includes('__BUILD_TIME__')) {
        return null;
      }
      return code
        .replace(/__BUILD_SHA__/g, JSON.stringify(BUILD_SHA))
        .replace(/__BUILD_TIME__/g, JSON.stringify(BUILD_TIME));
    },
  };
}

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
    buildStamp(),
    devRuntimeSafety(),
    createDevTools({ hm: '' }),
  ],
  defineConfig(config) {
    config.root = workspaceRoot;
    config.server = {
      ...config.server,
      port: DEV_PORT,
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

    // 预览服务器同样固定 9527，避免 `vite preview` 回落到 4173 形成第二端口。
    config.preview = {
      ...config.preview,
      port: DEV_PORT,
      strictPort: true,
    };
    return config;
  },
});
