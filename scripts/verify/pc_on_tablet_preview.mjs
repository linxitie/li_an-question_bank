/**
 * 「平板与电脑用同一套页面」可行性实测 + 预期效果预览
 *
 * 做法：
 *  1) 把视口切成平板（768×1024 / 1024×768），直接打开**电脑端**页面
 *     （/materials/xingce、/materials/detail、/materials/upload、/badges）
 *  2) 记录基线数据：横向溢出、卡片网格列数与单卡尺寸、触控目标高度
 *  3) 注入「候选覆盖样式」（不动 .vtj 源码，只在本次会话注入 <style>），再测一遍并截图
 *     → 截图即「预期效果图」：真实页面 + 候选 CSS 的真实渲染，不是画图
 *
 * 依赖：前端 9527、后端 8000、Chrome 9222。只读，不改数据库。
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8000';
const OUT = resolve('docs/plans/assets/备考资料_平板PC同版预览');
const IPAD_UA =
  'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

/**
 * 「预期效果」用的候选覆盖样式（最小改动版）
 * 结论先行：电脑端页面在 768/1024 下**版式本来就成立**（auto-fill 网格自动变 3/6 列、无横向溢出），
 * 所以只补触控目标高度，不动网格/间距 —— 这样才是真正的「同一套页面、同一套布局」。
 */
const OVERRIDE_CSS = `
@media (max-width: 1024px) {
  .mat-page .top-bar .back,
  .mat-page .fav-toggle,
  .mat-page .block-head a {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    padding: 0 6px;
  }
  /* DOM 注入的建卡操作条（PC 版功能，平板同样可见） */
  #materials-create-bar .mce-btn { height: 44px; border-radius: 22px; }
  /* 详情页触控 */
  .md-page .md-back,
  .md-page .md-fs button,
  .md-page .md-actions button { min-height: 44px; }
}
`;

const MEASURE = `(() => {
  const de = document.documentElement;
  const grid = document.querySelector('.card-grid');
  const card = document.querySelector('.card-grid .flip');
  const cr = card ? card.getBoundingClientRect() : null;
  const cs = grid ? getComputedStyle(grid) : null;
  const tap = [...document.querySelectorAll('a,button,.md-back,.fav-toggle,.block-head a')]
    .map((b) => { const q = b.getBoundingClientRect(); return { t: (b.textContent || '').trim().slice(0, 8), w: Math.round(q.width), h: Math.round(q.height) }; })
    .filter((x) => x.w > 0 && x.h > 0 && x.h < 44);
  return {
    vw: window.innerWidth,
    overflowX: de.scrollWidth - window.innerWidth,
    gridCols: cs ? cs.gridTemplateColumns.split(' ').length : 0,
    card: cr ? { w: Math.round(cr.width), h: Math.round(cr.height) } : null,
    smallTap: tap.slice(0, 8),
    heroTitle: (document.querySelector('.hero-text h2') || {}).textContent || '',
    hasMatPage: !!document.querySelector('.mat-page'),
    hasGrid: !!grid,
    bodyHead: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 60)
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

  const setViewport = async (w, h) => {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: w,
      height: h,
      deviceScaleFactor: 2,
      mobile: true
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

  const injectOverride = async () => {
    await cdp.eval(`(() => {
      const id = 'tablet-pc-preview-override';
      document.getElementById(id)?.remove();
      const s = document.createElement('style');
      s.id = id;
      s.textContent = ${JSON.stringify(OVERRIDE_CSS)};
      document.head.appendChild(s);
      return true;
    })()`);
    await sleep(700);
  };
  const removeOverride = async () => {
    await cdp.eval(`document.getElementById('tablet-pc-preview-override')?.remove(); true`);
    await sleep(400);
  };

  const out = {};

  for (const [tag, w, h] of [['768x1024', 768, 1024], ['1024x768', 1024, 768]]) {
    await setViewport(w, h);
    if (tag === '768x1024') {
      await cdp.send('Page.navigate', { url: `${BASE}/#/` });
      await cdp.waitFor(`document.readyState === 'complete'`);
      await sleep(1800);
      await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
      await cdp.eval(
        `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
      );
    }

    // ① 电脑端资料页（/materials/xingce）
    await go('#/materials/xingce', `!!document.querySelector('.mat-page')`, 2000);
    out[`mat_before_${tag}`] = await cdp.eval(MEASURE);
    await cdp.shot(`01_PC资料页_平板基线_${tag}`);
    await injectOverride();
    out[`mat_after_${tag}`] = await cdp.eval(MEASURE);
    await cdp.shot(`02_PC资料页_平板适配后_${tag}`);
    await removeOverride();

    if (tag === '768x1024') {
      // ② 电脑端详情页（取该科目第一张卡的真实 id）
      const list = await (
        await fetch(`${API}/api/materials?subject=xingce&type=card&page_size=1`, {
          headers: { Authorization: `Bearer ${stu.access_token}` }
        })
      ).json();
      const firstCardId = list?.items?.[0]?.id || 0;
      await go(`#/materials/detail?subject=xingce&id=${firstCardId}`, `!!document.querySelector('.md-page')`, 1800);
      out.detail = await cdp.eval(`(() => ({
        hash: location.hash,
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        flexDir: getComputedStyle(document.querySelector('.md-body')).flexDirection,
        sideW: (() => { const s = document.querySelector('.md-side'); return s ? Math.round(s.getBoundingClientRect().width) : null; })(),
        title: (document.querySelector('.md-title') || {}).textContent || ''
      }))()`);
      await cdp.shot('03_PC详情页_平板_768x1024');

      // ③ 电脑端 Excel 上传页
      await go('#/materials/upload?tab=excel', `document.body.innerText.includes('Excel')`, 1500);
      out.upload = await cdp.eval(MEASURE);
      await cdp.shot('04_PC上传页_平板_768x1024');

      // ④ 徽章页
      await go('#/badges', `document.body.innerText.includes('徽章')`, 1800);
      out.badges = await cdp.eval(`(() => ({
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        cols: (() => { const g = document.querySelector('.bg-grid'); return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; })(),
        small: [...document.querySelectorAll('.bg-page button, .bd-chip')].map((b) => Math.round(b.getBoundingClientRect().height)).filter((x) => x > 0 && x < 44).length
      }))()`);
      await cdp.shot('05_PC徽章页_平板_768x1024');
    }
  }

  ws.close();
  writeFileSync(`${OUT}/_feasibility.json`, JSON.stringify(out, null, 2), 'utf8');
  console.log('\n结果：', JSON.stringify(out, null, 2).slice(0, 2500));
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
