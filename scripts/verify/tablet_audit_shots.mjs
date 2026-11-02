/**
 * 平板端（768×1024 / 1024×768）现状核查：
 *  1) 备考资料在平板上是否有入口、走的哪条路由
 *  2) 卡片栈复用手机页后在平板宽度下的形变（固定 226px 高 × 全宽）
 *  3) 徽章页、创建/Excel 上传页在平板宽度下的溢出与可点区
 *  4) PC 资料页被平板直接打开时会怎样（说明「没有平板专属设计」的影响面）
 *
 * 依赖：前端 9527（DEV_BACKEND_ORIGIN=http://127.0.0.1:8010）、后端 8010、Chrome 9222。
 * 只读：不建卡、不改数据；截图落 docs/plans/assets/备考资料_平板端验收/
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_平板端验收');
const IPAD_UA =
  'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
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
      data = (await this.send('Page.captureScreenshot', { format: 'png', fromSurface: false }, 20000))
        .data;
    }
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, 'base64'));
    console.log('  ✓', name);
  }
}

const M = `(() => {
  const de = document.documentElement;
  const card = document.querySelector('.stack-card.lv0');
  const r = card ? card.getBoundingClientRect() : null;
  const act = document.querySelector('.card-act');
  const bar = document.querySelector('.stack-bar button');
  const small = [...document.querySelectorAll('button, .card-act, .tabs .tab, .chip')]
    .map((b) => { const q = b.getBoundingClientRect(); return { t: (b.textContent || '').trim().slice(0, 10), w: Math.round(q.width), h: Math.round(q.height) }; })
    .filter((x) => x.w > 0 && x.h > 0 && (x.h < 40 || x.w < 40));
  return {
    hash: location.hash,
    vw: window.innerWidth,
    vh: window.innerHeight,
    scrollW: de.scrollWidth,
    overflowX: de.scrollWidth - window.innerWidth,
    card: r ? { w: Math.round(r.width), h: Math.round(r.height), aspect: +(r.width / r.height).toFixed(2) } : null,
    actBtn: act ? { w: Math.round(act.getBoundingClientRect().width), h: Math.round(act.getBoundingClientRect().height) } : null,
    barBtnH: bar ? Math.round(bar.getBoundingClientRect().height) : null,
    smallTap: small.slice(0, 8)
  };
})()`;

/** 列出页面上可见的「入口」文字（排除 style/script，避免把 CSS 当文案） */
const ENTRIES = `(() => {
  const bad = new Set(['STYLE', 'SCRIPT', 'LINK', 'META', 'TITLE']);
  const leaves = [...document.querySelectorAll('a,button,[role="button"],li,div,span,p')].filter((e) => {
    if (bad.has(e.tagName)) return false;
    if (e.querySelector('a,button,[role="button"]')) return false;
    const t = (e.textContent || '').trim();
    return t && t.length <= 14 && e.getBoundingClientRect().height > 0;
  });
  return [...new Set(leaves.map((e) => e.textContent.trim()))].slice(0, 40);
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
  if (!stu.access_token) throw new Error('登录失败：' + JSON.stringify(stu));

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
  };

  const go = async (hash, ready, extraWait = 900) => {
    await cdp.eval(`location.hash = ${JSON.stringify(hash)}; true`);
    await cdp.waitFor(ready, 20000);
    await sleep(extraWait);
  };

  const out = {};

  // ---------- 平板竖屏 768×1024 ----------
  await setViewport(768, 1024);
  await cdp.send('Page.navigate', { url: `${BASE}/#/tablet/home` });
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(1600);
  await cdp.eval(
    `localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`
  );
  const lp = await cdp.eval(
    `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
  );
  console.log('登录注入:', lp);

  // 设备判定 & 首页入口
  const dev = await cdp.eval(`(() => ({
    w: window.innerWidth,
    ua: navigator.userAgent.includes('iPad'),
    touch: navigator.maxTouchPoints,
    hash: location.hash
  }))()`);
  console.log('设备', JSON.stringify(dev));
  out.home = await cdp.eval(M);
  out.homeEntries = await cdp.eval(ENTRIES);
  console.log('平板首页入口', JSON.stringify(out.homeEntries));
  await cdp.shot('01_平板首页_768');

  // 我的页 → 资料入口
  await go('#/tablet/profile', `document.body.innerText.includes('我的') || !!document.querySelector('.user-role')`);
  out.profile = await cdp.eval(M);
  out.profileEntries = await cdp.eval(ENTRIES);
  const profHit = await cdp.eval(`(() => {
    const el = [...document.querySelectorAll('a,button,[role="button"],div,span')]
      .filter((e) => !['STYLE','SCRIPT'].includes(e.tagName) && !e.querySelector('a,button,[role="button"]'))
      .find((e) => /资料|下载|备考/.test((e.textContent || '').trim()) && (e.textContent || '').trim().length <= 12);
    return el ? { text: el.textContent.trim(), tag: el.tagName } : null;
  })()`);
  out.profileHit = profHit;
  console.log('我的页资料入口', JSON.stringify(profHit), '| 入口数', out.profileEntries.length);
  await cdp.shot('02_平板我的页_资料入口');

  // 备考资料（复用手机页）
  await go('#/tablet/materials', `!!document.querySelector('.stack-card')`, 1200);
  out.materials = await cdp.eval(M);
  out.materialsList = await cdp.eval(`(() => {
    const top = document.querySelector('.stack-card.lv0');
    const title = top ? (top.querySelector('.card-title') || {}).textContent : '';
    const fs = top ? getComputedStyle(top.querySelector('.card-title') || top).fontSize : '';
    const listCols = getComputedStyle(document.querySelector('.list') || document.body).gridTemplateColumns;
    return { title: (title || '').trim().slice(0, 30), titleFont: fs, listCols, hash: location.hash };
  })()`);
  console.log('平板资料页', JSON.stringify({ ...out.materials, ...out.materialsList }));
  await cdp.shot('03_平板资料页_卡片栈_768');

  // 翻页 / 翻转 / 看配图在平板上的表现
  await cdp.eval(`[...document.querySelectorAll('.stack-bar button')].find(b => b.textContent.includes('下一张')).click(); true`);
  await sleep(900);
  await cdp.shot('04_平板资料页_翻页后');
  await cdp.eval(`document.querySelector('.stack-card.lv0').click(); true`);
  await sleep(900);
  out.flip = await cdp.eval(`(() => {
    const inner = document.querySelector('.card-inner');
    return { flipped: !!document.querySelector('.stack.is-flipped'), t: inner ? getComputedStyle(inner).transform.slice(0, 20) : '' };
  })()`);
  await cdp.shot('05_平板资料页_卡片背面');
  await cdp.eval(`document.querySelector('.card-act') && document.querySelector('.card-act').click(); true`);
  const okLb = await cdp.waitFor(`!!document.querySelector('.lb-mask')`, 8000);
  await sleep(600);
  out.lightbox = await cdp.eval(`(() => {
    const img = document.querySelector('.lb-img');
    const r = img ? img.getBoundingClientRect() : null;
    const tools = [...document.querySelectorAll('.lb-tool, .lb-nav')].map((b) => {
      const q = b.getBoundingClientRect();
      return { t: (b.getAttribute('title') || b.textContent || '').trim().slice(0, 8), w: Math.round(q.width), h: Math.round(q.height) };
    });
    return {
      open: !!document.querySelector('.lb-mask'),
      img: r ? { w: Math.round(r.width), h: Math.round(r.height) } : null,
      count: (document.querySelector('.lb-count') || {}).textContent || '',
      tools,
      smallTools: tools.filter((x) => x.w > 0 && (x.h < 44 || x.w < 44))
    };
  })()`);
  console.log('平板全图查看器', JSON.stringify({ okLb, ...out.lightbox }));
  await cdp.shot('06_平板_卡片配图全图');
  await cdp.eval(`document.querySelector('.lb-close') && document.querySelector('.lb-close').click(); true`);
  await sleep(400);

  // 创建卡片（手机页内建卡弹层）
  await cdp.eval(`document.querySelector('.create-btn') && document.querySelector('.create-btn').click(); true`);
  const okSheet = await cdp.waitFor(`!!document.querySelector('.cc-subjects')`, 8000);
  await sleep(500);
  out.create = await cdp.eval(`(() => {
    const mask = document.querySelector('.cc-mask');
    const panel = document.querySelector('.cc-panel');
    const mr = mask ? mask.getBoundingClientRect() : null;
    const pr = panel ? panel.getBoundingClientRect() : null;
    const step = document.querySelector('.cc-batch-step');
    return {
      open: !!document.querySelector('.cc-subjects'),
      mask: mr ? { w: Math.round(mr.width), h: Math.round(mr.height) } : null,
      panel: pr ? { w: Math.round(pr.width), h: Math.round(pr.height) } : null,
      panelMaxW: panel ? getComputedStyle(panel).maxWidth : null,
      batchStep: step ? step.textContent.trim() : null
    };
  })()`);
  console.log('平板建卡弹层', JSON.stringify({ okSheet, ...out.create }));
  await cdp.shot('07_平板_建卡弹层_选科目');
  await cdp.eval(`document.querySelector('.cc-close') && document.querySelector('.cc-close').click(); true`);
  await sleep(400);

  // 徽章页（无平板路由，走 PC 页）
  await go('#/badges', `document.body.innerText.includes('徽章')`, 1400);
  out.badges = await cdp.eval(M);
  out.badgeGrid = await cdp.eval(`(() => {
    const cands = [...document.querySelectorAll('[class*="grid"], [class*="wall"], [class*="list"]')]
      .filter((e) => e.children.length >= 3);
    const g = cands[0];
    if (!g) return { cols: null, cls: null };
    const cs = getComputedStyle(g);
    return {
      cls: g.className,
      display: cs.display,
      cols: cs.display.includes('grid') ? cs.gridTemplateColumns.split(' ').length : null,
      w: Math.round(g.getBoundingClientRect().width),
      childW: Math.round(g.children[0].getBoundingClientRect().width),
      childH: Math.round(g.children[0].getBoundingClientRect().height)
    };
  })()`);
  console.log('平板徽章页', JSON.stringify({ ...out.badges, ...out.badgeGrid }));
  await cdp.shot('08_平板徽章页_768');

  // Excel 上传页（无平台前缀）
  await go('#/materials/upload?tab=excel', `document.body.innerText.includes('Excel')`, 1200);
  out.upload = await cdp.eval(M);
  out.uploadBox = await cdp.eval(`(() => {
    // 之前用 .mu-page/.page 都没命中，回落到 body.firstElementChild（#app）→ 误判成「通栏无上限」；
    // 真实容器是 .mc-page（max-width:860px）
    const box = document.querySelector('.mc-page');
    const r = box ? box.getBoundingClientRect() : null;
    const sub = document.querySelector('.mc-sub');
    const sr = sub ? sub.getBoundingClientRect() : null;
    return {
      container: box ? '.mc-page' : null,
      w: r ? Math.round(r.width) : null,
      max: box ? getComputedStyle(box).maxWidth : null,
      textW: sr ? Math.round(sr.width) : null
    };
  })()`);
  console.log('平板 Excel 上传页', JSON.stringify({ ...out.upload, ...out.uploadBox }));
  await cdp.shot('09_平板_Excel上传页_768');

  // PC 资料页在平板宽度下（说明「没有平板专属设计」时的实际后果）
  await cdp.eval(`location.hash = '#/materials/shenlun'; true`);
  await sleep(2200);
  out.pcPage = await cdp.eval(M);
  out.pcPageInfo = await cdp.eval(`(() => ({
    hash: location.hash,
    matPage: !!document.querySelector('.mat-page'),
    topBar: (document.querySelector('.mat-page > .top-bar') || {}).innerText || '',
    cardW: (() => { const c = document.querySelector('.card, .flip-card, [class*="card"]'); if (!c) return null; const r = c.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })(),
    bodyHead: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 120)
  }))()`);
  console.log('平板打开 PC 资料页', JSON.stringify({ ...out.pcPage, ...out.pcPageInfo }));
  await cdp.shot('10_平板打开PC资料页_768');

  // ---------- 平板横屏 1024×768 ----------
  await setViewport(1024, 768);
  await go('#/tablet/materials', `!!document.querySelector('.stack-card')`, 1200);
  out.materialsLandscape = await cdp.eval(M);
  console.log('横屏资料页', JSON.stringify(out.materialsLandscape));
  await cdp.shot('11_平板横屏_资料页_1024');

  ws.close();
  writeFileSync(`${OUT}/_audit.json`, JSON.stringify(out, null, 2), 'utf8');
  console.log('\n已写入', `${OUT}/_audit.json`);
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
