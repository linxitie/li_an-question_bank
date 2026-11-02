/**
 * ③「平板首页也切电脑版」的预期效果实测
 *
 * 电脑首页 = `$vtj/vue/home_page.vue`，上层是 `grid-template-columns: 280px 1fr 320px` 三栏。
 * 这里在 iPad 横屏三种尺寸下真实渲染电脑首页，量：三栏实际宽度、溢出、触控目标，
 * 并对两种候选适配出图：
 *   V1 基线（原样三栏）
 *   V2 两侧收窄（280/320 → 220/260）
 *   V3 右栏下移（两栏 + 右栏独占一行）
 *
 * 依赖：前端 9527、后端 8010、Chrome 9222。只读。
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_平板首页电脑版预览');
const IPAD_UA =
  'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
/** 关键：`/home` 在平板设备下会被 device.ts 映射到 `/tablet/home`（R4 不许改），
 *  所以预览「电脑首页在平板横屏」必须用「桌面设备 + 横屏尺寸」来渲染，
 *  否则拿到的其实是平板首页。 */
const DESKTOP_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

/** 触控补齐（首页相关按钮/链接） */
const TOUCH_CSS = `
@media (orientation: landscape) and (max-width: 1366px) {
  .home-page a,
  .home-page button,
  .home-page .nav-item,
  .home-page .section-more,
  .home-page .quick-action {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
  }
}
`;

/** V2：两侧栏收窄，让中间内容更宽 */
const V2_CSS = `
@media (orientation: landscape) and (max-width: 1200px) {
  .home-page .top-section { grid-template-columns: 220px 1fr 260px; gap: 14px; }
  .home-page .page-inner, .home-page .container { padding-left: 20px; padding-right: 20px; }
}
`;

/** V3：右栏下移（两栏 + 右栏独占一行） */
const V3_CSS = `
@media (orientation: landscape) and (max-width: 1200px) {
  .home-page .top-section { grid-template-columns: 240px 1fr; gap: 14px; }
  .home-page .right-col { grid-column: 1 / -1; }
}
`;

const MEASURE = `(() => {
  const de = document.documentElement;
  const top = document.querySelector('.top-section');
  const cols = top ? getComputedStyle(top).gridTemplateColumns : '';
  const rects = ['left-col', 'center-col', 'right-col'].map((c) => {
    const el = document.querySelector('.' + c);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { c, w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) };
  });
  const recruit = document.querySelector('.recruit-grid');
  const tap = [...document.querySelectorAll('a,button,.nav-item,.section-more')]
    .map((b) => { const q = b.getBoundingClientRect(); return { t: (b.textContent || '').trim().slice(0, 8), h: Math.round(q.height) }; })
    .filter((x) => x.h > 0 && x.h < 44);
  return {
    vw: window.innerWidth,
    vh: window.innerHeight,
    overflowX: de.scrollWidth - window.innerWidth,
    pageHeight: de.scrollHeight,
    topCols: cols,
    cols: rects,
    recruitCols: recruit ? getComputedStyle(recruit).gridTemplateColumns.split(' ').length : 0,
    smallTap: tap.slice(0, 6),
    smallTapCount: tap.length,
    hasHome: !!document.querySelector('.home-page'),
    bodyHead: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 70)
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

  const setViewport = async (w, h, tablet = false) => {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: w,
      height: h,
      deviceScaleFactor: 2,
      mobile: tablet,
      screenOrientation: { type: 'landscapePrimary', angle: 90 }
    });
    await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: tablet, maxTouchPoints: tablet ? 5 : 0 }).catch(() => {});
    await cdp.send('Emulation.setUserAgentOverride', { userAgent: tablet ? IPAD_UA : DESKTOP_UA }).catch(() => {});
    await cdp.send('Page.bringToFront', {}, 8000).catch(() => {});
  };
  const go = async (hash, ready, wait = 1600) => {
    await cdp.eval(`location.hash = ${JSON.stringify(hash)}; true`);
    await cdp.waitFor(ready, 20000);
    await sleep(wait);
  };
  const inject = async (css) => {
    await cdp.eval(
      `(() => {
        document.getElementById('home-preview-override')?.remove();
        const s = document.createElement('style');
        s.id = 'home-preview-override';
        s.textContent = ${JSON.stringify(String(css || ''))};
        document.head.appendChild(s);
        return true;
      })()`
    );
    await sleep(700);
  };
  const unject = async () => {
    await cdp.eval(`document.getElementById('home-preview-override')?.remove(); true`);
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

    await go('#/home', `!!document.querySelector('.home-page')`, 2400);
    out[`home_base_${tag}`] = await cdp.eval(MEASURE);
    await cdp.shot(`01_${tag}_电脑首页_基线`);
    await inject(TOUCH_CSS);
    out[`home_touch_${tag}`] = await cdp.eval(MEASURE);
    await cdp.shot(`02_${tag}_电脑首页_触控补齐`);
    await inject(TOUCH_CSS + V2_CSS);
    out[`home_v2_${tag}`] = await cdp.eval(MEASURE);
    await cdp.shot(`03_${tag}_电脑首页_V2两侧收窄`);
    await inject(TOUCH_CSS + V3_CSS);
    out[`home_v3_${tag}`] = await cdp.eval(MEASURE);
    await cdp.shot(`04_${tag}_电脑首页_V3右栏下移`);
    await unject();

    // 对照：同一尺寸下「现在的平板首页」
    if (tag === '1024x768') {
      await setViewport(w, h, true);
      await cdp.eval(`location.hash = '#/tablet/home'; true`);
      await cdp.waitFor(`!!document.querySelector('.quick-actions')`, 15000);
      await sleep(1600);
      out.tabletHome_1024 = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        hash: location.hash,
        hasQuick: !!document.querySelector('.quick-actions'),
        entry: !!document.getElementById('tablet-materials-entry')
      }))()`);
      await cdp.shot('00_1024x768_现行平板首页_对照');
      await setViewport(w, h, false);
    }
  }

  ws.close();
  writeFileSync(`${OUT}/_home.json`, JSON.stringify(out, null, 2), 'utf8');
  console.log('\n=== 汇总 ===');
  for (const [tag] of SIZES) {
    for (const k of ['home_base', 'home_touch', 'home_v2', 'home_v3']) {
      const v = out[`${k}_${tag}`];
      console.log(`${tag} ${k}: cols=${v.topCols} 子列=${v.cols.map((c) => (c ? c.w : '-')).join('/')} 招考=${v.recruitCols}列 溢出=${v.overflowX} 小目标=${v.smallTapCount}`);
    }
  }
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
