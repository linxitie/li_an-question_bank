/**
 * 三轮验收（PC / 真实登录态）：
 *  1) 资料页「返回首页」不再镜像 + 顶栏下方出现「创建卡片 / Excel 批量导入」入口
 *  2) 创建页两种方式并存（逐张创建 / Excel 批量导入），Excel 走真实接口
 *  3) 卡片详情配图可点开「全图查看器」（含一卡两图的第 2 张）
 *
 * 依赖：前端 9527（DEV_BACKEND_ORIGIN=http://127.0.0.1:8000）、后端 8000、Chrome 调试端口 9222。
 * 会写入：1 张演示卡（2 张图，申论，免审批）+ 一次 Excel 导入（下架态，5 条）。
 * 清理：python scripts/verify/cleanup_test_materials.py --creator 3 之后按提示删下架行，
 *      或直接跑 _run/_cleanup_round3.py（见文档）。
 */
import http from 'node:http';
import zlib from 'node:zlib';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WebSocket } from 'ws';

const PORT = 9222;
const BASE = 'http://localhost:9527';
const API = 'http://127.0.0.1:8000';
const OUT = resolve('docs/plans/assets/备考资料_三轮验收');
const XLSX = resolve('..', '备考资料', '_测试文件', '测试_行测_正常5张.xlsx');
/** 演示配图（由 scripts/verify/gen_demo_images.py 生成；缺失时退化为纯色块） */
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
        fail(new Error(`CDP TIMEOUT ${method} (${timeoutMs}ms)`));
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
    // 兜底说明：窗口被遮挡/后台时 captureScreenshot 可能一直等合成帧。
    // 优先 fromSurface:true（截的是页面，不含浏览器外壳、且遵循 Emulation 尺寸）；
    // 超时才退回 fromSurface:false（截窗口表面，尺寸会跟窗口一致）。
    await this.send('Page.bringToFront', {}, 8000).catch(() => {});
    let data = null;
    try {
      const png = await this.send('Page.captureScreenshot', { format: 'png' }, 20000);
      data = png.data;
    } catch (e) {
      console.warn('  ! fromSurface 截图为默认失败，退回窗口表面：', (e && e.message) || e);
      const png = await this.send(
        'Page.captureScreenshot',
        { format: 'png', fromSurface: false },
        20000
      );
      data = png.data;
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

/** 生成两张纯色 PNG（避免依赖本地图片文件） */
function png(w, h, rgb) {
  const raw = [];
  for (let y = 0; y < h; y++) {
    raw.push(Buffer.from([0]));
    for (let x = 0; x < w; x++) raw.push(Buffer.from(rgb));
  }
  const crcTable = [];
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crcTable[n] = c >>> 0;
  }
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (tag, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(tag), data]);
    const c = Buffer.alloc(4);
    c.writeUInt32BE(crc(body));
    return Buffer.concat([len, body, c]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(Buffer.concat(raw))),
    chunk('IEND', Buffer.alloc(0))
  ]);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const admin = await (
    await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=cbrycc&password=cbrycc'
    })
  ).json();
  const stu = await (
    await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=202516001&password=test123456'
    })
  ).json();

  // 演示卡：两张图（第 1 张进 cover_image，第 2 张进 content），内容带随机后缀避免去重
  const tag = String(Date.now()).slice(-6);
  const demoBytes = (i, w, h, rgb) =>
    existsSync(DEMO_IMG[i]) ? readFileSync(DEMO_IMG[i]) : png(w, h, rgb);
  const fd = new FormData();
  fd.append('subject', 'shenlun');
  fd.append('card_front', `申论综合分析 三步拆解（演示 ${tag}）`);
  fd.append('card_back', '①圈定材料观点；②按主体分层；③给结论并回扣题干。');
  fd.append('category', '综合分析');
  fd.append('images', new Blob([demoBytes(0, 560, 320, [37, 99, 235])], { type: 'image/png' }), 'demo-1.png');
  fd.append('images', new Blob([demoBytes(1, 560, 320, [180, 83, 9])], { type: 'image/png' }), 'demo-2.png');
  const createResp = await fetch(`${API}/api/materials/my/card`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${stu.access_token}` },
    body: fd
  });
  const demo = await createResp.json();
  if (!createResp.ok) throw new Error('演示卡创建失败：' + JSON.stringify(demo));
  console.log('演示卡 id =', demo.id, '图片 =', (demo.images || []).length);

  // 顺带清掉上一次跑脚本遗留的 Excel 导入行（按标题前缀，下架态）
  const adminHdr = { Authorization: `Bearer ${admin.access_token}` };
  const adminList = await (
    await fetch(`${API}/api/materials/admin/list?page=1&page_size=100`, { headers: adminHdr })
  ).json();
  const stale = (adminList.items || []).filter(
    (i) => i.status === 0 && /逻辑填空|图形推理|速算技巧|数字推理|定义判断/.test(i.title || '')
  );
  for (const it of stale) {
    await fetch(`${API}/api/materials/admin/${it.id}`, { method: 'DELETE', headers: adminHdr });
  }
  if (stale.length) console.log('清掉上次导入遗留', stale.length, '条');

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
  await cdp.send('DOM.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });

  await cdp.send('Page.navigate', { url: `${BASE}/#/` });
  await cdp.waitFor(`document.readyState === 'complete'`);
  await sleep(1600);
  await cdp.eval(
    `localStorage.setItem('__VTJ_AUTH_STATE__', ${JSON.stringify(JSON.stringify(state))}); true`
  );
  const lp = await cdp.eval(
    `(async () => { try { await window.__VTJ_AUTH__.login('202516001','test123456'); return 'ok'; } catch(e){ return 'err:'+e.message } })()`
  );
  check('学生登录态注入', lp === 'ok', lp);

  // ===== 1. 资料页：返回首页按钮 + 创建入口 =====
  await cdp.eval(`location.hash = '#/materials/xingce'; true`);
  const okList = await cdp.waitFor(`!!document.querySelector('.mat-page .top-bar')`, 25000);
  await cdp.eval(`location.hash = '#/materials/xingce'; true`); // 触发 hashchange，让入口注入同步
  const okBar = await cdp.waitFor(`!!document.querySelector('#materials-create-bar')`, 15000);
  await sleep(600);
  const head = await cdp.eval(`(() => {
    const back = document.querySelector('.mat-page .top-bar > .back');
    const cs = back ? getComputedStyle(back) : null;
    const bar = document.getElementById('materials-create-bar');
    return {
      backText: back ? back.textContent.trim() : '',
      transform: cs ? cs.transform : '',
      barTexts: bar ? [...bar.querySelectorAll('.mce-btn')].map(b => b.textContent.trim()) : [],
      barRect: bar ? (() => { const r = bar.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })() : null
    };
  })()`);
  console.log('资料页头部', JSON.stringify(head));
  check('资料页渲染', okList);
  check('「返回首页」不再被镜像（transform=none）', (head.transform === 'none' || head.transform === '') && head.backText.includes('返回首页'), `${head.backText} / ${head.transform}`);
  check('顶栏下方出现建卡入口', okBar && head.barTexts.length === 2, JSON.stringify(head.barTexts));
  await cdp.shot('01_PC资料页_返回首页正常且含建卡入口');

  // ===== 2. 创建页：两种方式并存 =====
  await cdp.eval(`[...document.querySelectorAll('#materials-create-bar .mce-btn')].find(b => b.textContent.includes('创建卡片')).click(); true`);
  const okCreate = await cdp.waitFor(`!!document.querySelector('.mc-tabs')`, 20000);
  await sleep(700);
  const tabs = await cdp.eval(`(() => ({
    labels: [...document.querySelectorAll('.mc-tab')].map(t => t.textContent.trim()),
    on: (document.querySelector('.mc-tab.is-on')||{}).textContent || '',
    inlineForm: !!document.querySelector('.cc-panel.is-inline')
  }))()`);
  console.log('创建页', JSON.stringify(tabs));
  check('创建页两种方式并存', okCreate && tabs.labels.length === 2 && tabs.on === '逐张创建', JSON.stringify(tabs.labels));
  await cdp.shot('02_创建页_逐张创建');

  // 切到 Excel 面板
  await cdp.eval(`[...document.querySelectorAll('.mc-tab')].find(t => t.textContent.includes('Excel')).click(); true`);
  await cdp.waitFor(`!!document.querySelector('.mc-excel') && getComputedStyle(document.querySelector('.mc-excel')).display !== 'none'`);
  await sleep(400);
  const excelUi = await cdp.eval(`(() => ({
    hasDrop: !!document.querySelector('.mc-drop input[type=file]'),
    accept: (document.querySelector('.mc-drop input[type=file]')||{}).accept || '',
    quota: [...document.querySelectorAll('.mc-quota-num')].map(e => e.textContent.trim()),
    hash: location.hash
  }))()`);
  console.log('Excel 面板', JSON.stringify(excelUi));
  check('Excel 面板可选文件且参数正确', excelUi.hasDrop && excelUi.accept.includes('xlsx'), excelUi.accept);
  check('切 tab 后 URL 带 ?tab=excel', excelUi.hash.includes('tab=excel'), excelUi.hash);
  await cdp.shot('03_创建页_Excel批量导入');

  // 真实上传
  const doc = await cdp.send('DOM.getDocument', { depth: -1 });
  const node = await cdp.send('DOM.querySelector', {
    nodeId: doc.root.nodeId,
    selector: '.mc-drop input[type=file]'
  });
  if (!node.nodeId) throw new Error('未找到 Excel 文件输入框');
  await cdp.send('DOM.setFileInputFiles', { nodeId: node.nodeId, files: [XLSX] });
  await cdp.waitFor(`!!document.querySelector('.mc-drop.has-file')`);
  await cdp.eval(`document.querySelector('.mc-actions .mc-btn').click(); true`);
  const okResult = await cdp.waitFor(`!!document.querySelector('.mc-result')`, 60000);
  await sleep(600);
  const resText = await cdp.eval(`(() => {
    const r = document.querySelector('.mc-result');
    return { head: (r.querySelector('b')||{}).textContent || '', note: (r.querySelector('.mc-result-note')||{}).textContent || '' };
  })()`);
  console.log('Excel 结果', JSON.stringify(resText));
  check('Excel 导入返回真实结果', okResult && /已提交 \d+ 张/.test(resText.head), resText.head + ' ' + resText.note);
  await cdp.shot('04_创建页_Excel导入结果');

  // ===== 3. 详情页配图 + 全图查看器 =====
  await sleep(3200); // 等 Excel 提交的 toast 消失，避免串进详情页截图
  await cdp.eval(`location.hash = '#/materials/detail?subject=shenlun&id=${demo.id}'; true`);
  const okDetail = await cdp.waitFor(`!!document.querySelector('.md-card-cover img')`, 20000);
  await sleep(900);
  const coverInfo = await cdp.eval(`(() => {
    const box = document.querySelector('.md-card-cover');
    const img = box ? box.querySelector('img') : null;
    return { has: !!img, src: img ? img.getAttribute('src').slice(0, 40) : '', zoomHint: (box ? box.querySelector('.md-zoom') : null) ? true : false };
  })()`);
  console.log('详情配图', JSON.stringify(coverInfo));
  check('详情页显示卡片配图', okDetail && coverInfo.has, coverInfo.src);
  await cdp.shot('05_PC详情页_配图可点');

  await cdp.eval(`document.querySelector('.md-card-cover').click(); true`);
  const okLb = await cdp.waitFor(`!!document.querySelector('.lb-mask')`, 10000);
  await sleep(500);
  const lb1 = await cdp.eval(`(() => ({
    count: (document.querySelector('.lb-count')||{}).textContent || '',
    scale: (document.querySelector('.lb-scale')||{}).textContent || '',
    hasImg: !!document.querySelector('.lb-img')
  }))()`);
  console.log('全图弹层', JSON.stringify(lb1));
  check('点击配图打开全图弹层', okLb && lb1.hasImg && lb1.count.startsWith('1 / 2'), lb1.count);
  await cdp.shot('06_全图查看器_第1张');

  // 下一张 + 放大
  await cdp.eval(`document.querySelector('.lb-next').click(); true`);
  await sleep(350);
  const lb2 = await cdp.eval(`(document.querySelector('.lb-count')||{}).textContent || ''`);
  check('全图弹层可切到第 2 张配图', lb2.trim().startsWith('2 / 2'), lb2);
  await cdp.eval(`[...document.querySelectorAll('.lb-tool')].find(b => b.textContent.trim() === '＋').click(); true`);
  await sleep(300);
  const zoomText = await cdp.eval(`(document.querySelector('.lb-scale')||{}).textContent || ''`);
  check('全图弹层可放大', zoomText.trim() === '125%', zoomText);
  await cdp.shot('07_全图查看器_第2张放大');

  // Esc 关闭
  await cdp.eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); true`);
  await sleep(400);
  const closed = await cdp.eval(`!document.querySelector('.lb-mask')`);
  check('Esc 关闭全图弹层', closed === true);

  ws.close();
  console.log('\n演示卡 id =', demo.id);
  const failed = results.filter((r) => !r.pass);
  console.log(`结论：${results.length - failed.length}/${results.length} 通过`);
  if (failed.length) {
    console.log('失败项：' + failed.map((f) => f.label).join('; '));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error('FAILED:', e.stack || e.message);
  process.exit(1);
});
