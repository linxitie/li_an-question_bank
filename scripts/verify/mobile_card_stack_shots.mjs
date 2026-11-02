/**
 * 手机端卡片栈改版验收：
 *  1) 卡片上直接有「查看配图（N）」/「查看详情」按钮，点开就是全图（不用去下面列表找）
 *  2) 背景不再画整张白卡，只留渐变纸片；卡片无白边
 *  3) 翻页动画期间纸片淡出（不留白框），翻转是 3D 透视
 *
 * 依赖：前端 9527（DEV_BACKEND_ORIGIN=http://127.0.0.1:8010）、后端 8010、Chrome 9222。
 * 会临时建 1 张申论演示卡（2 张配图），跑完可用 cleanup_round3.py 清理。
 */
import http from 'node:http';
import zlib from 'node:zlib';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_四轮验收');
const DEMO_IMG = [
  resolve('docs/plans/assets/备考资料_三轮验收/_素材/demo-img-1.png'),
  resolve('docs/plans/assets/备考资料_三轮验收/_素材/demo-img-2.png')
];
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
  const { readFileSync, existsSync } = await import('node:fs');

  const stu = await (
    await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=202516001&password=test123456'
    })
  ).json();

  // 演示卡：2 张配图（第 1 张 cover，第 2 张进 content）
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
  console.log('演示卡 id =', created.id, '图片 =', (created.images || []).length);

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
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true
  });
  // 打开触摸模拟：让 (pointer: coarse) 生效，全图提示才会走手机文案
  await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 }).catch(() => {});

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

  await cdp.eval(`location.hash = '#/mobile/materials'; true`);
  await cdp.waitFor(`!!document.querySelector('.stack-card')`);
  // 切到申论（演示卡在申论，且是最新一张 → 栈顶）
  await cdp.eval(
    `[...document.querySelectorAll('.tabs .tab')].find(t => t.textContent.includes('申论')).click(); true`
  );
  await cdp.waitFor(`document.querySelector('.card-title') && document.querySelector('.card-title').textContent.includes('演示')`, 15000);
  await sleep(700);

  // ① 结构：后面 3 张真卡片（有正文）、顶层容器透明、底部有操作按钮
  const dom = await cdp.eval(`(() => {
    const top = document.querySelector('.stack-card.lv0');
    const topCs = top ? getComputedStyle(top) : null;
    const behind = [...document.querySelectorAll('.stack-card.behind')];
    const b0 = behind[0];
    const b0Cs = b0 ? getComputedStyle(b0) : null;
    const act = document.querySelector('.card-act');
    const rectOf = el => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width)]; };
    return {
      behindCount: behind.length,
      behindText: b0 ? (b0.querySelector('.card-title') || {}).textContent || '' : '',
      behindBody: b0 ? (b0.querySelector('.card-text') || {}).textContent || '' : '',
      topBg: topCs ? topCs.backgroundColor : '',
      behindBg: b0Cs ? b0Cs.backgroundColor : '',
      faceBg: b0 ? getComputedStyle(b0.querySelector('.card-face')).backgroundColor : '',
      topRect: top ? rectOf(top) : null,
      behindRect: b0 ? rectOf(b0) : null,
      borderWidth: topCs ? topCs.borderTopWidth : '',
      actText: act ? act.textContent.trim() : '',
      title: (document.querySelector('.stack-card.lv0 .card-title') || {}).textContent || ''
    };
  })()`);
  console.log('卡片结构', JSON.stringify(dom));
  check('栈顶是要看的那张卡', dom.title.includes('演示'), dom.title);
  check('后面叠着 3 张真卡片（带正文，不是白板）',
    dom.behindCount === 3 && !!dom.behindText && dom.behindBody.length > 0,
    `${dom.behindText} / ${dom.behindBody.slice(0, 14)}`);
  check('顶层卡容器透明（翻转时不会露白底）', dom.topBg !== 'rgb(255, 255, 255)', dom.topBg);
  check('后面卡片比顶层窄（白身被遮住，无白框）',
    dom.behindRect && dom.topRect && dom.behindRect[2] < dom.topRect[2],
    `behind=${dom.behindRect && dom.behindRect[2]} top=${dom.topRect && dom.topRect[2]}`);
  check('卡片没有白边（border=0）', dom.borderWidth === '0px', dom.borderWidth);
  check('卡片上有「查看配图」按钮', /查看配图/.test(dom.actText), dom.actText);
  await cdp.shot('01_卡片_默认态');

  // ② 翻转：3D 透视 + 翻转途中能看到后面卡片的文字
  //    为了让静态截图能停在「翻到一半」，临时把翻转时长拉到 3s（只影响截图，改完即移除）
  await cdp.eval(`(() => {
    const s = document.createElement('style');
    s.id = 'qa-slowflip';
    s.textContent = '.card-inner { transition-duration: 3s !important; }';
    document.head.appendChild(s);
    return true;
  })()`);
  await cdp.eval(`document.querySelector('.stack-card.lv0').click(); true`);
  await sleep(40);
  const midFlip = await cdp.eval(`(() => {
    const b = document.querySelector('.stack-card.behind .card-title');
    const inner = document.querySelector('.card-inner');
    const r = b ? b.getBoundingClientRect() : null;
    return {
      behindText: b ? b.textContent : '',
      behindVisible: r ? (r.width > 0 && r.height > 0) : false,
      innerTransform: inner ? getComputedStyle(inner).transform.slice(0, 22) : ''
    };
  })()`);
  console.log('翻转中', JSON.stringify(midFlip));
  await cdp.shot('02_翻转中_3D透视');
  await sleep(900);
  await cdp.shot('02b_翻转中_后卡文字');
  // 移除临时样式，让翻转正常结束
  await cdp.eval(`document.getElementById('qa-slowflip')?.remove(); true`);
  await sleep(1200);
  check('翻转途中后面卡片的文字可见', midFlip.behindVisible && !!midFlip.behindText, midFlip.behindText);
  const flipped = await cdp.eval(`(() => {
    const inner = document.querySelector('.card-inner');
    return { transform: inner ? getComputedStyle(inner).transform : '', back: (document.querySelector('.card-face.back .card-act')||{}).textContent || '' };
  })()`);
  check('翻转后停在背面（matrix3d）', /matrix3d/.test(flipped.transform), flipped.transform.slice(0, 24));
  await cdp.shot('03_卡片_背面');

  // ③ 卡片上直接看配图
  await cdp.eval(`document.querySelector('.stack-card').click(); true`); // 翻回正面
  await sleep(600);
  await cdp.eval(`document.querySelector('.card-act').click(); true`);
  const okLb = await cdp.waitFor(`!!document.querySelector('.lb-mask')`, 8000);
  await sleep(500);
  const lb = await cdp.eval(`(() => ({
    count: (document.querySelector('.lb-count')||{}).textContent || '',
    hasImg: !!document.querySelector('.lb-img')
  }))()`);
  check('卡片按钮直接打开全图', okLb && lb.hasImg && lb.count.trim().startsWith('1 / 2'), lb.count);
  await cdp.shot('04_卡片配图_全图');
  await cdp.eval(`document.querySelector('.lb-close').click(); true`);
  await sleep(400);

  // ④ 翻页动画期间：纸片淡出、不留白框
  const before = await cdp.eval(`document.querySelector('.card-title').textContent`);
  await cdp.eval(`[...document.querySelectorAll('.stack-bar button')].find(b => b.textContent.includes('下一张')).click(); true`);
  await sleep(90);
  const mid = await cdp.eval(`(() => {
    const slab = document.querySelector('.stack-slab');
    const card = document.querySelector('.stack-card');
    return {
      slabOpacity: slab ? getComputedStyle(slab).opacity : '',
      cardTransform: card ? getComputedStyle(card).transform : '',
      leaving: !!document.querySelector('.stack.is-leaving')
    };
  })()`);
  console.log('翻页中', JSON.stringify(mid));
  check('翻页期间纸片淡出（无白框残留）',
    parseFloat(mid.slabOpacity) < 0.2 || mid.leaving, `opacity=${mid.slabOpacity} leaving=${mid.leaving}`);
  await cdp.shot('05_翻页中_无白框');
  await sleep(700);
  const after = await cdp.eval(`document.querySelector('.card-title').textContent`);
  check('翻页后切到下一张', before !== after, `${before.slice(0, 12)} → ${after.slice(0, 12)}`);
  await cdp.shot('06_翻页后_恢复');

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
