/**
 * 平板全图查看器「触摸手势」真机模拟验收：
 *  1) 双指捏合 → 缩放百分比变大（真实 Input.dispatchTouchEvent，不是直接改 ref）
 *  2) 单指左滑 → 切到第 2 张（放大状态下应当不切图，避免和缩放抢手势）
 *
 * 依赖：前端 9527、后端 8000、Chrome 9222。
 * 会临时建 1 张申论演示卡（2 张配图），跑完用 scripts/verify/cleanup_round3.py 清理。
 */
import http from 'node:http';
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8000';
const OUT = resolve('docs/plans/assets/备考资料_平板端验收');
const DEMO_IMG = [
  resolve('docs/plans/assets/备考资料_三轮验收/_素材/demo-img-1.png'),
  resolve('docs/plans/assets/备考资料_三轮验收/_素材/demo-img-2.png')
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const results = [];
const check = (label, pass, extra = '') => {
  results.push({ label, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${label}${extra ? '  → ' + extra : ''}`);
};

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
  /** 触摸事件分发：带超时重试，避免上一组手势没收敛导致下一次挂住 */
  async touch(type, points, timeoutMs = 12000) {
    try {
      await this.send('Input.dispatchTouchEvent', { type, touchPoints: points }, timeoutMs);
    } catch (e) {
      // 先结束残留触点，再重试一次
      await this.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }, 5000).catch(() => {});
      await sleep(250);
      await this.send('Input.dispatchTouchEvent', { type, touchPoints: points }, timeoutMs);
    }
  }
  async resetTouches() {
    await this.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }, 5000).catch(() => {});
    await sleep(150);
  }
  /** 单指滑动 */
  async swipe(from, to, steps = 5) {
    await this.resetTouches();
    await this.touch('touchStart', [{ x: from.x, y: from.y, id: 1 }]);
    for (let i = 1; i <= steps; i++) {
      const x = from.x + ((to.x - from.x) * i) / steps;
      const y = from.y + ((to.y - from.y) * i) / steps;
      await this.touch('touchMove', [{ x, y, id: 1 }]);
      await sleep(20);
    }
    await this.touch('touchEnd', []);
  }
  /** 双指捏合（factor > 1 张开，< 1 捏拢） */
  async pinch(center, startGap, factor, steps = 5) {
    await this.resetTouches();
    const p = (gap) => [
      { x: center.x - gap / 2, y: center.y, id: 1 },
      { x: center.x + gap / 2, y: center.y, id: 2 }
    ];
    await this.touch('touchStart', p(startGap));
    for (let i = 1; i <= steps; i++) {
      const gap = startGap * (1 + (factor - 1) * (i / steps));
      await this.touch('touchMove', p(gap));
      await sleep(20);
    }
    await this.touch('touchEnd', []);
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

  // 演示卡：2 张配图（第 1 张 cover、第 2 张进 content），保证「左右滑动」有 2 张可切
  const tag = String(Date.now()).slice(-6);
  const fd = new FormData();
  fd.append('subject', 'shenlun');
  fd.append('card_front', `申论对策题 三步成文（演示 ${tag}）`);
  fd.append('card_back', '①亮明观点；②分主体给对策；③回扣题干做小结。');
  fd.append('category', '提出对策');
  for (const p of DEMO_IMG) {
    if (existsSync(p)) fd.append('images', new Blob([readFileSync(p)], { type: 'image/png' }), 'demo.png');
  }
  const created = await (
    await fetch(`${API}/api/materials/my/card`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${stu.access_token}` },
      body: fd
    })
  ).json();
  if (!created.id) throw new Error('演示卡创建失败：' + JSON.stringify(created));
  console.log('演示卡 id =', created.id, '配图 =', (created.images || []).length);

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
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    // 2026-11-02：平板已与电脑同版（/tablet/materials → /materials/xingce，电脑页），
    // 全图手势组件仍在手机端资料页使用 → 这里改用手机视口验证同一个组件。
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true
  });
  await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 }).catch(() => {});
  // 触摸事件要送进渲染进程，窗口被遮挡时容易挂住：先把页面提到前台并开焦点模拟
  await cdp.send('Page.bringToFront', {}, 8000).catch(() => {});
  await cdp.send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {});

  /** 按视口比例算触点（换成手机/平板视口都不会落到屏幕外） */
  const vp = async () => {
    const d = await cdp.eval(`({ w: window.innerWidth, h: window.innerHeight })`);
    return d;
  };
  const gesture = (w, h) => ({
    center: { x: Math.round(w * 0.5), y: Math.round(h * 0.5) },
    left: { x: Math.round(w * 0.2), y: Math.round(h * 0.5) },
    right: { x: Math.round(w * 0.8), y: Math.round(h * 0.5) },
    gap: Math.round(w * 0.45)
  });

  await cdp.send('Page.navigate', { url: `${BASE}/#/` });
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(1500);
  await cdp.eval(`localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`);
  const lp = await cdp.eval(
    `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
  );
  check('学生登录态注入', lp === 'ok', lp);

  const { w: vw, h: vh } = await vp();
  const G = gesture(vw, vh);

  await cdp.eval(`location.hash = '#/mobile/materials'; true`);
  await cdp.waitFor(`!!document.querySelector('.stack-card')`);
  await cdp.eval(
    `[...document.querySelectorAll('.tabs .tab')].find(t => t.textContent.includes('申论')).click(); true`
  );
  await cdp.waitFor(
    `document.querySelector('.stack-card.lv0 .card-title') && document.querySelector('.stack-card.lv0 .card-title').textContent.includes('演示')`,
    15000
  );
  await sleep(700);

  // 打开全图（演示卡有 2 张图）
  const actText = await cdp.eval(`(document.querySelector('.card-act')||{}).textContent || ''`);
  check('卡片按钮显示 2 张配图', /2/.test(actText), actText.trim());
  await cdp.eval(`document.querySelector('.card-act').click(); true`);
  const okLb = await cdp.waitFor(`!!document.querySelector('.lb-mask')`, 8000);
  await sleep(600);

  const before = await cdp.eval(`(() => ({
    count: (document.querySelector('.lb-count')||{}).textContent || '',
    scaleText: (document.querySelector('.lb-scale')||{}).textContent || '',
    transform: (document.querySelector('.lb-img')||{}).style ? document.querySelector('.lb-img').style.transform : ''
  }))()`);
  console.log('全图初始', JSON.stringify(before));
  check('全图已打开且有 2 张', okLb && before.count.trim().startsWith('1 / 2'), before.count.trim());
  await cdp.shot('12_平板全图_手势前');

  // ① 双指张开 → 缩放应 > 100%
  await cdp.pinch(G.center, G.gap, 1.8);
  await sleep(500);
  const afterPinch = await cdp.eval(`(() => ({
    scaleText: (document.querySelector('.lb-scale')||{}).textContent || '',
    transform: document.querySelector('.lb-img').style.transform || ''
  }))()`);
  const pinchPct = parseInt((afterPinch.scaleText || '').replace('%', ''), 10);
  console.log('捏合后', JSON.stringify(afterPinch));
  check('双指张开能放大（>100%）', Number.isFinite(pinchPct) && pinchPct > 100, afterPinch.scaleText);
  await cdp.shot('13_平板全图_双指放大');

  // ② 放大状态下左滑 → 不应切图（防手势打架）
  const idxBeforeSwipe = await cdp.eval(`(document.querySelector('.lb-count')||{}).textContent || ''`);
  await cdp.swipe(G.right, G.left);
  await sleep(400);
  const idxAfterZoomedSwipe = await cdp.eval(`(document.querySelector('.lb-count')||{}).textContent || ''`);
  console.log('放大后左滑', JSON.stringify({ idxBeforeSwipe, idxAfterZoomedSwipe }));
  check('放大状态下左滑不切图', idxBeforeSwipe.trim() === idxAfterZoomedSwipe.trim(), `${idxBeforeSwipe.trim()} → ${idxAfterZoomedSwipe.trim()}`);

  // ③ 复位到 1:1，再左滑 → 应切到第 2 张
  await cdp.eval(`document.querySelector('.lb-reset').click(); true`);
  await sleep(300);
  await cdp.swipe(G.right, G.left);
  await sleep(500);
  const afterSwipe = await cdp.eval(`(() => ({
    count: (document.querySelector('.lb-count')||{}).textContent || '',
    scaleText: (document.querySelector('.lb-scale')||{}).textContent || ''
  }))()`);
  console.log('1:1 左滑后', JSON.stringify(afterSwipe));
  check('1:1 状态下左滑切到下一张', afterSwipe.count.trim() === '2 / 2', afterSwipe.count.trim());
  check('切图后缩放回到 100%', (afterSwipe.scaleText || '').trim() === '100%', afterSwipe.scaleText);
  await cdp.shot('14_平板全图_左滑到第2张');

  // ④ 右滑回到第 1 张
  await cdp.swipe(G.left, G.right);
  await sleep(450);
  const afterSwipeBack = await cdp.eval(`(document.querySelector('.lb-count')||{}).textContent || ''`);
  check('右滑回到上一张', afterSwipeBack.trim() === '1 / 2', afterSwipeBack.trim());

  // ⑤ 双指捏合 → 缩不回 100% 以下
  await cdp.pinch(G.center, G.gap, 0.4);
  await sleep(400);
  const afterPinchIn = await cdp.eval(`(document.querySelector('.lb-scale')||{}).textContent || ''`);
  check('双指捏合不小于 100%', (afterPinchIn || '').trim() === '100%', afterPinchIn);

  await cdp.eval(`document.querySelector('.lb-close').click(); true`);
  await sleep(300);

  ws.close();
  const failed = results.filter((r) => !r.pass);
  console.log(`\n结论：${results.length - failed.length}/${results.length} 通过`);
  console.log('演示卡 id =', created.id);
  if (failed.length) {
    console.log('失败项：' + failed.map((f) => f.label).join('; '));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
