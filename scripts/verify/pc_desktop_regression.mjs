/**
 * PC 端登录/资料页回归（电脑界面不能被跳到平板/手机版）
 *
 * 背景：2026-11-02 曾把 `/materials`、`/badges` 加进 `DEVICE_ROUTE_MAP`，
 * 触屏笔记本（宽 768~1024 + 有触摸）会被 detectDevice() 判成 tablet，
 * 于是打开 `/materials` 直接被改道到 `/tablet/materials`（手机版界面）。
 * 按 R4「device.ts 原样保留」已回滚，本脚本就是这条回归的守卫。
 *
 * 依赖：前端 9527、后端 8000、Chrome 9222（脚本会把视口设成 1440×900 桌面）
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8000';
const OUT = resolve('docs/plans/assets/备考资料_平板端验收');
const DESKTOP_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const results = [];
const check = (label, pass, extra = '') => {
  results.push({ label, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${label}${extra ? '  → ' + extra : ''}`);
};

const httpJson = (p) =>
  new Promise((ok, fail) => {
    http.get({ host: '127.0.0.1', port: PORT, path: p }, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
      res.on('end', () => ok(JSON.parse(b)));
    }).on('error', fail);
  });

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.p = new Map();
    ws.on('message', (raw) => {
      const m = JSON.parse(raw.toString());
      if (m.id && this.p.has(m.id)) {
        const { ok, fail } = this.p.get(m.id);
        this.p.delete(m.id);
        m.error ? fail(new Error(JSON.stringify(m.error))) : ok(m.result);
      }
    });
  }
  send(method, params = {}, timeoutMs = 30000) {
    const id = ++this.id;
    return new Promise((ok, fail) => {
      const t = setTimeout(() => {
        this.p.delete(id);
        fail(new Error('CDP TIMEOUT ' + method));
      }, timeoutMs);
      this.p.set(id, {
        ok: (v) => {
          clearTimeout(t);
          ok(v);
        },
        fail: (e) => {
          clearTimeout(t);
          fail(e);
        }
      });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r?.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval');
    return r?.result?.value;
  }
  async waitFor(expr, timeoutMs = 20000) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      try {
        if (await this.eval(expr)) return true;
      } catch {}
      await sleep(200);
    }
    return false;
  }
  async shot(name) {
    await this.send('Page.bringToFront', {}, 8000).catch(() => {});
    let data = null;
    try {
      data = (await this.send('Page.captureScreenshot', { format: 'png' }, 20000)).data;
    } catch {
      data = (await this.send('Page.captureScreenshot', { format: 'png', fromSurface: false }, 20000)).data;
    }
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, 'base64'));
    console.log('  ✓', name);
  }
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const stu = await (
    await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=202516001&password=test123456'
    })
  ).json();
  const state = {
    token: stu.access_token,
    refreshToken: stu.refresh_token || '',
    username: '202516001',
    loginTime: Date.now()
  };

  const targets = await httpJson('/json');
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((ok, fail) => {
    ws.once('open', ok);
    ws.once('error', fail);
  });
  const cdp = new Cdp(ws);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  // 桌面视口：1440×900、DPR 1、非 mobile、无触摸、Windows Chrome UA
  await cdp.send('Emulation.clearDeviceMetricsOverride').catch(() => {});
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: false }).catch(() => {});
  await cdp.send('Emulation.setUserAgentOverride', { userAgent: DESKTOP_UA }).catch(() => {});
  await cdp.send('Page.bringToFront', {}, 8000).catch(() => {});

  const desktop = await cdp.eval(`(() => ({ w: window.innerWidth, touch: navigator.maxTouchPoints, ua: navigator.userAgent.includes('Windows') }))()`);
  console.log('桌面视口', JSON.stringify(desktop));
  check('视口是桌面尺寸且无触摸', desktop.w === 1440 && desktop.touch === 0, JSON.stringify(desktop));

  // 登录页必须是 PC 版（不能是 tablet/mobile 登录页）
  await cdp.eval(`localStorage.clear(); location.hash = '#/login'; true`);
  await cdp.send('Page.reload', {}, 20000).catch(() => {});
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(2200);
  const loginInfo = await cdp.eval(`(() => ({
    hash: location.hash,
    text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 60),
    hasTabletLogin: !!document.querySelector('.tablet-login, [class*="tablet-login"]'),
    hasMobileLogin: !!document.querySelector('.mobile-login, [class*="mobile-login"]')
  }))()`);
  console.log('登录页', JSON.stringify(loginInfo));
  check('电脑打开的是 PC 登录页（未跳到 /tablet/login 或 /mobile/login）',
    !/\/(tablet|mobile)\/login/.test(loginInfo.hash) && !loginInfo.hasTabletLogin && !loginInfo.hasMobileLogin,
    loginInfo.hash);
  await cdp.shot('15_PC登录页_1440');

  // 登录后：首页 / 资料页都必须走 PC
  await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
  const lp = await cdp.eval(
    `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
  );
  check('学生登录态注入', lp === 'ok', lp);

  await cdp.eval(`location.hash = '#/home'; true`);
  await sleep(2000);
  const home = await cdp.eval(`(() => ({ hash: location.hash, cols: document.querySelectorAll('.main-content, .home-page, .dashboard').length }))()`);
  check('登录后落在 PC 首页', home.hash === '#/home', home.hash);
  await cdp.shot('16_PC首页_1440');

  await cdp.eval(`location.hash = '#/materials/shenlun'; true`);
  await sleep(2200);
  const pcMat = await cdp.eval(`(() => ({
    hash: location.hash,
    matPage: !!document.querySelector('.mat-page'),
    grid: document.querySelectorAll('.card-grid .flip').length
  }))()`);
  console.log('PC 资料页', JSON.stringify(pcMat));
  check('电脑打开 /materials/shenlun 仍是 PC 资料页',
    pcMat.hash === '#/materials/shenlun' && pcMat.matPage, JSON.stringify(pcMat));
  await cdp.shot('17_PC资料页_1440');

  // 关键回归：桌面访问 /materials 不能被改道到 /tablet/materials
  await cdp.eval(`location.hash = '#/materials'; true`);
  await sleep(2000);
  const matRoot = await cdp.eval(`(() => ({ hash: location.hash, stack: !!document.querySelector('.stack-card'), grid: !!document.querySelector('.t-grid') }))()`);
  console.log('PC /materials', JSON.stringify(matRoot));
  check('电脑打开 /materials 不会被改道到平板页',
    !matRoot.hash.includes('/tablet/') && !matRoot.hash.includes('/mobile/'),
    JSON.stringify(matRoot));

  // 2026-11-04：徽章展示模块下线 → 改为验证「/badges 已无徽章页，且不会被改道到平板/手机」
  await cdp.eval(`location.hash = '#/badges'; true`);
  await sleep(1800);
  const badges = await cdp.eval(`(() => ({ hash: location.hash, hasBadgesPage: !!document.querySelector('.badges-page'), hasMatPage: !!document.querySelector('.mat-page') }))()`);
  check('电脑打开 /badges 不会被改道到平板/手机页',
    !badges.hash.includes('/tablet/') && !badges.hash.includes('/mobile/'),
    JSON.stringify(badges));
  check('电脑打开 /badges 已无徽章页（模块已下线）', !badges.hasBadgesPage, JSON.stringify(badges));

  ws.close();
  const failed = results.filter((r) => !r.pass);
  console.log(`\n结论：${results.length - failed.length}/${results.length} 通过`);
  if (failed.length) {
    console.log('失败项：' + failed.map((f) => f.label).join('; '));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
