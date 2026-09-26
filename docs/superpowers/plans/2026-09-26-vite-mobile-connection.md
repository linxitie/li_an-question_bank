# Vite Mobile WebSocket Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Per the user's explicit instruction, this plan will be executed inline by the primary agent in the main directory, without a worktree and without writing subagents.

**Goal:** Restore deterministic `npm run dev` startup on port 9527 and make `/ws/connect` survive mobile network resets without crashing the Vite development server.

**Architecture:** Fix the root cause by adding a real WebSocket proxy route and a deterministic npm dependency contract, then add a dev-only socket error boundary as defense in depth. Keep FastAPI, `src/auth.ts`, `tsconfig.json`, VTJ pages, and DSL unchanged. Use a temporary mock HTTP+WebSocket backend to prove the failure before the fix and stability after it.

**Tech Stack:** Node.js 24, npm 11, Vite 6.3, `@vtj/cli` 0.12.19, VTJ 0.16.35, TypeScript 5.9, `ws` 8.20, PowerShell, Playwright.

**Workspace:** `D:\砺安题库\砺安题库`
**Branch:** `fix/vite-mobile-connection`
**Design spec:** `solve_problems_files/Vite代理添加错误处理方案.md`
**Ports:** Vite/HMR 9527; FastAPI 8000
**Constraint:** Do not create or use a Git worktree. Do not merge whole `.worktrees/*` branches. Port only the approved file-level changes.

---

## File Map

| File | Responsibility |
|---|---|
| `package.json` | Declare every directly used tool/runtime package and pin the verified dependency contract |
| `package-lock.json` | Reproducible npm dependency tree, committed to Git |
| `.npmrc` | npm-only registry configuration |
| `.gitignore` | Stop ignoring `package-lock.json`; keep ignoring `node_modules` |
| `scripts/verify-vite-resilience.mjs` | Deterministic red/green integration harness for WebSocket proxying, resets, liveness, backend outage, and strict port |
| `proxy.config.ts` | Route `/api`, `/ws`, `/static`, `/uploads`; classify proxy errors without corrupting WebSocket sockets or leaking JWTs |
| `vite.config.ts` | Enforce workspace/port, disable VTJ analytics, isolate worktrees, and guard dev sockets |
| `index.html` | Allow mobile same-origin WebSockets through CSP |
| `solve_problems_files/Vite代理添加错误处理方案.md` | Approved design and operational contract; update final status after verification |

**Explicitly unchanged:** `tsconfig.json`, `src/auth.ts`, `backend/app/api/v1/websocket.py`, `backend/app/main.py`, `backend/app/core/security.py`, `.vtj/files/*.json`, `.vtj/vue/*.vue`, `src/vtj/vue/*.vue`, `src/views/*.vue`.

---

### Task 1: Establish the deterministic npm dependency contract

**Files:**
- Modify: `package.json`
- Modify: `.npmrc`
- Modify: `.gitignore`
- Create/track: `package-lock.json`

- [ ] **Step 1: Record the failing baseline**

Run:

```powershell
npm run dev -- --host 127.0.0.1 --port 9527
```

Expected before this task:

```text
'cross-env' 不是内部或外部命令，也不是可运行的程序
```

Also record:

```powershell
Test-Path node_modules/.bin
Test-Path node_modules/@vtj/cli/config/tsconfig.web.json
```

Expected: both `False`.

- [ ] **Step 2: Replace `package.json` with the pinned contract**

Write:

