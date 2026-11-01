/**
 * 需求(6) 终验图：真实登录态下截 徽章页 / 个人页徽章墙（SPA 内跳转，避免重新 boot 丢内存态）
 *
 * 关键修复：先登录注入 → 用 location.hash 做 SPA 跳转（不再 Page.navigate 重新加载），
 * 每次跳转后轮询等待目标选择器出现，再截图。
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222, BASE = 'http://localhost:9527', API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_徽章终验');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpJson(p) {
  return new Promise((ok, fail) => {
    http.get({ host: '127.0.0.1', port: PORT, path: p }, (res) => {
      let b = ''; res.on('data', (c) => (b += c));
      res.on('end', () => { try { ok(JSON.parse(b)); } catch (e) { fail(e); } });
    }).on('error', fail);
  });
}
class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.p = new Map();
    ws.on('message', (raw) => { const m = JSON.parse(raw.toString());
      if (m.id && this.p.has(m.id)) { const { ok, fail } = this.p.get(m.id); this.p.delete(m.id);
        m.error ? fail(new Error(JSON.stringify(m.error))) : ok(m.result); } }); }
  send(method, params = {}) { const id = ++this.id;
    return new Promise((ok, fail) => { this.p.set(id, { ok, fail }); this.ws.send(JSON.stringify({ id, method, params })); }); }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r?.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval');
    return r?.result?.value;
  }
  async waitFor(expr, timeoutMs = 12000) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      try { if (await this.eval(expr)) return true; } catch { }
      await sleep(250);
    }
    return false;
  }
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const tok = await (await fetch(`${API}/api/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'username=202516001&password=test123456' })).json();
  const state = { token: tok.access_token, refreshToken: tok.refresh_token || '',
    username: '202516001', loginTime: Date.now() };

  const targets = await httpJson('/json');
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((ok, fail) => { ws.once('open', ok); ws.once('error', fail); });
  const cdp = new Cdp(ws);
  await cdp.send('Page.enable'); await cdp.send('Runtime.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });

  // 1) 加载一次应用，注入登录态并同步内存
  await cdp.send('Page.navigate', { url: `${BASE}/#/` });
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(1200);
  await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
  const lp = await cdp.eval(`(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`);
  console.log('provider.login =', lp);

  const shoot = async (name) => {
    const png = await cdp.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(png.data, 'base64'));
    console.log('  ✓', name);
  };

  // 2) 徽章页（SPA 跳转 + 等卡片渲染）
  await cdp.eval(`location.hash = '#/badges'; true`);
  const okBadge = await cdp.waitFor(`document.querySelectorAll('.bg-card').length > 0`, 15000);
  await sleep(800);
  const stat = await cdp.eval(`(() => ({ cards: document.querySelectorAll('.bg-card').length,
      chips: document.querySelectorAll('.bd-chip').length,
      coins: (document.querySelector('.bd-coins-num')||{}).textContent || null }))()`);
  console.log('徽章页:', okBadge, JSON.stringify(stat));
  await shoot('徽章页_全量');

  // 3) 个人页徽章墙（滚到底）
  await cdp.eval(`location.hash = '#/profile'; true`);
  const okWall = await cdp.waitFor(`document.querySelectorAll('.bw-item').length > 0`, 15000);
  await cdp.eval(`window.scrollTo(0, document.body.scrollHeight); true`);
  await sleep(900);
  const wall = await cdp.eval(`(() => ({ items: document.querySelectorAll('.bw-item').length,
      overflow: document.documentElement.scrollWidth > window.innerWidth + 1 }))()`);
  console.log('个人页徽章墙:', okWall, JSON.stringify(wall));
  await shoot('个人页_徽章墙');

  ws.close();
  const good = okBadge && okWall && stat.cards > 0 && wall.items > 0;
  console.log('\n结论:', good ? 'PASS' : 'FAIL');
  if (!good) process.exit(1);
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
