/**
 * 真实登录态截图（D3 能力 + 本轮三项修复的验证）
 *
 * 用法：node scripts/verify/auth_login_shots.mjs [--port 9222] [--base http://localhost:9527]
 * 前置：headless Chrome 带 --remote-debugging-port 启动；前后端在跑。
 *
 * 做的事：真登录（填账号密码点登录）→ 截 我的徽章 / 个人页徽章墙 / 手机端资料卡（并翻一张）
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const args = process.argv.slice(2);
const getArg = (n, d) => {
  const i = args.indexOf(n);
  return i >= 0 && args[i + 1] ? args[i + 1] : d;
};
const PORT = Number(getArg('--port', '9222'));
const BASE = getArg('--base', 'http://localhost:9527');
const USER = getArg('--user', '202516001');
const PASS = getArg('--pass', 'test123456');
const OUT = resolve(getArg('--out', 'docs/plans/assets/备考资料_登录态截图'));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpJson(path) {
  return new Promise((ok, fail) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
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
    return new Promise((ok, fail) => {
      this.pending.set(id, { ok, fail });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r?.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + (r.exceptionDetails.exception?.description || ''));
    return r?.result?.value;
  }
}

const FILL = (user, pass) => `(() => {
  const setVal = (el, v) => {
    const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
    d.set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const ins = Array.from(document.querySelectorAll('input')).filter(i => i.type !== 'hidden');
  if (ins.length < 2) return 'inputs:' + ins.length;
  setVal(ins[0], ${JSON.stringify(user)});
  setVal(ins[1], ${JSON.stringify(pass)});
  // 登录页有「同意协议」勾选框，不勾可能阻断登录
  const boxes = Array.from(document.querySelectorAll('input[type=checkbox]'));
  boxes.forEach((b) => {
    if (!b.checked) {
      b.click();
      if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change', { bubbles: true })); }
    }
  });
  const btn = Array.from(document.querySelectorAll('button, .el-button, [role=button]'))
    .find(b => (b.textContent || '').replace(/\\s/g, '').includes('登录'));
  if (!btn) return 'no-button';
  if (btn.disabled) return 'button-disabled';
  btn.click();
  return 'clicked(' + boxes.length + 'box)';
})()`;

async function main() {
  const targets = await httpJson('/json');
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((ok, fail) => { ws.once('open', ok); ws.once('error', fail); });
  const cdp = new Cdp(ws);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  mkdirSync(OUT, { recursive: true });

  // 1) 登录
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Page.navigate', { url: `${BASE}/#/login` });
  await sleep(2500);
  const r1 = await cdp.eval(FILL(USER, PASS));
  await sleep(3000);
  const after = await cdp.eval('location.hash');
  const logged = !String(after).includes('login');
  console.log(`登录：${r1} → hash=${after} → ${logged ? 'OK' : 'FAIL'}`);

  const shots = [];
  const shoot = async (name) => {
    const png = await cdp.send('Page.captureScreenshot', { format: 'png' });
    const f = `${OUT}/${name}.png`;
    writeFileSync(f, Buffer.from(png.data, 'base64'));
    shots.push(f);
    console.log('  ✓', name);
  };

  // 2) 徽章页（筛「未获得 + 青铜」验证筛选修复 + 点一张卡开弹层）
  await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
  await cdp.send('Page.navigate', { url: `${BASE}/#/badges` }); await sleep(2500);
  const filterInfo = await cdp.eval(`(() => {
    const chips = Array.from(document.querySelectorAll('.bd-chip'));
    const unowned = chips.find(c => (c.textContent||'').trim() === '未获得');
    const bronze = chips.find(c => (c.textContent||'').trim() === '青铜');
    unowned && unowned.click();
    bronze && bronze.click();
    return { chips: chips.length, hitUnowned: !!unowned, hitBronze: !!bronze };
  })()`);
  await sleep(900);
  const cardCount = await cdp.eval(`document.querySelectorAll('.bg-card').length`);
  const tiers = await cdp.eval(
    `Array.from(document.querySelectorAll('.bg-card .bg-meta')).slice(0,6).map(e=>e.textContent.trim())`);
  console.log(`筛选：chips=${filterInfo.chips} 未获得=${filterInfo.hitUnowned} 青铜=${filterInfo.hitBronze}` +
    ` → 卡片 ${cardCount} 张；前几张 ${JSON.stringify(tiers)}`);
  await shoot('徽章页_筛选未获得青铜');

  // 3) 个人页徽章墙（滚到底）
  await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
  await cdp.send('Page.navigate', { url: `${BASE}/#/profile` }); await sleep(2500);
  await cdp.eval('window.scrollTo(0, document.body.scrollHeight); true');
  await sleep(900);
  const wall = await cdp.eval(`(() => {
    const el = document.querySelector('.badge-wall-card');
    return { exists: !!el, count: document.querySelectorAll('.bw-item').length,
             overflow: document.documentElement.scrollWidth > window.innerWidth + 1 };
  })()`);
  console.log('个人页徽章墙:', JSON.stringify(wall));
  await shoot('个人页_徽章墙');

  // 4) 手机端资料卡（翻一张，验证主题与翻页动效）
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
  await cdp.send('Page.navigate', { url: `${BASE}/#/mobile/materials` }); await sleep(3000);
  const top = await cdp.eval(`(() => {
    const tabs = document.querySelector('.tabs');
    const card = document.querySelector('.stack-card.lv0');
    if (!tabs || !card) return { ok: false };
    const t = tabs.getBoundingClientRect(), c = card.getBoundingClientRect();
    return { ok: true, overlap: c.top < t.bottom - 1, tabBottom: Math.round(t.bottom), cardTop: Math.round(c.top),
             overflow: document.documentElement.scrollWidth > window.innerWidth + 1 };
  })()`);
  console.log('手机端卡片与科目栏:', JSON.stringify(top));
  await shoot('手机_资料卡_修后');

  const next = await cdp.eval(`(() => {
    const b = Array.from(document.querySelectorAll('.stack-bar button')).find(x => x.textContent.includes('下一张'));
    if (!b) return false; b.click(); return true;
  })()`);
  await sleep(600);
  await shoot('手机_资料卡_翻页后');
  console.log('翻页点击:', next);

  const bad = top.ok && (top.overlap || top.overflow);
  console.log(`\n结论：卡片遮挡科目栏=${top.overlap} 横向溢出=${top.overflow} → ${bad ? 'FAIL' : 'PASS'}`);
  ws.close();
  if (!logged || bad) process.exit(1);
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