```json
{
  "name": "vtj-web-template",
  "description": "VTJ.PRO Web 项目模版",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "packageManager": "npm@11.9.0",
  "engines": {
    "node": ">=20.19.0 <25",
    "npm": ">=10 <12"
  },
  "repository": {
    "url": "https://gitee.com/newgateway/vtj"
  },
  "homepage": "https://vtj.pro",
  "scripts": {
    "setup": "npm ci",
    "dev": "cross-env ENV_TYPE=local vite",
    "build": "npm run build:prod",
    "build:sit": "vue-tsc && cross-env ENV_TYPE=sit vite build",
    "build:uat": "vue-tsc && cross-env ENV_TYPE=uat vite build",
    "build:pre": "vue-tsc && cross-env ENV_TYPE=pre vite build",
    "build:prod": "vue-tsc && cross-env ENV_TYPE=live vite build",
    "typecheck": "vue-tsc --noEmit -p tsconfig.json",
    "test:vite-resilience": "node scripts/verify-vite-resilience.mjs",
    "preview": "vite preview",
    "clean": "node ./scripts/clean.mjs",
    "sync:vtj-version": "node ./scripts/sync_vtj_version.mjs",
    "prebuild": "npm run sync:vtj-version",
    "mcp:setup": "cd vtj-mcp-server && npm install",
    "mcp:start": "node vtj-mcp-server/vtj-mcp-server.js",
    "mcp:test": "node -e \"const{spawn}=require('child_process');const s=spawn('node',['vtj-mcp-server/vtj-mcp-server.js']);let o='';s.stdout.on('data',d=>o+=d);s.on('close',()=>{const r=JSON.parse(o);console.log('VTJ MCP Server -',r.result.tools.length,'tools registered');r.result.tools.forEach(t=>console.log(' ✅',t.name))});s.stdin.write(JSON.stringify({jsonrpc:'2.0',id:1,method:'tools/list',params:{}})+'\\n');setTimeout(()=>s.stdin.end(),2000);\""
  },
  "dependencies": {
    "@vtj/charts": "0.16.35",
    "@vtj/icons": "0.16.35",
    "@vtj/ui": "0.16.35",
    "@vtj/utils": "0.16.35",
    "@vtj/web": "0.16.35",
    "@vueuse/core": "14.1.0",
    "ant-design-vue": "4.2.6",
    "axios": "1.13.6",
    "docx-preview": "0.3.7",
    "element-plus": "2.13.7",
    "mammoth": "1.8.0",
    "mockjs": "1.1.0",
    "pinia": "3.0.4",
    "vue": "3.5.34",
    "vue-i18n": "11.2.8",
    "vue-router": "4.6.4",
    "wangeditor": "4.7.15",
    "xlsx": "0.18.5"
  },
  "devDependencies": {
    "@types/node": "24.13.6",
    "@vtj/cli": "0.12.19",
    "@vtj/materials": "0.16.35",
    "@vtj/pro": "0.16.35",
    "cross-env": "7.0.3",
    "typescript": "5.9.3",
    "vite": "6.3.7",
    "vue-tsc": "3.3.11",
    "ws": "8.20.1"
  },
  "vtj": {
    "platform": "web",
    "id": "linxitie.policy-exam-bank",
    "name": "砺安题库",
    "remote": "https://app.vtj.pro"
  }
}
```

Preserve the existing `mcp:test` body exactly from the current file if the text above differs only in JSON escaping; do not change MCP behavior.

- [ ] **Step 3: Reduce `.npmrc` to npm-only configuration**

Write:

```ini
registry=https://registry.npmmirror.com
```

- [ ] **Step 4: Track the npm lockfile**

In `.gitignore`, remove only:

```gitignore
package-lock.json
```

Keep:

```gitignore
node_modules
```

Do not copy the worktree's `yarn.lock.json` typo.

- [ ] **Step 5: Generate the lockfile without running install scripts**

Run:

```powershell
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
```

Expected: exit 0 and no `Unknown project config "hoist"` warnings.

- [ ] **Step 6: Rebuild the dependency tree deterministically**

Run:

```powershell
npm ci
```

Expected: exit 0; `node_modules/.bin` is recreated.

- [ ] **Step 7: Verify the dependency contract**

Run:

```powershell
npm ls --depth=0
Test-Path node_modules/.bin/cross-env.cmd
Test-Path node_modules/@vtj/cli/config/tsconfig.web.json
node -e "console.log(require('./node_modules/vite/package.json').version, require('./node_modules/@vtj/cli/package.json').version, require('./node_modules/ws/package.json').version)"
```

Expected:

- `npm ls` has no `UNMET DEPENDENCY`, `invalid`, or `extraneous` entries;
- both `Test-Path` commands return `True`;
- version line is `6.3.7 0.12.19 8.20.1`.

- [ ] **Step 8: Commit the dependency contract**

```powershell
git add package.json package-lock.json .npmrc .gitignore
git commit -m "build: 固定前端依赖并跟踪 package-lock"
```

---

### Task 2: Add the failing WebSocket/Vite resilience regression harness

**Files:**
- Create: `scripts/verify-vite-resilience.mjs`
- Test: `scripts/verify-vite-resilience.mjs`

- [ ] **Step 1: Create the deterministic integration harness**

Write:

