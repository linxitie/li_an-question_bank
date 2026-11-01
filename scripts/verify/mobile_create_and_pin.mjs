/**
 * 二轮验收（真实登录态 + 手机视口）：
 *  1) 徽章「设为精选」后的金色五角星（徽章页左上角 / 弹层右侧）+ 按钮文案切换
 *  2) 手机端学生「创建卡片」：选科目 → 填字段 + 1~2 张配图 → 保存立即公开
 *
 * 依赖：前端 9527（DEV_BACKEND_ORIGIN=http://127.0.0.1:8010）、后端 8010、
 *       Chrome 远程调试 9222。SPA 内跳转一律用 location.hash，避免重新 boot 丢登录态。
 *
 * 注意：脚本会真实写入 1 张申论卡片（内容固定，便于比对效果图）。重复执行前先清理，
 *       否则同内容会命中后端去重返回 409：
 *         python scripts/verify/cleanup_test_materials.py
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8010';
const OUT = resolve('docs/plans/assets/备考资料_二轮验收');
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
  async waitFor(expr, timeoutMs = 15000) {
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
    const png = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(png.data, 'base64'));
    console.log('  ✓', name);
  }
}

const results = [];
const check = (label, pass, extra = '') => {
  results.push({ label, pass, extra });
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
  await cdp.send('DOM.enable');
  // 手机视口（iPhone 12/13 逻辑分辨率）
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

  // ========== 1. 徽章精选星标 ==========
  await cdp.eval(`location.hash = '#/badges'; true`);
  const okGrid = await cdp.waitFor(`document.querySelectorAll('.bg-card').length > 0`);
  await sleep(600);
  const starInfo = await cdp.eval(`(() => ({
    cards: document.querySelectorAll('.bg-card').length,
    stars: document.querySelectorAll('.bg-pin-star').length,
    pinnedNames: [...document.querySelectorAll('.bg-pin-star')].map(s => s.closest('.bg-card').querySelector('.bg-name').textContent.trim()),
    vtjLink: !!document.querySelector('#vtjLink'),
    vtjLinkVisible: (() => { const el = document.querySelector('#vtjLink'); return !!el && getComputedStyle(el).display !== 'none'; })()
  }))()`);
  console.log('徽章页', JSON.stringify(starInfo));
  check('徽章页出现精选星标', okGrid && starInfo.stars === 2, `stars=${starInfo.stars} ${starInfo.pinnedNames.join('/')}`);
  check('右下角铅笔悬浮按钮已移除', starInfo.vtjLinkVisible === false, `#vtjLink=${starInfo.vtjLink} visible=${starInfo.vtjLinkVisible}`);

  // 三列网格不得横向溢出（旧实现右边界 403 > 390，第 3 列被裁）
  const overflow = await cdp.eval(`(() => {
    let worst = 0;
    document.querySelectorAll('.bg-card').forEach((el) => {
      worst = Math.max(worst, el.getBoundingClientRect().right);
    });
    return { inner: window.innerWidth, worst: Math.round(worst) };
  })()`);
  check('徽章三列不横向溢出', overflow.worst <= overflow.inner + 0.5,
    `right=${overflow.worst} inner=${overflow.inner}`);
  await cdp.shot('01_徽章页_精选星标');

  // 打开已精选徽章（初来乍到）的详情弹层
  const opened = await cdp.eval(`(() => {
    const card = [...document.querySelectorAll('.bg-card')].find(c => c.querySelector('.bg-pin-star'));
    if (!card) return false; card.click(); return true;
  })()`);
  await cdp.waitFor(`!!document.querySelector('.dm-card')`);
  await sleep(350);
  const modalInfo = await cdp.eval(`(() => ({
    name: (document.querySelector('.dm-name')||{}).textContent || '',
    hasStar: !!document.querySelector('.dm-pin-col .pin-star'),
    btn: (document.querySelector('.dm-btn-pin')||{}).textContent || ''
  }))()`);
  console.log('弹层', JSON.stringify(modalInfo));
  check('弹层显示精选星标', opened && modalInfo.hasStar === true, `name=${modalInfo.name}`);
  check('弹层按钮文案为「取消精选」', modalInfo.btn === '取消精选', `btn=${modalInfo.btn}`);
  await cdp.shot('02_徽章弹层_精选星标');

  // 取消精选 → 星标减少、按钮变回「设为精选」
  await cdp.eval(`document.querySelector('.dm-btn-pin').click(); true`);
  const offOk = await cdp.waitFor(`(document.querySelector('.dm-btn-pin')||{}).textContent === '设为精选'`, 15000);
  await sleep(400);
  const afterOff = await cdp.eval(`(() => ({
    btn: (document.querySelector('.dm-btn-pin')||{}).textContent || '',
    modalStar: !!document.querySelector('.dm-pin-col .pin-star'),
    gridStars: document.querySelectorAll('.bg-pin-star').length
  }))()`);
  console.log('取消精选后', JSON.stringify(afterOff));
  check('取消精选：按钮文案回退', offOk && afterOff.btn === '设为精选', `btn=${afterOff.btn}`);
  check('取消精选：星标同步消失', afterOff.modalStar === false && afterOff.gridStars === 1, `grid=${afterOff.gridStars}`);

  // 重新设为精选，恢复现场
  await cdp.eval(`document.querySelector('.dm-btn-pin').click(); true`);
  const onOk = await cdp.waitFor(`(document.querySelector('.dm-btn-pin')||{}).textContent === '取消精选'`, 15000);
  await sleep(400);
  const afterOn = await cdp.eval(`(() => ({
    btn: (document.querySelector('.dm-btn-pin')||{}).textContent || '',
    modalStar: !!document.querySelector('.dm-pin-col .pin-star'),
    gridStars: document.querySelectorAll('.bg-pin-star').length
  }))()`);
  check('重新设为精选：星标与文案恢复', onOk && afterOn.modalStar && afterOn.gridStars === 2, JSON.stringify(afterOn));
  await cdp.eval(`document.querySelector('.dm-close').click(); true`);
  await sleep(300);

  // ========== 2. 手机端创建卡片 ==========
  await cdp.eval(`location.hash = '#/mobile/materials'; true`);
  const okList = await cdp.waitFor(`!!document.querySelector('.create-btn')`);
  await sleep(800);
  const btnInfo = await cdp.eval(`(() => {
    const b = document.querySelector('.create-btn');
    const tb = document.querySelector('.topbar').getBoundingClientRect();
    const r = b ? b.getBoundingClientRect() : null;
    return { text: b ? b.textContent.trim() : '', rect: r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] : null,
             topbar: [Math.round(tb.width), Math.round(tb.height)],
             overlap: r ? document.elementsFromPoint(r.x + r.width/2, r.y + r.height/2).some(el => el.closest('.mtb-bar')) : null };
  })()`);
  console.log('创建按钮', JSON.stringify(btnInfo));
  check('手机端出现「创建」按钮且不与底部导航重叠', okList && btnInfo.text.includes('创建') && btnInfo.overlap === false, JSON.stringify(btnInfo.rect));
  await cdp.shot('03_手机端_创建入口');

  // 打开创建弹层 → 选科目
  await cdp.eval(`document.querySelector('.create-btn').click(); true`);
  await cdp.waitFor(`!!document.querySelector('.cc-subjects')`);
  await sleep(350);
  await cdp.shot('04_创建卡片_选科目');

  // 选「申论」 → 填表
  await cdp.eval(`(() => { const b = [...document.querySelectorAll('.cc-subject')].find(x => x.textContent.includes('申论')); b.click(); return true; })()`);
  await cdp.waitFor(`!!document.querySelector('.cc-body')`);
  await sleep(500);

  const filled = await cdp.eval(`(() => {
    const set = (el, v) => {
      el.value = v;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    };
    const tas = document.querySelectorAll('.cc-body textarea');
    set(tas[0], '申论概括题 先分后总答题');
    set(tas[1], '①先划材料总分结构；②圈出高频修饰词；③同类合并后按「一是/二是」重组，最后补一句结论。');
    const selects = document.querySelectorAll('.cc-body select');
    // 分类下拉选第一个真实分类，考点随之联动
    if (selects[0] && selects[0].options.length > 1) set(selects[0], selects[0].options[1].value);
    return { front: tas[0].value, back: tas[1].value, cat: selects[0] ? selects[0].value : '', points: selects[1] ? selects[1].options.length : 0 };
  })()`);
  await sleep(400);
  // 分类选定后考点下拉联动，选第一个考点（这样建出来的卡是完整分类，不会落「通用技巧」）
  const pointPicked = await cdp.eval(`(() => {
    const s = document.querySelectorAll('.cc-body select')[1];
    if (!s || s.options.length < 2) return null;
    s.value = s.options[1].value;
    s.dispatchEvent(new Event('change', { bubbles: true }));
    return s.options[1].textContent.trim();
  })()`);
  await sleep(300);
  console.log('填写', JSON.stringify({ ...filled, point: pointPicked }));

  // 造一张 200x120 的 PNG 注入 file input（避免 CDP 文件路径依赖）
  const imgOk = await cdp.eval(`(async () => {
    const c = document.createElement('canvas'); c.width = 240; c.height = 140;
    const g = c.getContext('2d');
    const grad = g.createLinearGradient(0, 0, 240, 140);
    grad.addColorStop(0, '#1e3a8a'); grad.addColorStop(1, '#60a5fa');
    g.fillStyle = grad; g.fillRect(0, 0, 240, 140);
    g.fillStyle = '#fff'; g.font = 'bold 20px sans-serif'; g.fillText('申论 · 配图示例', 28, 78);
    const blob = await new Promise(r => c.toBlob(r, 'image/png'));
    const dt = new DataTransfer();
    dt.items.add(new File([blob], 'card-1.png', { type: 'image/png' }));
    const input = document.querySelector('.cc-img-add input[type=file]');
    if (!input) return 'no-input';
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 400));
    return document.querySelectorAll('.cc-img img').length;
  })()`);
  check('配图上传（1 张）', Number(imgOk) === 1, `thumbs=${imgOk}`);
  await sleep(300);
  await cdp.shot('05_创建卡片_填写完成');

  // 保存
  await cdp.eval(`[...document.querySelectorAll('.cc-actions .cc-primary')][0].click(); true`);
  const savedOk = await cdp.waitFor(`!document.querySelector('.cc-body')`, 20000);
  await sleep(1600);
  const afterSave = await cdp.eval(`(() => ({
    modalGone: !document.querySelector('.cc-panel'),
    firstCard: (document.querySelector('.list .card .m-title')||{}).textContent || '',
    msg: (document.querySelector('.el-message')||{}).textContent || ''
  }))()`);
  console.log('保存后', JSON.stringify(afterSave));
  check('保存成功并关闭弹层', savedOk && afterSave.modalGone === true);
  check('列表首条为新卡片', afterSave.firstCard.includes('申论概括题'), afterSave.firstCard);
  await cdp.shot('06_创建后_列表首条');

  // ========== 3. 桌面端「创建卡片」页（学生端已无 Excel 上传入口） ==========
  await sleep(3200); // 等手机端的 success toast 消失，避免串进桌面图
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  await cdp.eval(`location.hash = '#/materials/upload'; true`);
  const okPage = await cdp.waitFor(`!!document.querySelector('.cc-panel.is-inline')`, 15000);
  await sleep(700);
  const pageInfo = await cdp.eval(`(() => ({
    title: (document.querySelector('.mc-head h1')||{}).textContent || '',
    hasXlsxInput: !!document.querySelector('input[type=file][accept*="xlsx"]'),
    hasOldDrop: !!document.querySelector('.mu-drop'),
    inlineForm: !!document.querySelector('.cc-panel.is-inline')
  }))()`);
  console.log('桌面建卡页', JSON.stringify(pageInfo));
  check('桌面端为「创建卡片」表单页', okPage && pageInfo.title === '创建卡片' && pageInfo.inlineForm);
  check('学生端不再有 Excel 上传控件', pageInfo.hasXlsxInput === false && pageInfo.hasOldDrop === false);
  await cdp.shot('11_学生端_创建卡片页_桌面');

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
