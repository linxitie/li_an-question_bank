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
  child.label = label;
  child.stdout.on('data', (chunk) => {
    child.output += chunk.toString();
  });
  child.stderr.on('data', (chunk) => {
    child.output += chunk.toString();
  });
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