```js
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import net from 'node:net';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocket, WebSocketServer } from 'ws';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const children = new Set();
let backendHttpServer;
let backendWss;

function trackChild(child) {
  children.add(child);
  child.once('exit', () => children.delete(child));
  return child;
}

function killChildren() {
  for (const child of children) {
    if (child.exitCode === null) child.kill();
  }
}

async function freePort() {
  const server = net.createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  const port = typeof address === 'object' && address ? address.port : 0;
  await new Promise((resolveClose) => server.close(resolveClose));
  assert.ok(port > 0, 'failed to allocate a free port');
  return port;
}

async function waitForHttp(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return response;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error(`timeout waiting for ${url}: ${lastError?.message || 'unknown error'}`);
}

function startVite(port, backendOrigin, label) {
  const child = trackChild(
    spawn(
      process.execPath,
      ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(port)],
      {
        cwd: root,
        env: {
          ...process.env,
          BROWSER: 'none',
          NO_COLOR: '1',
          DEV_BACKEND_ORIGIN: backendOrigin,
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    )
  );

  child.output = '';
  child.stdout.on('data', (chunk) => {
    child.output += chunk.toString();
  });
  child.stderr.on('data', (chunk) => {
    child.output += chunk.toString();
  });
  child.label = label;
  return child;
}

function waitForExit(child, timeoutMs = 20_000) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve({ code: child.exitCode, signal: child.signalCode });
  }

  return new Promise((resolveExit, rejectExit) => {
    const timer = setTimeout(() => {
      child.kill();
      rejectExit(new Error(`${child.label} did not exit within ${timeoutMs}ms`));
    }, timeoutMs);

    child.once('exit', (code, signal) => {
      clearTimeout(timer);
      resolveExit({ code, signal });
    });
  });
}

function openWebSocket(url, timeoutMs = 4_000) {
  return new Promise((resolveOpen, rejectOpen) => {
    const socket = new WebSocket(url);
    const timer = setTimeout(() => {
      socket.terminate();
      rejectOpen(new Error(`WebSocket did not open: ${url}`));
    }, timeoutMs);

    socket.once('open', () => {
      clearTimeout(timer);
      resolveOpen(socket);
    });

    socket.once('error', (error) => {
      clearTimeout(timer);
      rejectOpen(error);
    });
  });
}

function resetWebSocket(socket) {
  return new Promise((resolveClose) => {
    socket.once('close', () => resolveClose());
    const rawSocket = socket._socket;
    if (rawSocket && typeof rawSocket.resetAndDestroy === 'function') {
      rawSocket.resetAndDestroy();
    } else {
      socket.terminate();
    }
  });
}

async function startBackend(port) {
  backendHttpServer = createServer((request, response) => {
    if (request.url === '/api/health') {
      response.writeHead(200, { 'Content-Type': 'application/json' });
      response.end('{"status":"ok"}');
      return;
    }
    response.writeHead(404, { 'Content-Type': 'application/json' });
    response.end('{"detail":"not found"}');
  });

  backendWss = new WebSocketServer({ server: backendHttpServer });
  backendWss.on('connection', (socket) => {
    socket.send(JSON.stringify({ type: 'connected' }));
    socket.on('message', (raw) => {
      const message = JSON.parse(raw.toString());
      if (message.type === 'heartbeat') {
        socket.send(JSON.stringify({ type: 'heartbeat' }));
      }
    });
  });

  backendHttpServer.listen(port, '127.0.0.1');
  await once(backendHttpServer, 'listening');
}

async function stopBackend() {
  if (!backendWss || !backendHttpServer) return;
  for (const client of backendWss.clients) client.terminate();
  await new Promise((resolveWss) => backendWss.close(resolveWss));
  await new Promise((resolveHttp) => backendHttpServer.close(resolveHttp));
  backendWss = undefined;
  backendHttpServer = undefined;
}

async function main() {
  const backendPort = await freePort();
  const vitePort = await freePort();
  const backendOrigin = `http://127.0.0.1:${backendPort}`;

  await startBackend(backendPort);

  const vite = startVite(vitePort, backendOrigin, 'primary-vite');
  const baseUrl = `http://127.0.0.1:${vitePort}`;

  try {
    await waitForHttp(`${baseUrl}/`);

    for (let index = 0; index < 50; index += 1) {
      const socket = await openWebSocket(
        `ws://127.0.0.1:${vitePort}/ws/connect?token=integration-test`
      );
      await resetWebSocket(socket);
      const response = await fetch(`${baseUrl}/`);
      assert.equal(response.status, 200, `Vite died after reset ${index + 1}`);
    }

    assert.equal(
      vite.exitCode,
      null,
      `primary Vite exited early:\n${vite.output}`
    );

    const secondVite = startVite(vitePort, backendOrigin, 'strict-port-collision');
    const secondResult = await waitForExit(secondVite);
    assert.notEqual(
      secondResult.code,
      0,
      `second Vite unexpectedly succeeded on occupied port:\n${secondVite.output}`
    );
    assert.match(
      secondVite.output,
      /already in use|Port .* in use/i,
      'strictPort failure did not explain the occupied port'
    );

    await stopBackend();
    const outageResponse = await fetch(`${baseUrl}/api/health`);
    assert.ok(
      outageResponse.status === 502 ||
        outageResponse.status === 503 ||
        outageResponse.status === 504,
      `expected 502/503/504 after backend outage, got ${outageResponse.status}`
    );

    const liveness = await fetch(`${baseUrl}/`);
    assert.equal(liveness.status, 200, 'Vite must survive backend outage');
    assert.equal(vite.exitCode, null, 'primary Vite must still be running');

    console.log('PASS vite resilience: ws proxy, 50 resets, strictPort, backend outage');
  } finally {
    await stopBackend();
    killChildren();
    await new Promise((resolveWait) => setTimeout(resolveWait, 500));
  }
}

