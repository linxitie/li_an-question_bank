/**
 * 学生手机端首页布局补丁 V1（2026-11-28，零 .vtj 模板改动）。
 *
 * 对齐 mobile.html：问候卡 → 双卡行（本周做题/倒计时）→ 金句 → 警考雷达 → 新闻。
 * - 双卡行采用 HTML 的白卡风格；
 * - 金句/雷达/新闻/顶栏沿用现有组件；
 * - 底部 MobileTabBar 完全不动；
 * - 只隐藏现有「本周学习趋势」和「最近做题记录」，不改任务/业务逻辑。
 */
import { formatPoliceExamDate, getNextPoliceExamDate } from '@/config/policeExam';

let styleInjected = false;

function ensureStyle(): void {
  if (styleInjected) return;
  styleInjected = true;
  const style = document.createElement('style');
  style.id = 'la-mobile-home-style';
  style.textContent = [
    '.la-mobile-v2 .trend-section,.la-mobile-v2 .recent-records{display:none !important}',
    /* 金句卡去掉自身 16px 外边距，与双卡行左右边缘严格对齐 */
    '.la-mobile-v2 .mobile-quote-card{margin-left:0 !important;margin-right:0 !important;width:100% !important;box-sizing:border-box}',
    '.la-mobile-v2 .radar-entry{display:none !important}',
    '.la-mobile-duo{display:grid;grid-template-columns:1.25fr 1fr;gap:12px;align-items:stretch;margin:12px 0}',
    '.la-mobile-week{background:#fff;border-radius:16px;box-shadow:0 4px 14px rgba(20,30,60,.06);padding:14px 14px 10px;display:flex;flex-direction:column}',
    '.la-mobile-week__head{display:flex;justify-content:space-between;align-items:center}',
    '.la-mobile-week__title{font-size:15px;font-weight:800;color:#1a2b5f}',
    '.la-mobile-week__pill{font-size:9.5px;color:#999;border:1px solid #e2e2e6;border-radius:999px;padding:2px 8px}',
    '.la-mobile-week__num{margin-top:10px;font-weight:800;display:flex;align-items:baseline;gap:2px;color:#1a2b5f}',
    '.la-mobile-week__num .big{font-size:30px;line-height:1;letter-spacing:-1px}',
    '.la-mobile-week__num .unit{font-size:12px;font-weight:700;margin-right:3px}',
    '.la-mobile-week__days{margin-top:12px;display:flex;justify-content:space-between}',
    '.la-mobile-wd{display:flex;flex-direction:column;align-items:center;gap:4px}',
    '.la-mobile-wd .box{width:24px;height:24px;border-radius:7px;background:#f0f0f2;display:flex;align-items:center;justify-content:center}',
    '.la-mobile-wd.done .box{background:#4a90e2}',
    '.la-mobile-wd.done .box::after{content:"";width:11px;height:6px;border-left:2.2px solid #fff;border-bottom:2.2px solid #fff;transform:rotate(-45deg) translate(1px,-1px)}',
    '.la-mobile-wd .lb{font-size:10px;color:#888}',
    '.la-mobile-week__foot{margin-top:10px;border-top:1px solid #f2f2f4;padding-top:8px;font-size:10px;color:#aaa;text-align:center}',
    '.la-mobile-count{background:#fff;border-radius:16px;box-shadow:0 4px 14px rgba(20,30,60,.06);padding:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:6px}',
    '.la-mobile-count__title{font-size:12px;color:#888;font-weight:600}',
    '.la-mobile-count__days{font-size:38px;font-weight:800;color:#1e2a5c;line-height:1.1}',
    '.la-mobile-count__days small{font-size:13px;font-weight:700;margin-left:2px}',
    '.la-mobile-count__date{font-size:11px;color:#b0b0b6}',
    '.la-mobile-count__chip{margin-top:2px;font-size:10px;color:#f5222d;background:#fdeeee;border-radius:999px;padding:3px 10px}',
    /* 雷达：图二样式，背景与 hero 卡一致 */
    '.la-mobile-radar{width:100%;box-sizing:border-box;border-radius:16px;background:linear-gradient(135deg,rgb(26,54,93) 0%,rgb(42,82,152) 100%);padding:14px 16px;display:flex;align-items:center;gap:12px;color:#fff;position:relative;overflow:hidden;margin:0 0 12px;text-decoration:none}',
    '.la-mobile-radar::after{content:"";position:absolute;right:-28px;bottom:-48px;width:130px;height:130px;border-radius:50%;border:18px solid rgba(255,255,255,.06)}',
    '.la-mobile-radar__ico{width:38px;height:38px;border-radius:10px;background:rgba(255,255,255,.12);display:flex;align-items:center;justify-content:center;font-size:18px;flex:0 0 auto}',
    '.la-mobile-radar__info{display:flex;flex-direction:column;gap:2px;min-width:0}',
    '.la-mobile-radar__t{font-size:15px;font-weight:700}',
    '.la-mobile-radar__s{font-size:10.5px;opacity:.65;white-space:nowrap}',
    '.la-mobile-radar__go{margin-left:auto;background:#e8342e;border-radius:999px;padding:6px 12px;font-size:11px;font-weight:600;white-space:nowrap;z-index:1}',
    '.la-mobile-data-error{font-size:10px;color:#c41e3a;margin-top:2px;text-align:center}'
  ].join('\n');
  document.head.appendChild(style);
}

