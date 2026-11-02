/**
 * P4 残余验收：字号三档 + 性能数据（登录态下真跑）
 *
 * 用法：node scripts/verify/p4_acceptance.mjs [--port 9222] [--base http://localhost:9527]
 * 输出：docs/plans/assets/备考资料_P4验收/ 下三张字号截图 + 终端打印性能指标
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const args = process.argv.slice(2);
const getArg = (n, d) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const PORT = Number(getArg('--port', '9222'));
const BASE = getArg('--base', 'http://localhost:9527');
const USER = getArg('--user', '202516001');
const PASS = getArg('--pass', 'test123456');
const OUT = resolve(getArg('--out', 'docs/plans/assets/备考资料_P4验收'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpJson(path) {
  return new Promise((ok, fail) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => {
      let b = ''; res.on('data', (c) => (b += c));
      res.on('end', () => { try { ok(JSON.parse(b)); } catch (e) { fail(e); } });
    }).on('error', fail);
  });
}

class Cdp {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.on('message', (raw) => {
      const m = JSON.parse(raw.toString());
      if (m.id && this.pending.has(m.id)) {
        const { ok, fail } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? fail(new Error(JSON.stringify(m.error))) : ok(m.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((ok, fail) => { this.pending.set(id, { ok, fail }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r?.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r?.result?.value;
  }
}

async function main() {
  const targets = await httpJson('/json');
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((ok, fail) => { ws.once('open', ok); ws.once('error', fail); });
  const cdp = new Cdp(ws);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  mkdirSync(OUT, { recursive: true });

  // 登录（API + provider.login）
  const resp = await fetch('http://127.0.0.1:8000/api/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${encodeURIComponent(USER)}&password=${encodeURIComponent(PASS)}`,
  });
  const tok = await resp.json();
  const state = { token: tok.access_token, refreshToken: tok.refresh_token || '', username: USER, loginTime: Date.now() };

  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  await cdp.send('Page.navigate', { url: `${BASE}/#/login` });
  await sleep(1500);
  await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
  const lp = await cdp.eval(`(async () => { try {
      await window.__VTJ_AUTH__.login(${JSON.stringify(USER)}, ${JSON.stringify(PASS)}); return 'ok';
    } catch (e) { return 'err:' + e.message } })()`);
  console.log('provider.login =', lp);

  // ===== 1) 字号三档 =====
  await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
  await cdp.send('Page.navigate', { url: `${BASE}/#/mobile/materials` }); await sleep(3000);

  const readable = await cdp.eval(`(() => {
    const t = document.querySelector('.card-text');
    const s = document.querySelector('.stack');
    return { hasCard: !!t, hasStack: !!s, hash: location.hash,
             font: t ? getComputedStyle(t).fontSize : null,
             scaleVar: s ? getComputedStyle(s).getPropertyValue('--sm-font-scale').trim() : null };
  })()`);
  console.log('卡片渲染:', JSON.stringify(readable));

  const tiers = [];
  for (const [label, btnText] of [['A-', 'A-'], ['A', 'A'], ['A+', 'A+']]) {
    const clicked = await cdp.eval(`(() => {
      const b = Array.from(document.querySelectorAll('.font-row button'))
        .find(x => (x.textContent || '').trim() === ${JSON.stringify(btnText)});
      if (!b) return false; b.click(); return true;
    })()`);
    await sleep(450);
    const m = await cdp.eval(`(() => {
      const t = document.querySelector('.card-text');
      const s = document.querySelector('.stack');
      return { font: parseFloat(getComputedStyle(t).fontSize),
               scale: parseFloat(getComputedStyle(s).getPropertyValue('--sm-font-scale')) };
    })()`);
    tiers.push({ label, clicked, ...m });
    const png = await cdp.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`${OUT}/字号_${label.replace('+', 'plus').replace('-', 'minus')}.png`,
      Buffer.from(png.data, 'base64'));
    console.log(`  字号 ${label}: clicked=${clicked} font=${m.font}px scale=${m.scale}`);
  }
  const ratioOk = tiers[0].font < tiers[1].font && tiers[1].font < tiers[2].font;

  // ===== 2) 性能：首屏 + 资源 + 动画帧率 =====
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
  await cdp.send('Page.navigate', { url: `${BASE}/#/materials/xingce` }); await sleep(3800);

  const perf = await cdp.eval(`(() => {
    const nav = performance.getEntriesByType('navigation')[0] || {};
    const paints = performance.getEntriesByType('paint').map(p => ({ name: p.name, t: Math.round(p.startTime) }));
    const res = performance.getEntriesByType('resource')
      .filter(r => r.name.includes('/api/materials'))
      .map(r => ({ url: r.name.split('/api')[1], ms: Math.round(r.duration), size: r.transferSize }));
    return {
      domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
      loadEvent: Math.round(nav.loadEventEnd || 0),
      paints,
      api: res.slice(0, 4),
    };
  })()`);
  console.log('性能：', JSON.stringify(perf));

  // 动画帧率：点「下一张」再采样 800ms
  const fps = await cdp.eval(`(async () => {
    const next = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').includes('下一张'));
    if (next) next.click();
    return await new Promise((res) => {
      let n = 0, t0 = performance.now(), last = t0, maxGap = 0;
      function loop(t) {
        n++; const gap = t - last; if (gap > maxGap) maxGap = gap; last = t;
        if (t - t0 < 800) requestAnimationFrame(loop);
        else res({ frames: n, fps: Math.round((n * 1000) / (t - t0)), maxGapMs: Math.round(maxGap) });
      }
      requestAnimationFrame(loop);
    });
  })()`);
  console.log('翻页动画采样：', JSON.stringify(fps));

  const png = await cdp.send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(`${OUT}/PC_资料页_性能参考.png`, Buffer.from(png.data, 'base64'));

  const fcp = (perf.paints.find(p => p.name === 'first-contentful-paint') || {}).t;
  const checks = [
    ['字号三档递增（A- < A < A+）', ratioOk],
    ['A- 约为基准 0.9 倍', Math.abs((tiers[0].font / tiers[1].font) - 0.9) < 0.05],
    ['A+ 约为基准 1.15 倍', Math.abs((tiers[2].font / tiers[1].font) - 1.15) < 0.06],
    ['首屏 FCP ≤ 2000ms', typeof fcp === 'number' && fcp <= 2000],
    ['资料接口返回 ≤ 800ms', (perf.api[0]?.ms ?? 9999) <= 800],
    ['翻页动画 ≥ 50fps', fps.fps >= 50],
  ];
  console.log('\\n=== 断言 ===');
  let ok = true;
  for (const [name, pass] of checks) {
    console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name}`);
    ok = ok && pass;
  }
  writeFileSync(`${OUT}/_report.json`, JSON.stringify({ tiers, perf, fps, checks }, null, 2));
  ws.close();
  process.exit(ok ? 0 : 1);
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