main().catch((error) => {
  console.error('FAIL vite resilience:', error);
  process.exitCode = 1;
});
```

- [ ] **Step 2: Run the harness and verify the current code goes red**

Run:

```powershell
npm run test:vite-resilience
```

Expected before the proxy fix:

```text
FAIL vite resilience: Error: WebSocket did not open: ws://127.0.0.1:<port>/ws/connect?token=integration-test
```

Exit code must be non-zero.

- [ ] **Step 3: Commit the red regression harness**

```powershell
git add scripts/verify-vite-resilience.mjs
git commit -m "test: 添加 Vite WebSocket 稳定性回归测试"
```

---

### Task 3: Add the real `/ws` proxy route and safe proxy error handling

**Files:**
- Modify: `proxy.config.ts`
- Test: `scripts/verify-vite-resilience.mjs`

- [ ] **Step 1: Replace `proxy.config.ts` with the validated proxy contract**

Write:

```ts
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
        response.end(JSON.stringify({
          detail: '后端服务暂不可用，请稍后重试',
          code: 'BACKEND_UNAVAILABLE',
        }));
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
```

- [ ] **Step 2: Run the regression harness**

Run:

```powershell
npm run test:vite-resilience
```

Expected at this stage:

- WebSocket handshake and 50 reset checks pass;
- the run fails at strict-port collision because `vite.config.ts` has not yet enabled `strictPort`.

- [ ] **Step 3: Verify no token is printed**

Run the harness and inspect output:

```powershell
npm run test:vite-resilience 2>&1 | Select-String "token="
```

Expected: no match.

- [ ] **Step 4: Commit the proxy fix**

```powershell
git add proxy.config.ts
git commit -m "fix: 补全 /ws 代理与安全错误处理"
```

---

### Task 4: Enforce port 9527 and add the dev-only socket boundary

**Files:**
- Modify: `vite.config.ts`
- Test: `scripts/verify-vite-resilience.mjs`

- [ ] **Step 1: Replace `vite.config.ts` with the workspace-safe configuration**

Write:

```ts
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
            const key = `${route}:${code}`;
            const now = Date.now();

            if (now - (lastLogAt.get(key) || 0) > 10_000) {
              console.warn(
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
        ignored: ['**/.worktrees/**'],
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
```

- [ ] **Step 2: Run the resilience harness and verify green**

Run:

```powershell
npm run test:vite-resilience
```

Expected:

```text
PASS vite resilience: ws proxy, 50 resets, strictPort, backend outage
```

Exit code 0.

- [ ] **Step 3: Verify the resolved Vite configuration**

Run:

```powershell
node node_modules/vite/bin/vite.js --debug --host 127.0.0.1 --port 19527
```

Inspect resolved config and confirm:

- root is `D:/砺安题库/砺安题库`;
- port is 9527 unless CLI override is used;
- `strictPort: true`;
- `cors: false`;
- `hmr.clientPort: 9527`;
- `fs.deny` includes `**/.worktrees/**`;
- VTJ analytics plugin is absent because `hm: ''`.

Stop the process after inspection.

- [ ] **Step 4: Commit the Vite configuration**

```powershell
git add vite.config.ts
git commit -m "fix: 固定 9527 并加固 Vite 开发服务器"
```

---

### Task 5: Apply the mobile WebSocket CSP and run static verification

**Files:**
- Modify: `index.html`
- Test: `scripts/verify-vite-resilience.mjs`

- [ ] **Step 1: Update the CSP `connect-src` directive**

Change the existing meta tag to:

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' ws: wss:; img-src 'self' data:; style-src 'self' 'unsafe-inline';" />
```

Do not change the VTJ page templates or any `.vtj` DSL file.

- [ ] **Step 2: Re-run the resilience harness**

```powershell
npm run test:vite-resilience
```

Expected: PASS.

- [ ] **Step 3: Run TypeScript validation**

```powershell
npm run typecheck
```

Expected: exit 0. If unrelated pre-existing errors appear, capture the exact output and stop rather than expanding P0 scope.

- [ ] **Step 4: Run the production build**

```powershell
npm run build
```

Expected: exit 0 with the VTJ/Vite build completing.

- [ ] **Step 5: Confirm the working tree scope**

```powershell
git status --short
git diff --check
```

Expected: only `index.html` is uncommitted; no `.vtj`, backend, or page changes.

- [ ] **Step 6: Commit the CSP fix**

```powershell
git add index.html
git commit -m "fix: 兼容移动端同源 WebSocket CSP"
```

---

### Task 6: Perform real dev-server and Playwright mobile QA

**Files:**
- No source changes expected
- Update after success: `solve_problems_files/Vite代理添加错误处理方案.md`

- [ ] **Step 1: Verify the real backend**

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health
```

Expected: HTTP 200.

- [ ] **Step 2: Start the real Vite dev server**

```powershell
npm run dev
```

Expected:

- `Local: http://<lan-ip>:9527/`;
- no `cross-env` error;
- no `tsconfig.web.json` ENOENT;
- no silent switch to 9528;
- startup log identifies `D:/砺安题库/砺安题库`.

- [ ] **Step 3: Verify the port owner**

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 9527
Get-CimInstance Win32_Process -Filter "ProcessId = <PID>"
```

Expected: the owning process command line points to the main workspace, not `.worktrees`.

- [ ] **Step 4: Run Playwright mobile QA**

Use viewport `390×844` and open:

```text
http://<LAN-IP>:9527/#/mobile/login
```

Verify:

- HMR connects;
- page loads;
- login succeeds with a user-provided test account;
- `/ws/connect?token=...` upgrades successfully;
- heartbeat receives a response;
- console has no CSP WebSocket error;
- terminal logs contain no JWT.

- [ ] **Step 5: Run connection-loss scenarios**

Perform at least 20 cycles of:

- lock/unlock the phone;
- background/foreground the browser;
- toggle Wi-Fi;
- briefly stop and restart the FastAPI backend.

After each cycle:

- Vite remains alive;
- the browser reconnects;
- the app recovers without a manual reload;
- no `Unhandled 'error' event` appears.

- [ ] **Step 6: Stop the dev server and all spawned test processes**

Confirm no Vite process remains on 9527 unless intentionally left running.

---

### Task 7: Record verification results and close the plan

**Files:**
- Modify: `solve_problems_files/Vite代理添加错误处理方案.md`

- [ ] **Step 1: Update the final checklist**

Mark only checks whose evidence exists. Replace the remaining unchecked items with the actual command output summary, including:

```text
npm ls --depth=0
npm run test:vite-resilience
npm run typecheck
npm run build
Playwright 390x844 LAN QA
```

- [ ] **Step 2: Record deviations**

If any test failed, record:

- exact command;
- exact failure;
- whether it is caused by this change;
- the corrective action or explicit scope decision.

- [ ] **Step 3: Commit the verification record**

```powershell
git add solve_problems_files/Vite代理添加错误处理方案.md
git commit -m "docs: 记录 Vite 稳定性验证结果"
```

- [ ] **Step 4: Final repository verification**

```powershell
git status --short --branch
git log --oneline -8
git diff 48de900..HEAD --stat
```

Expected:

- only the pre-existing untracked runtime/backup files remain;
- no `.vtj` or unrelated backend changes are present;
- the six focused commits are visible.

---

## Plan Self-Review

- **Spec coverage:** dependency repair, `/ws` proxy, 9527, workspace isolation, worktree selective port, VTJ analytics opt-out, CSP, socket boundary, red-green harness, static checks, Playwright QA, rollback — all mapped to tasks.
- **Placeholder scan:** no TBD/TODO/implement-later steps; every code-changing task contains concrete content and commands.
- **Type consistency:** `ProxyOptions`, `Plugin`, `DEV_BACKEND_ORIGIN`, `strictPort`, `hmr.clientPort`, `workspaceRoot`, and `createDevTools({ hm: '' })` are consistent across tasks.
- **Scope check:** one subsystem (local development connectivity), small enough for a single plan.
- **User constraint check:** main directory only, no worktree, no whole-branch merge, direct primary-agent execution.
