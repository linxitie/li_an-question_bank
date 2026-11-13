/**
 * 三端操作视觉验收（CDP 驱动，无需 Playwright）
 *
 * 用法：
 *   node scripts/verify/three_device_shots.mjs [--port 9222] [--out <目录>] [--base http://localhost:9527]
 *
 * 前置：已用 `--remote-debugging-port=9222` 启动 headless Chrome，且 dev server 在跑。
 * 做的事：按 PC / 平板 / 手机三种视口，打开页面、**真的点一下卡片**（触发详情弹层），
 *        截图并输出「横向是否溢出」的实测值——这才是"操作后"的验收图，不是静态首屏。
 */
import http from 'node:http';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { WebSocket } from 'ws';

const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};

const PORT = Number(getArg('--port', '9222'));
const BASE = getArg('--base', 'http://localhost:9527');
const OUT = resolve(getArg('--out', 'docs/plans/assets/备考资料_三端'));

const DEVICES = [
  { key: 'PC', width: 1440, height: 900, dpr: 1 },
  { key: '平板', width: 834, height: 1112, dpr: 2 },
  { key: '手机', width: 390, height: 844, dpr: 3 },
];

const SCENES = [
  {
    name: '徽章页_详情弹层',
    hash: '#/badges-demo',
    // 点击第一张徽章卡 → 打开详情弹层
    click: '.bg-card',
    wait: 900,
  },
  {
    name: '徽章页_主页墙',
    hash: '#/badges-demo',
    scroll: 520,
    wait: 600,
  },
  {
    name: '上传页',
    hash: '#/materials/upload?demo=1',
    wait: 700,
  },
];

function httpJson(path) {
  return new Promise((ok, fail) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
      res.on('end', () => {
        try {
          ok(JSON.parse(b));
        } catch (e) {
          fail(e);
        }
      });
    }).on('error', fail);
  });
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.id && this.pending.has(msg.id)) {
        const { ok, fail } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? fail(new Error(JSON.stringify(msg.error))) : ok(msg.result);
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((ok, fail) => {
      this.pending.set(id, { ok, fail });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expr) {
    const r = await this.send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    return r?.result?.value;
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const targets = await httpJson('/json');
  const page = targets.find((t) => t.type === 'page');
  if (!page) throw new Error('找不到 page target（Chrome 是否带 --remote-debugging-port 启动？）');

  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((ok, fail) => {
    ws.once('open', ok);
    ws.once('error', fail);
  });
  const cdp = new Cdp(ws);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  mkdirSync(OUT, { recursive: true });
  const report = [];

  for (const dev of DEVICES) {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: dev.width, height: dev.height,
      deviceScaleFactor: dev.dpr, mobile: dev.key !== 'PC',
    });

    for (const scene of SCENES) {
      // 先回空白页：同一 hash 重复 navigate 不会重新加载，会把上一个场景的弹层状态带过来
      await cdp.send('Page.navigate', { url: 'about:blank' });
      await sleep(150);
      await cdp.send('Page.navigate', { url: `${BASE}/${scene.hash}` });
      await sleep(scene.wait || 800);
      if (scene.click) {
        const clicked = await cdp.eval(
          `(() => { const el = document.querySelector(${JSON.stringify(scene.click)});
             if (!el) return false; el.click(); return true; })()`);
        await sleep(600);
        if (!clicked) console.warn(`  ! ${dev.key}/${scene.name}: 未找到 ${scene.click}`);
      }
      if (scene.scroll) {
        await cdp.eval(`window.scrollTo(0, ${scene.scroll}); true`);
        await sleep(300);
      }
      const overflow = await cdp.eval(
        `(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }))()`);
      const shot = await cdp.send('Page.captureScreenshot', { format: 'png' });
      const file = `${OUT}/${dev.key}_${scene.name}.png`;
      mkdirSync(dirname(file), { recursive: true });
      writeFileSync(file, Buffer.from(shot.data, 'base64'));
      const bad = overflow && overflow.sw > overflow.iw + 1;
      report.push({
        device: dev.key, scene: scene.name, file,
        scrollWidth: overflow?.sw, innerWidth: overflow?.iw,
        horizontalOverflow: !!bad,
      });
      console.log(`  ✓ ${dev.key}/${scene.name}: ${overflow?.sw}/${overflow?.iw}` +
        (bad ? '  ← 横向溢出' : ''));
    }
  }

  writeFileSync(`${OUT}/_report.json`,
    JSON.stringify({ generatedAt: new Date().toISOString(), report }, null, 2));
  const bad = report.filter((r) => r.horizontalOverflow);
  console.log(`\n完成 ${report.length} 张；横向溢出 ${bad.length} 处`);
  if (bad.length) bad.forEach((b) => console.log(`  - ${b.device}/${b.scene}`));
  ws.close();
}

main().catch((e) => {
  console.error('FAILED:', e.message);
  process.exit(1);
});
