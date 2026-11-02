/**
 * 三轮验收补充（手机视口）：Excel 批量入口在手机端也可达
 *  1) 手机端「创建卡片」弹层底部新增「Excel 批量导入」入口
 *  2) 手机端打开 #/materials/upload?tab=excel 的布局不溢出
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_三轮验收');
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
  send(method, params = {}, timeoutMs = 30000) {
    const id = ++this.id;
    return new Promise((ok, fail) => {
      const timer = setTimeout(() => {
        this.p.delete(id);
        fail(new Error(`CDP TIMEOUT ${method}`));
      }, timeoutMs);
      this.p.set(id, {
        ok: (v) => {
          clearTimeout(timer);
          ok(v);
        },
        fail: (e) => {
          clearTimeout(timer);
          fail(e);
        }
      });
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
      await sleep(220);
    }
    return false;
  }
  async shot(name) {
    await this.send('Page.bringToFront', {}, 8000).catch(() => {});
    let data = null;
    try {
      data = (await this.send('Page.captureScreenshot', { format: 'png' }, 20000)).data;
    } catch {
      data = (
        await this.send('Page.captureScreenshot', { format: 'png', fromSurface: false }, 20000)
      ).data;
    }
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, 'base64'));
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
      body: 'username=202516001&password=test123456'
    })
  ).json();
  const state = {
    token: tok.access_token,
    refreshToken: tok.refresh_token || '',
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
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true
  });

  await cdp.send('Page.navigate', { url: `${BASE}/#/` });
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(1500);
  await cdp.eval(
    `localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`
  );
  const lp = await cdp.eval(
    `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
  );
  check('学生登录态注入', lp === 'ok', lp);

  // 手机端创建弹层 → 底部「Excel 批量导入」入口
  await cdp.eval(`location.hash = '#/mobile/materials'; true`);
  await cdp.waitFor(`!!document.querySelector('.create-btn')`);
  await sleep(700);
  await cdp.eval(`document.querySelector('.create-btn').click(); true`);
  await cdp.waitFor(`!!document.querySelector('.cc-subjects')`);
  await sleep(400);
  await cdp.eval(
    `[...document.querySelectorAll('.cc-subject')].find(x => x.textContent.includes('申论')).click(); true`
  );
  await cdp.waitFor(`!!document.querySelector('.cc-body')`);
  await sleep(600);
  const batchBtn = await cdp.eval(`(() => {
    const b = document.querySelector('.cc-batch');
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return { text: b.textContent.trim(), rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] };
  })()`);
  console.log('手机端批量入口', JSON.stringify(batchBtn));
  check('手机端弹层有 Excel 批量入口', !!batchBtn && batchBtn.text.includes('Excel'), batchBtn ? batchBtn.text : 'null');
  await cdp.shot('08_手机端_创建弹层_Excel入口');

  // 点进去 → Excel 面板（390px 布局）
  await cdp.eval(`document.querySelector('.cc-batch').click(); true`);
  const okExcel = await cdp.waitFor(
    `!!document.querySelector('.mc-excel') && getComputedStyle(document.querySelector('.mc-excel')).display !== 'none'`,
    20000
  );
  await sleep(700);
  const layout = await cdp.eval(`(() => ({
    inner: window.innerWidth,
    docW: document.documentElement.scrollWidth,
    tabOn: (document.querySelector('.mc-tab.is-on')||{}).textContent || '',
    hasDrop: !!document.querySelector('.mc-drop')
  }))()`);
  console.log('手机端 Excel 面板', JSON.stringify(layout));
  check('手机端可打开 Excel 面板', okExcel && layout.hasDrop && layout.tabOn.includes('Excel'));
  check('手机端无横向溢出', layout.docW <= layout.inner + 1, `${layout.docW} vs ${layout.inner}`);
  await cdp.shot('09_手机端_Excel导入');

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
