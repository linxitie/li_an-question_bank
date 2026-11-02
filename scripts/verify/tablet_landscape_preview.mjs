/**
 * 「平板横屏 + 与电脑同版」可行性实测与预期效果
 *
 * 覆盖横屏尺寸：1024×768（iPad 基础横屏）、1180×820（iPad Air）、1366×1024（iPad Pro 12.9 横屏）
 * 每个尺寸都打开**电脑端页面**测：网格列数、单卡尺寸、横向溢出、卡片网格距顶高度、
 * 首屏可见卡片行数、卡片正文字号、<44px 触控目标数；并对触控补齐后的效果截图。
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
const OUT = resolve('docs/plans/assets/备考资料_平板横屏预览');
const IPAD_UA =
  'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 横屏尺寸（iPad 家族 + 常见安卓平板） */
const SIZES = [
  ['1024x768', 1024, 768],
  ['1180x820', 1180, 820],
  ['1366x1024', 1366, 1024]
];

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

/** 触控补齐（最小改动版：不动版式，只把可点区抬到 44px） */
const TOUCH_CSS = `
@media (max-width: 1366px) and (orientation: landscape) {
  .mat-page .top-bar .back,
  .mat-page .fav-toggle,
  .mat-page .block-head a {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    padding: 0 6px;
  }
  #materials-create-bar .mce-btn { height: 44px; border-radius: 22px; }
  .md-page .md-back,
  .md-page .md-fs button,
  .md-page .md-actions button { min-height: 44px; }
}
`;

/** 横屏「紧凑版」候选（可选）：仍是同一套页面/同一区块顺序，只收紧顶部留白并藏掉副标题，
 *  目的是把首屏从 1 行卡片抬到 2 行 —— 只在 ≤1200px 的横屏生效，电脑大屏不受影响 */
const DENSE_CSS = `
@media (max-width: 1200px) and (orientation: landscape) {
  .mat-page .hero { margin: 8px 16px 0; padding: 10px 14px; }
  .mat-page .hero-text h2 { font-size: 18px; }
  .mat-page .hero-text p { display: none; }
  .mat-page .progress-line { margin-top: 4px; }
  #materials-create-bar { margin-top: 6px; }
  #materials-create-bar .mce-hint { display: none; }
  .mat-page .block { margin: 8px 16px 0; }
  .mat-page .block-head { margin-bottom: 6px; }
}
`;

