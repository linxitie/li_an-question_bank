/**
 * 管理员端 Excel 批量导入验收（真实登录态 + 桌面视口）：
 *   智能导入 → 选 .xlsx → 列映射预览 → 确认入库（下架态）
 * 用真实文件：备考资料/_测试文件/测试_行测_正常5张.xlsx
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_二轮验收');
const XLSX = resolve('..', '备考资料', '_测试文件', '测试_行测_正常5张.xlsx');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpJson(p) {
  return new Promise((ok, fail) => {
    http
      .get({ host: '127.0.0.1', port: PORT, path: p }, (res) => {
        let b = '';
        res.on('data', (c) => (b += c));
        res.on('end', () => {
          try {
            ok(JSON.parse(b));
          } catch (e) {
            fail(e);
          }
        });
      })
      .on('error', fail);
  });
}
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
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((ok, fail) => {
      this.p.set(id, { ok, fail });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (r?.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval');
    return r?.result?.value;
  }
  async waitFor(expr, timeoutMs = 20000) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      try {
        if (await this.eval(expr)) return true;
      } catch {}
      await sleep(250);
    }
    return false;
  }
  async shot(name) {
    const png = await this.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(png.data, 'base64'));
    console.log('  ✓', name);
  }
}

const results = [];
const check = (label, pass, extra = '') => {
  results.push({ label, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${label}${extra ? '  → ' + extra : ''}`);
};

async function main() {
  mkdirSync(OUT, { recursive: true });
  const tok = await (
    await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=cbrycc&password=cbrycc'
    })
  ).json();
  if (!tok.access_token) throw new Error('管理员登录失败');
  const state = {
    token: tok.access_token,
    refreshToken: tok.refresh_token || '',
    username: 'cbrycc',
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
  await cdp.send('DOM.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });

  await cdp.send('Page.navigate', { url: `${BASE}/#/` });
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(1500);
  await cdp.eval(
    `localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`
  );
  const lp = await cdp.eval(
    `(async () => { try { await window.__VTJ_AUTH__.login('cbrycc','cbrycc'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
  );
  check('管理员登录态注入', lp === 'ok', lp);

  await cdp.eval(`location.hash = '#/admin/materials'; true`);
  const okPage = await cdp.waitFor(`document.body.innerText.includes('智能导入')`, 25000);
  await sleep(900);
  const btn = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '智能导入');
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return { text: b.textContent.trim(), rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] };
  })()`);
  check('管理端存在「智能导入」按钮', okPage && !!btn, JSON.stringify(btn));
  await cdp.shot('07_管理端_资料管理_导入入口');

  await cdp.eval(
    `[...document.querySelectorAll('button')].find(x => x.textContent.trim() === '智能导入').click(); true`
  );
  const dlg = await cdp.waitFor(`!!document.querySelector('#impFile')`);
  await sleep(500);
  check('导入向导（① 上传）打开', dlg);
  await cdp.shot('08_管理端_导入向导_上传');

  // 真实文件写进 input[type=file]
  const doc = await cdp.send('DOM.getDocument', { depth: -1 });
  const node = await cdp.send('DOM.querySelector', {
    nodeId: doc.root.nodeId,
    selector: '#impFile'
  });
  if (!node.nodeId) throw new Error('未找到 #impFile');
  await cdp.send('DOM.setFileInputFiles', { nodeId: node.nodeId, files: [XLSX] });

  const previewed = await cdp.waitFor(
    `document.body.innerText.includes('共 5 行数据') || document.body.innerText.includes('选择列映射')`,
    60000
  );
  await sleep(700);
  const prev = await cdp.eval(`(() => ({
    rowsText: (document.querySelector('.sec-b')||{}).textContent || '',
    cards: document.querySelectorAll('.card-prev .cp').length,
    first: (document.querySelector('.card-prev .cp b')||{}).textContent || ''
  }))()`);
  console.log('解析预览', JSON.stringify(prev));
  check('Excel 解析出 5 行并可预览', previewed && prev.cards === 5, prev.rowsText + ' cards=' + prev.cards);
  await cdp.shot('09_管理端_导入向导_列映射预览');

  const before = await (await fetch(`${API}/api/materials/admin/list?page=1&page_size=1`, {
    headers: { Authorization: `Bearer ${state.token}` }
  })).json();

  await cdp.eval(
    `[...document.querySelectorAll('button')].find(x => x.textContent.includes('确认入库')).click(); true`
  );
  const imported = await cdp.waitFor(
    `!!document.querySelector('.ok-tip') || document.body.innerText.includes('已入库')`,
    60000
  );
  await sleep(1200);
  const tip = await cdp.eval(`(document.querySelector('.ok-tip')||{}).textContent || ''`);
  check('确认入库成功', imported, tip.trim().slice(0, 60));
  await cdp.shot('10_管理端_导入向导_入库结果');

  const after = await (await fetch(`${API}/api/materials/admin/list?page=1&page_size=50`, {
    headers: { Authorization: `Bearer ${state.token}` }
  })).json();
  console.log('库内资料数：', before.total, '→', after.total);
  check('库内新增 5 条（下架态待上架）', after.total - before.total === 5, `${before.total}→${after.total}`);

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
