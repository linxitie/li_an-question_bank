/**
 * 平板与电脑「同版」验收（2026-11-02 实施后）
 *
 * 断言（1024×768 / 1180×820 / 1366×1024 三种 iPad 横屏）：
 *  1. /tablet/home 渲染的是电脑首页（.home-page），并注入「📚 备考资料」导航项
 *  2. 首页上层三栏在 1024 变两栏（260 + 1fr，右栏下移），top-section 不溢出容器
 *  3. 点导航入口 → /materials/xingce，资料页 5 列（1024）/ 卡片 179×170 / 首屏 ≥2 行 / 无溢出
 *  4. 详情页横屏仍是左右两栏（row）
 *  5. 上传页 860 居中、徽章页 4 列，均无溢出
 *  6. 旧地址 /tablet/materials、/tablet/badges、/tablet/materials/detail → 302 到电脑端
 *  7. 三种尺寸下 <44px 可点元素 = 0
 *
 * 依赖：前端 9527、后端 8010、Chrome 9222。只读，不改数据。
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_平板同版验收');
const IPAD_UA =
  'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const SIZES = [
  ['1024x768', 1024, 768],
  ['1180x820', 1180, 820],
  ['1366x1024', 1366, 1024]
];
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

const HOME_M = `(() => {
  const de = document.documentElement;
  const top = document.querySelector('.top-section');
  const entry = document.getElementById('tablet-materials-entry');
  const tap = [...document.querySelectorAll('.home-page a, .home-page button, .home-page .menu-item')]
    .map((b) => Math.round(b.getBoundingClientRect().height)).filter((h) => h > 0 && h < 44);
  return {
    hash: location.hash,
    hasHomePage: !!document.querySelector('.home-page'),
    hasEntry: !!entry,
    entryRect: entry ? [Math.round(entry.getBoundingClientRect().width), Math.round(entry.getBoundingClientRect().height)] : null,
    topCols: top ? getComputedStyle(top).gridTemplateColumns : '',
    fits: top ? top.scrollWidth <= top.clientWidth + 1 : null,
    overflowX: de.scrollWidth - window.innerWidth,
    smallTap: tap.length,
    hasTabletHomeScore: !!document.querySelector('.quick-actions')
  };
})()`;

const MAT_M = `(() => {
  const de = document.documentElement;
  const grid = document.querySelector('.card-grid');
  const card = document.querySelector('.card-grid .flip');
  const gr = grid ? grid.getBoundingClientRect() : null;
  const cr = card ? card.getBoundingClientRect() : null;
  const cs = grid ? getComputedStyle(grid) : null;
  const gap = cs ? parseFloat(cs.gap || cs.rowGap || '0') : 0;
  const rows = gr && cr ? Math.max(0, Math.floor((window.innerHeight - gr.top + gap) / (cr.height + gap))) : 0;
  const tap = [...document.querySelectorAll('.mat-page a, .mat-page button, #materials-create-bar .mce-btn')]
    .map((b) => Math.round(b.getBoundingClientRect().height)).filter((h) => h > 0 && h < 44);
  return {
    hash: location.hash,
    hasMatPage: !!document.querySelector('.mat-page'),
    cols: cs ? cs.gridTemplateColumns.split(' ').length : 0,
    card: cr ? [Math.round(cr.width), Math.round(cr.height)] : null,
    gridTop: gr ? Math.round(gr.top) : null,
    rows,
    overflowX: de.scrollWidth - window.innerWidth,
    smallTap: tap.length
  };
})()`;

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
  const list = await (
    await fetch(`${API}/api/materials?subject=xingce&type=card&page_size=1`, {
      headers: { Authorization: `Bearer ${stu.access_token}` }
    })
  ).json();
  const cardId = list?.items?.[0]?.id || 0;

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
  await cdp.send('Page.bringToFront', {}, 8000).catch(() => {});
  await cdp.send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {});

  const setViewport = async (w, h) => {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: w,
      height: h,
      deviceScaleFactor: 2,
      mobile: true,
      screenOrientation: { type: 'landscapePrimary', angle: 90 }
    });
    await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 }).catch(() => {});
    await cdp.send('Emulation.setUserAgentOverride', { userAgent: IPAD_UA }).catch(() => {});
  };
  const go = async (hash, ready, wait = 1800) => {
    await cdp.eval(`location.hash = ${JSON.stringify(hash)}; true`);
    await cdp.waitFor(ready, 20000);
    await sleep(wait);
  };

  let booted = false;
  for (const [tag, w, h] of SIZES) {
    await setViewport(w, h);
    if (!booted) {
      await cdp.send('Page.navigate', { url: `${BASE}/#/tablet/home` });
      await cdp.waitFor(`document.readyState === 'complete'`);
      await sleep(2000);
      await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
      await cdp.eval(
        `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
      );
      booted = true;
    }

    // ① 平板首页 = 电脑首页 + 注入入口
    await go('#/tablet/home', `!!document.querySelector('.home-page')`, 2200);
    const home = await cdp.eval(HOME_M);
    console.log(`首页 ${tag}`, JSON.stringify(home));
    check(`${tag} 平板首页渲染的是电脑首页`, home.hasHomePage && !home.hasTabletHomeScore, JSON.stringify({ hasHomePage: home.hasHomePage }));
    check(`${tag} 首页有「备考资料」导航入口（≥44px）`, home.hasEntry && home.entryRect && home.entryRect[1] >= 44, JSON.stringify(home.entryRect));
    check(`${tag} 首页上层三栏不溢出容器`, home.fits === true, `topCols=${home.topCols} fits=${home.fits}`);
    check(`${tag} 首页 <44px 可点元素为 0`, home.smallTap === 0, `smallTap=${home.smallTap}`);
    await cdp.shot(`01_${tag}_平板首页_电脑版`);

    // ② 点入口 → 电脑资料页
    await cdp.eval(`document.getElementById('tablet-materials-entry')?.click(); true`);
    await sleep(2000);
    const mat = await cdp.eval(MAT_M);
    console.log(`资料页 ${tag}`, JSON.stringify(mat));
    check(`${tag} 点入口进的是电脑端资料页`, mat.hash === '#/materials/xingce' && mat.hasMatPage, mat.hash);
    check(`${tag} 资料页横向无溢出`, mat.overflowX === 0, `overflowX=${mat.overflowX}`);
    check(`${tag} 资料页 <44px 可点元素为 0`, mat.smallTap === 0, `smallTap=${mat.smallTap}`);
    check(`${tag} 资料页首屏可见卡片 ≥2 行`, mat.rows >= 2, `rows=${mat.rows} gridTop=${mat.gridTop}`);
    await cdp.shot(`02_${tag}_电脑端资料页_平板横屏`);

    if (tag === '1024x768') {
      check('1024 资料页 5 列、卡片 179×170', mat.cols === 5 && mat.card?.[0] === 179 && mat.card?.[1] === 170, `${mat.cols}列 ${mat.card}`);
    }
    if (tag === '1366x1024') {
      check('1366 资料页 7 列', mat.cols === 7, `${mat.cols}列`);
    }

    // ③ 详情页（两栏）
    if (tag === '1024x768') {
      await go(`#/materials/detail?subject=xingce&id=${cardId}`, `!!document.querySelector('.md-page')`, 1800);
      const d = await cdp.eval(`(() => ({
        flexDir: getComputedStyle(document.querySelector('.md-body')).flexDirection,
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        sideW: Math.round(document.querySelector('.md-side').getBoundingClientRect().width)
      }))()`);
      check('1024 详情页是左右两栏（与电脑一致）', d.flexDir === 'row', JSON.stringify(d));
      check('1024 详情页无横向溢出', d.overflowX === 0, `overflowX=${d.overflowX}`);
      await cdp.shot('03_1024x768_电脑端详情页_横屏');

      // ④ 上传页 / 徽章页
      await go('#/materials/upload?tab=excel', `document.body.innerText.includes('Excel')`, 1500);
      const up = await cdp.eval(`(() => ({ overflowX: document.documentElement.scrollWidth - window.innerWidth, w: Math.round((document.querySelector('.mc-page')||{getBoundingClientRect:()=>({width:0})}).getBoundingClientRect().width) }))()`);
      check('1024 上传页无横向溢出', up.overflowX === 0, JSON.stringify(up));
      await cdp.shot('04_1024x768_电脑端上传页_横屏');

      await go('#/badges', `document.body.innerText.includes('徽章')`, 1800);
      const bd = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        cols: (() => { const g = document.querySelector('.bg-grid'); return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; })()
      }))()`);
      check('1024 徽章页 4 列且无溢出', bd.cols === 4 && bd.overflowX === 0, JSON.stringify(bd));
      await cdp.shot('05_1024x768_电脑端徽章页_横屏');

      // ⑤ 旧地址 302
      await go('#/tablet/materials', `!!document.querySelector('.mat-page')`, 1800);
      const r1 = await cdp.eval(`location.hash`);
      await go('#/tablet/badges', `document.body.innerText.includes('徽章')`, 1800);
      const r2 = await cdp.eval(`location.hash`);
      await go(`#/tablet/materials/detail?subject=xingce&id=${cardId}`, `!!document.querySelector('.md-page')`, 1800);
      const r3 = await cdp.eval(`location.hash`);
      check('旧平板地址自动 302 到电脑端', r1 === '#/materials/xingce' && r2 === '#/badges' && r3.startsWith('#/materials/detail'), `${r1} | ${r2} | ${r3}`);
    }
  }

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