function apiFetch(url: string): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  return auth?.apiFetch ? auth.apiFetch(url) : fetch(url);
}

function weekLabelsFromCheckin(data: any): Array<{ label: string; signed: boolean }> {
  const days = Array.isArray(data?.days) ? data.days : [];
  if (days.length === 7) {
    return days.map((d: any) => ({
      label: ['一', '二', '三', '四', '五', '六', '日'][Number(d.dayOfWeek || 0) - 1] || '',
      signed: !!d.signed
    }));
  }
  return ['一', '二', '三', '四', '五', '六', '日'].map((label) => ({ label, signed: false }));
}

function renderWeekCard(card: HTMLElement, weekly: any, checkin: any): void {
  const totalMinutes = Math.round(Number(weekly?.studyHours || 0) * 60);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  const num = card.querySelector('.la-mobile-week__num');
  if (num) {
    num.innerHTML = '<span class="big">' + h + '</span><span class="unit">小时</span>' +
      '<span class="big">' + m + '</span><span class="unit">分钟</span>';
  }
  const days = card.querySelector('.la-mobile-week__days');
  if (days) {
    days.innerHTML = weekLabelsFromCheckin(checkin).map((d) =>
      '<div class="la-mobile-wd ' + (d.signed ? 'done' : '') + '"><span class="box"></span><span class="lb">' + d.label + '</span></div>'
    ).join('');
  }
  const pill = card.querySelector('.la-mobile-week__pill');
  if (pill) pill.textContent = '本周';
}

function renderCountdown(card: HTMLElement): void {
  const info = getNextPoliceExamDate();
  const days = card.querySelector('.la-mobile-count__days');
  const date = card.querySelector('.la-mobile-count__date');
  if (days) days.innerHTML = info.daysLeft + '<small>天</small>';
  if (date) date.textContent = formatPoliceExamDate(info);
}

function buildDuo(): HTMLElement {
  const duo = document.createElement('div');
  duo.className = 'la-mobile-duo';
  duo.innerHTML =
    '<section class="la-mobile-week">' +
      '<div class="la-mobile-week__head"><span class="la-mobile-week__title">本周做题</span><span class="la-mobile-week__pill">统计中</span></div>' +
      '<div class="la-mobile-week__num"><span class="big">—</span><span class="unit">小时</span><span class="big">—</span><span class="unit">分钟</span></div>' +
      '<div class="la-mobile-week__days"></div>' +
      '<div class="la-mobile-week__foot">每日坚持练习，累计答题时长</div>' +
    '</section>' +
    '<section class="la-mobile-count">' +
      '<div class="la-mobile-count__title">公安联考倒计时</div>' +
      '<div class="la-mobile-count__days">—<small>天</small></div>' +
      '<div class="la-mobile-count__date"></div>' +
      '<div class="la-mobile-count__chip">稳住，我们能赢</div>' +
    '</section>';
  return duo;
}

function buildRadar(): HTMLAnchorElement {
  const a = document.createElement('a');
  a.className = 'la-mobile-radar';
  a.href = '#/mobile/recruitment/radar';
  a.innerHTML =
    '<div class="la-mobile-radar__ico">📡</div>' +
    '<div class="la-mobile-radar__info"><div class="la-mobile-radar__t">警考雷达</div>' +
    '<div class="la-mobile-radar__s">招考资讯 · 公告解读 · 一手掌握</div></div>' +
    '<span class="la-mobile-radar__go">进入警考雷达 ›</span>';
  return a;
}

async function hydrate(card: HTMLElement): Promise<void> {
  try {
    const [wRes, cRes] = await Promise.all([
      apiFetch('/api/stats/weekly'),
      apiFetch('/api/stats/weekly-checkin')
    ]);
    const weekly = wRes.ok ? await wRes.json() : {};
    const checkin = cRes.ok ? await cRes.json() : {};
    renderWeekCard(card, weekly, checkin);
  } catch {
    const num = card.querySelector('.la-mobile-week__num');
    if (num) num.innerHTML = '<span style="font-size:13px;color:#999">数据暂不可用</span>';
  }
}

let retryTimer = 0;

function apply(): void {
  if (!window.location.hash.startsWith('#/mobile/home')) return;
  const page = document.querySelector('.mobile-home-page') as HTMLElement | null;
  const userCard = document.querySelector('.user-card');
  const quote = document.querySelector('.mobile-quote-card');
  if (!page || !userCard || !quote) {
    window.clearTimeout(retryTimer);
    retryTimer = window.setTimeout(apply, 200);
    return;
  }
  if (page.dataset.laMobileLayout === '1') return;
  page.dataset.laMobileLayout = '1';
  ensureStyle();
  page.classList.add('la-mobile-v2');

  if (!document.querySelector('.la-mobile-duo')) {
    const duo = buildDuo();
    userCard.insertAdjacentElement('afterend', duo);
    void hydrate(duo);
    renderCountdown(duo.querySelector('.la-mobile-count') as HTMLElement);
  }
  if (!document.querySelector('.la-mobile-radar')) {
    quote.insertAdjacentElement('afterend', buildRadar());
  }
}

export function applyMobileHomeLayout(): void {
  apply();
}
