/**
 * 真实登录态截图：通用技巧卡（临时把 20 张待审卡置为已上线，截完 try/finally 还原）
 *
 * 用法：node scripts/verify/generic_card_shots.mjs
 */
import http from 'node:http';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8000';
const OUT = resolve('docs/plans/assets/备考资料_通用技巧卡');
const DB = 'backend/data/question_bank.db';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const sql = (q) => execFileSync('python', ['-c',
  `import sqlite3,sys;c=sqlite3.connect(r'${DB}');print(c.execute("""${q}""").fetchall());c.commit();c.close()`],
  { encoding: 'utf8' }).trim();

function httpJson(path) {
  return new Promise((ok, fail) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => {
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
  async eval(expression) { const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r?.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval error');
    return r?.result?.value; }
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const raw = sql(
    "select group_concat(material_id) from study_material where type='card' and status=0 and point_id is null");
  // python 会把结果打成 [('108,109,...')]，这里直接抓数字，避免解析 Python repr
  const list = (raw.match(/\d+/g) || []);
  console.log('待审通用技巧卡:', list.length, '张');
  if (!list.length) throw new Error('没有待审的通用技巧卡可截');

  const inSql = list.join(',');
  let restored = false;
  const restore = () => {
    if (restored) return;
    sql(`update study_material set status=0 where material_id in (${inSql})`);
    const left = sql(`select count(*) from study_material where material_id in (${inSql}) and status=1`);
    console.log('已还原待审，仍为上线的条数 =', left[0][0]);
    restored = true;
  };

  try {
    sql(`update study_material set status=1 where material_id in (${inSql})`);
    console.log('临时上线:', sql(`select count(*) from study_material where material_id in (${inSql}) and status=1`)[0][0]);

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

    // 手机端：资料卡列表
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 900, deviceScaleFactor: 3, mobile: true });
    await cdp.send('Page.navigate', { url: `${BASE}/#/login` }); await sleep(1500);
    await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
    await cdp.eval(`(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); } catch(e){} })()`);
    await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
    await cdp.send('Page.navigate', { url: `${BASE}/#/mobile/materials` }); await sleep(3200);
    const found = await cdp.eval(`(() => {
      const els = Array.from(document.querySelectorAll('.tag-generic'));
      if (els.length) els[0].scrollIntoView({ block: 'center' });
      return { chips: els.length, hash: location.hash };
    })()`);
    console.log('手机端通用技巧标数量:', JSON.stringify(found));
    await sleep(500);
    let png = await cdp.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`${OUT}/真机_手机列表_通用技巧.png`, Buffer.from(png.data, 'base64'));

    // PC 详情：打开第一张通用技巧卡
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    const first = list[0];
    await cdp.send('Page.navigate', { url: 'about:blank' }); await sleep(200);
    await cdp.send('Page.navigate', { url: `${BASE}/#/materials/detail?subject=xingce&id=${first}` });
    await sleep(2600);
    const chip = await cdp.eval(`document.querySelectorAll('.md-chip-generic').length`);
    console.log('PC 详情通用技巧 chip 数量:', chip);
    png = await cdp.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`${OUT}/真机_PC详情_通用技巧.png`, Buffer.from(png.data, 'base64'));
    ws.close();
  } finally {
    restore();
  }
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