/** 横屏下的版式与密度指标 */
const LANDSCAPE_MEASURE = `(() => {
  const de = document.documentElement;
  const grid = document.querySelector('.card-grid');
  const card = document.querySelector('.card-grid .flip');
  const face = card ? card.querySelector('.face p') : null;
  const gr = grid ? grid.getBoundingClientRect() : null;
  const cr = card ? card.getBoundingClientRect() : null;
  const cs = grid ? getComputedStyle(grid) : null;
  const gap = cs ? parseFloat(cs.gap || cs.rowGap || '0') : 0;
  const rowsVisible = (gr && cr && cr.height)
    ? Math.max(0, Math.floor((window.innerHeight - gr.top + gap) / (cr.height + gap)))
    : 0;
  const tap = [...document.querySelectorAll('a,button,.back,.fav-toggle,.block-head a,.md-back')]
    .map((b) => { const q = b.getBoundingClientRect(); return { t: (b.textContent || '').trim().slice(0, 8), h: Math.round(q.height) }; })
    .filter((x) => x.h > 0 && x.h < 44);
  return {
    vw: window.innerWidth,
    vh: window.innerHeight,
    overflowX: de.scrollWidth - window.innerWidth,
    cols: cs ? cs.gridTemplateColumns.split(' ').length : 0,
    card: cr ? { w: Math.round(cr.width), h: Math.round(cr.height) } : null,
    cardFont: face ? getComputedStyle(face).fontSize : null,
    gridTop: gr ? Math.round(gr.top) : null,
    rowsVisibleFirstScreen: rowsVisible,
    pageHeight: de.scrollHeight,
    smallTap: tap.slice(0, 8),
    heroTitle: (document.querySelector('.hero-text h2') || {}).textContent || ''
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
  const firstCardId = list?.items?.[0]?.id || 0;

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
    await cdp.send('Page.bringToFront', {}, 8000).catch(() => {});
  };
  const go = async (hash, ready, wait = 1600) => {
    await cdp.eval(`location.hash = ${JSON.stringify(hash)}; true`);
    await cdp.waitFor(ready, 20000);
    await sleep(wait);
  };
  const inject = async (css) => {
    const text = String(css || '');
    await cdp.eval(
      `(() => {
        document.getElementById('landscape-preview-override')?.remove();
        const s = document.createElement('style');
        s.id = 'landscape-preview-override';
        s.textContent = ${JSON.stringify(text)};
        document.head.appendChild(s);
        return true;
      })()`
    );
    await sleep(600);
  };
  const unject = async () => {
    await cdp.eval(`document.getElementById('landscape-preview-override')?.remove(); true`);
    await sleep(400);
  };

  const out = {};
  let booted = false;
  for (const [tag, w, h] of SIZES) {
    await setViewport(w, h);
    if (!booted) {
      await cdp.send('Page.navigate', { url: `${BASE}/#/` });
      await cdp.waitFor(`document.readyState === 'complete'`);
      await sleep(1800);
      await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
      await cdp.eval(
        `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
      );
      booted = true;
    }

    // 电脑端资料页
    await go('#/materials/xingce', `!!document.querySelector('.mat-page')`, 2000);
    out[`mat_base_${tag}`] = await cdp.eval(LANDSCAPE_MEASURE);
    await cdp.shot(`01_横屏_${tag}_电脑端资料页_基线`);
    await inject(TOUCH_CSS);
    out[`mat_touch_${tag}`] = await cdp.eval(LANDSCAPE_MEASURE);
    await cdp.shot(`02_横屏_${tag}_电脑端资料页_触控补齐`);
    await inject(TOUCH_CSS + DENSE_CSS);
    out[`mat_dense_${tag}`] = await cdp.eval(LANDSCAPE_MEASURE);
    await cdp.shot(`03_横屏_${tag}_电脑端资料页_紧凑版`);
    await unject();

    if (tag === '1024x768') {
      await go(`#/materials/detail?subject=xingce&id=${firstCardId}`, `!!document.querySelector('.md-page')`, 1800);
      out.detail_1024 = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        bodyH: Math.round(document.body.getBoundingClientRect().height),
        flexDir: getComputedStyle(document.querySelector('.md-body')).flexDirection,
        sideW: (() => { const s = document.querySelector('.md-side'); return s ? Math.round(s.getBoundingClientRect().width) : null; })(),
        stackTop: (() => { const s = document.querySelector('.md-stack'); return s ? Math.round(s.getBoundingClientRect().top) : null; })()
      }))()`);
      await cdp.shot('03_横屏_1024x768_电脑端详情页');

      await go('#/materials/upload?tab=excel', `document.body.innerText.includes('Excel')`, 1500);
      out.upload_1024 = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        w: Math.round((document.querySelector('.mc-page') || {}).getBoundingClientRect?.().width || 0),
        max: (document.querySelector('.mc-page') ? getComputedStyle(document.querySelector('.mc-page')).maxWidth : null)
      }))()`);
      await cdp.shot('04_横屏_1024x768_电脑端上传页');

      await go('#/badges', `document.body.innerText.includes('徽章')`, 1800);
      out.badges_1024 = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        cols: (() => { const g = document.querySelector('.bg-grid'); return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; })()
      }))()`);
      await cdp.shot('05_横屏_1024x768_电脑端徽章页');

      // 平板首页（横屏现状，用于对比「统一前后」的入口体验）
      await go('#/tablet/home', `!!document.querySelector('.quick-actions')`, 2000);
      out.tabletHome_1024 = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        entry: !!document.getElementById('tablet-materials-entry'),
        entryRect: (() => { const e = document.getElementById('tablet-materials-entry'); if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })()
      }))()`);
      await cdp.shot('06_横屏_1024x768_平板首页');
    }
  }

  ws.close();
  writeFileSync(`${OUT}/_landscape.json`, JSON.stringify(out, null, 2), 'utf8');
  console.log('\n=== 汇总 ===');
  for (const [tag] of SIZES) {
    const b = out[`mat_base_${tag}`];
    const t = out[`mat_touch_${tag}`];
    console.log(`${tag}: 基线 cols=${b.cols} card=${b.card?.w}x${b.card?.h} 字号=${b.cardFont} gridTop=${b.gridTop} 首屏可见=${b.rowsVisibleFirstScreen}行 溢出=${b.overflowX} 小目标=${b.smallTap.length}`);
    console.log(`${tag}: 补齐 cols=${t.cols} card=${t.card?.w}x${t.card?.h} 溢出=${t.overflowX} 小目标=${t.smallTap.length}`);
  }
  console.log('detail_1024', JSON.stringify(out.detail_1024));
  console.log('upload_1024', JSON.stringify(out.upload_1024));
  console.log('badges_1024', JSON.stringify(out.badges_1024));
  console.log('tabletHome_1024', JSON.stringify(out.tabletHome_1024));
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
