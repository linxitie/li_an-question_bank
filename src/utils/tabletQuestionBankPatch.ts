/**
 * 平板题库布局补丁（2026-11-23，路径 A：零 .vtj 模板改动）。
 *
 * 平板原页是静态壳（todayCount=18 / accuracy=70.2 / 总题=1289、假分页）；
 * 这里把统计替换成真实 /api/stats/dashboard，任务列表与快捷工具注入分类下方，
 * 错题本移到「联考小智」同一行，右侧统计拉长贴底。
 */
let styleInjected = false;
let applied = false;
let loading = false;

function ensureStyle() {
  if (styleInjected) return;
  styleInjected = true;
  const style = document.createElement('style');
  style.id = 'la-tablet-qb-style';
  style.textContent = [
    '.la-tq-card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(26,54,95,.04);margin-top:16px}',
    '.la-tq-bottom{display:grid;grid-template-columns:2fr 1fr;gap:10px;align-items:start}',
    '.la-tq-bottom .la-tq-card{margin-top:16px}',
    '.la-tq-bottom .la-tq-tools{grid-template-columns:1fr}',
    '.la-tq-card h3{margin:0 0 10px;font-size:15px;color:#1A365D}',
    '.la-tq-task{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #f1f4f9;font-size:13px;color:#33415c}',
    '.la-tq-task:last-child{border-bottom:none}',
    '.la-tq-task b{color:#1A365D;font-weight:600}',
    '.la-tq-meta{color:#8899aa;font-size:12px;white-space:nowrap}',
    '.la-tq-tools{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}',
    '.la-tq-tool{border:1px solid #e3e8f2;border-radius:10px;padding:10px 6px;text-align:center;cursor:pointer;font-size:13px;color:#1A365D;background:#fff}',
    '.la-tq-tool:hover{background:#f7f9fd}',
    '.right-panel.la-tq-stretch{position:sticky;top:84px;align-self:start;height:calc(100vh - 108px)}',
    '@media (max-width:900px){.right-panel.la-tq-stretch{position:static;height:auto}}'
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
    const values = [
      fmt(d.todayQuestions),
      (Number(d.accuracyRate || 0).toFixed(1) + '%'),
      fmt(d.totalQuestions),
      fmt(d.streakDays)
    ];
    document.querySelectorAll('.stats-grid .stat-value').forEach((el, i) => {
      if (values[i] !== undefined) el.textContent = values[i];
    });
  } catch {
    /* 统计失败保留原值 */
  }
}

async function fillTasks(): Promise<void> {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth?.apiFetch) return;
  try {
    const res = await auth.apiFetch('/api/tasks/overview');
    if (!res.ok) return;
    const d = await res.json();
    const weekly: any[] = Array.isArray(d.weekly) ? d.weekly : [];
    if (!weekly.length) return;
    const card = document.createElement('div');
    card.className = 'la-tq-card la-tq-tasks';
    const title = document.createElement('h3');
    title.textContent = '任务列表 · 本周';
    card.appendChild(title);
    weekly.slice(0, 8).forEach((t) => {
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
    const bottom = getBottom();
    // 任务列表必须排在左（2fr），快捷工具在右（1fr）。
    if (bottom) bottom.insertBefore(card, bottom.firstChild);
  } catch {
    /* 任务失败不阻塞 */
  }
}

function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));
}

function getBottom(): HTMLElement | null {
  const left = document.querySelector('.left-panel');
  if (!left) return null;
  let bottom = left.querySelector('.la-tq-bottom') as HTMLElement | null;
  if (!bottom) {
    bottom = document.createElement('div');
    bottom.className = 'la-tq-bottom';
    left.appendChild(bottom);
  }
  return bottom;
}

function addTools(): void {
  const bottom = getBottom();
  if (!bottom || bottom.querySelector('.la-tq-tools-card')) return;
  const card = document.createElement('div');
  card.className = 'la-tq-card la-tq-tools-card';
  const title = document.createElement('h3');
  title.textContent = '快捷工具';
  card.appendChild(title);
  const grid = document.createElement('div');
  grid.className = 'la-tq-tools';
  const tools = [
    ['笔记', '#/tablet/notes'],
    ['收藏', '#/tablet/favorites'],
    ['成绩分析', '#/tablet/score-analysis']
  ];
  tools.forEach(([label, href]) => {
    const btn = document.createElement('div');
    btn.className = 'la-tq-tool';
    btn.textContent = label;
    btn.addEventListener('click', () => { window.location.hash = href; });
    grid.appendChild(btn);
  });
  card.appendChild(grid);
  bottom.appendChild(card);
}

function moveWrongbook(): void {
  const items = Array.from(document.querySelectorAll('.action-card .action-item')) as HTMLElement[];
  const wrong = items.find((el) => (el.textContent || '').includes('错题本') || (el.textContent || '').includes('错题集'));
  const ai = items.find((el) => (el.textContent || '').includes('联考小智'));
  if (wrong && ai && wrong !== ai) {
    ai.parentElement?.insertBefore(wrong, ai.nextSibling);
  }
}

export function applyTabletQuestionBankPatch(): void {
  if (loading || applied) return;
  const page = document.querySelector('.tablet-question-bank-page');
  if (!page) return;
  loading = true;
  ensureStyle();
  moveWrongbook();
  addTools();
  const right = document.querySelector('.right-panel') as HTMLElement | null;
  if (right) right.classList.add('la-tq-stretch');
  void fillStats();
  void fillTasks();
  // 页面可能还没渲染完 left-panel：没挂上就下次扫描再试。
  applied = !!document.querySelector('.left-panel') && !!right;
  loading = false;
}
