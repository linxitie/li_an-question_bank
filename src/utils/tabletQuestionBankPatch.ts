/**
 * 平板题库布局补丁 V2（2026-11-24，零 .vtj 模板改动）。
 *
 * 目标：顶部动作行全宽 → 左侧任务列表 / 中间科目分类+考点树+题目列表 / 右侧统计。
 * 只移动节点和容器，不重写卡片 padding/圆角/字号。
 */
let styleInjected = false;
let applied = false;
let loading = false;

function ensureStyle() {
  if (styleInjected) return;
  styleInjected = true;
  const style = document.createElement('style');
  style.id = 'la-tablet-qb-v2-style';
  style.textContent = [
    '.la-tq-top{display:flex;gap:10px;align-items:stretch;padding:16px 20px 0}',
    '.la-tq-top .action-card{display:flex;gap:10px;flex-wrap:wrap;flex:1;padding:12px;margin:0}',
    '.la-tq-top .action-card .action-item{flex:1 1 0;min-width:0;padding:12px}',
    '.la-tq-top .action-card .action-desc{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.la-tq-tasks{position:sticky;top:84px;max-height:calc(100vh - 108px);overflow-y:auto}',
    '.la-tq-card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(26,54,95,.04)}',
    '.la-tq-card h3{margin:0 0 10px;font-size:15px;color:#1A365D}',
    '.la-tq-task{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #f1f4f9;font-size:13px;color:#33415c}',
    '.la-tq-task:last-child{border-bottom:none}',
    '.la-tq-task b{color:#1A365D;font-weight:600}',
    '.la-tq-meta{color:#8899aa;font-size:12px;white-space:nowrap}',
    '.right-panel.la-tq-stretch{position:sticky;top:84px;align-self:start;max-height:calc(100vh - 108px);overflow-y:auto}',
    '@media (max-width:999px){.tablet-question-bank-page .main-content{grid-template-columns:240px minmax(0,1fr)}.tablet-question-bank-page .main-content .right-panel{grid-column:2;position:static;max-height:none}.la-tq-tasks{max-height:none;position:static}}'
  ].join('\n');
  document.head.appendChild(style);
}

function fmt(v: any): string {
  return v === null || v === undefined ? '0' : String(v);
}

async function fillStats(): Promise<void> {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth?.apiFetch) return;
  try {
    const res = await auth.apiFetch('/api/stats/dashboard');
    if (!res.ok) return;
    const d = await res.json();
    const values = [fmt(d.todayQuestions), Number(d.accuracyRate || 0).toFixed(1) + '%', fmt(d.totalQuestions), fmt(d.streakDays)];
    document.querySelectorAll('.stats-grid .stat-value').forEach((el, i) => {
      if (values[i] !== undefined) el.textContent = values[i];
    });
  } catch {
    /* 保留原值 */
  }
}

function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));
}

async function fillTasks(): Promise<void> {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth?.apiFetch) return;
  try {
    const res = await auth.apiFetch('/api/tasks/overview');
    if (!res.ok) return;
    const d = await res.json();
    const weekly: any[] = Array.isArray(d.weekly) ? d.weekly : [];
    const left = document.querySelector('.left-panel') as HTMLElement | null;
    if (!left) return;
    left.querySelectorAll('.la-tq-card').forEach((el) => el.remove());
    const card = document.createElement('div');
    card.className = 'la-tq-card la-tq-tasks-card';
    const title = document.createElement('h3');
    title.textContent = '任务列表 · 本周';
    card.appendChild(title);
    (weekly.length ? weekly : []).slice(0, 8).forEach((t) => {
      const row = document.createElement('div');
      row.className = 'la-tq-task';
      const name = document.createElement('span');
      name.innerHTML = '<b>' + escapeHtml(t.title || '') + '</b>';
      const meta = document.createElement('span');
      meta.className = 'la-tq-meta';
      meta.textContent = fmt(t.current) + '/' + fmt(t.threshold) + ' · +' + fmt(t.reward_coins) + '金币';
      row.appendChild(name);
      row.appendChild(meta);
      card.appendChild(row);
    });
    if (!weekly.length) {
      const empty = document.createElement('div');
      empty.className = 'la-tq-task';
      empty.textContent = '暂无本周任务';
      card.appendChild(empty);
    }
    left.appendChild(card);
  } catch {
    /* 任务失败不阻塞 */
  }
}

function moveActionCard(main: HTMLElement): void {
  const actionCard = document.querySelector('.left-panel .action-card') as HTMLElement | null;
  if (!actionCard) return;
  let top = main.parentElement?.querySelector('.la-tq-top') as HTMLElement | null;
  if (!top && main.parentElement) {
    top = document.createElement('div');
    top.className = 'la-tq-top';
    main.parentElement.insertBefore(top, main);
  }
  if (top && actionCard.parentElement !== top) top.appendChild(actionCard);
}

function moveCategoryAndTree(main: HTMLElement): void {
  const center = main.querySelector('.center-content') as HTMLElement | null;
  if (!center) return;
  const category = main.querySelector('.left-panel .category-card') as HTMLElement | null;
  const tree = main.querySelector('.left-panel .tree-card') as HTMLElement | null;
  [tree, category].forEach((el) => {
    if (!el) return;
    if (el.parentElement !== center) center.insertBefore(el, center.firstChild);
  });
}

export function applyTabletQuestionBankPatch(): void {
  if (loading || applied) return;
  const page = document.querySelector('.tablet-question-bank-page');
  const main = document.querySelector('.main-content') as HTMLElement | null;
  if (!page || !main) return;
  loading = true;
  ensureStyle();
  moveActionCard(main);
  moveCategoryAndTree(main);
  const right = main.querySelector('.right-panel') as HTMLElement | null;
  const left = main.querySelector('.left-panel') as HTMLElement | null;
  if (right) right.classList.add('la-tq-stretch');
  if (left) left.classList.add('la-tq-tasks');
  void fillStats();
  void fillTasks();
  applied = !!left && !!right && !!main.querySelector('.center-content');
  loading = false;
}
