/**
 * 题库 PC 版布局补丁（2026-11-23，路径 A：零 .vtj 模板改动）。
 *
 * 目标（用户需求 6/7/8/9）：
 * - 任务列表（GoalCard）移到左侧分类下方，占 2/3 宽；
 * - 快捷工具移到左侧，占 1/3 宽（与任务同一行，固定随分类切换不消失）；
 * - 右侧只保留做题统计，sticky 拉长贴底；
 * - 错题本从快捷工具移到顶部「联考小智」动作行。
 */
let styleInjected = false;

function ensureStyle() {
  if (styleInjected) return;
  styleInjected = true;
  const style = document.createElement('style');
  style.id = 'la-qb-layout-style';
  style.textContent = [
    '.qb-right.la-qb-right-stretch{position:sticky;top:84px;align-self:start;height:calc(100vh - 108px);overflow-y:auto;padding-right:2px}',
    '.la-qb-bottom{display:grid;grid-template-columns:2fr 1fr;gap:12px;align-items:start;margin-top:14px}',
    '.la-qb-bottom .goal-card,.la-qb-bottom .quick-tools{margin:0;height:100%}',
    '.la-qb-bottom .quick-tools .right-header{margin-bottom:10px}',
    '@media (max-width:1100px){.la-qb-bottom{grid-template-columns:1fr}.qb-right.la-qb-right-stretch{position:static;height:auto}}'
  ].join('\n');
  document.head.appendChild(style);
}

function makeWrongbookAction(): HTMLButtonElement {
  // 克隆现有动作按钮：.vtj 页的 scoped 样式带 data-v 属性，动态 createElement 拿不到，
  // 会渲染成浏览器默认按钮（灰底黑边）。克隆节点保留 data-v，风格自然一致。
  const source = document.querySelector(
    '.qb-actions .action-scroll .action-btn:not([data-la-wrongbook="1"])'
  ) as HTMLButtonElement | null;
  const btn = source
    ? (source.cloneNode(true) as HTMLButtonElement)
    : document.createElement('button');
  btn.type = 'button';
  btn.className = 'action-btn';
  btn.classList.remove('active');
  btn.dataset.laWrongbook = '1';
  const icon = btn.querySelector('.action-icon');
  const name = btn.querySelector('.action-name');
  if (icon) icon.textContent = '📕';
  else btn.insertAdjacentHTML('afterbegin', '<span class="action-icon">📕</span>');
  if (name) name.textContent = '错题本';
  else btn.insertAdjacentHTML('beforeend', '<span class="action-name">错题本</span>');
  btn.querySelectorAll('.action-tag').forEach((el) => el.remove());
  btn.addEventListener('click', () => {
    window.location.hash = '#/page/wrong_questions';
  });
  return btn;
}

export function applyQuestionBankLayout(): void {
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash.startsWith('/page/question_bank')) return;
  const body = document.querySelector('.qb-body') as HTMLElement | null;
  if (!body) return;
  ensureStyle();
  const left = body.querySelector('.qb-left') as HTMLElement | null;
  const right = body.querySelector('.qb-right') as HTMLElement | null;
  if (!left || !right) return;

  const goal = right.querySelector('.goal-card') as HTMLElement | null;
  const tools = right.querySelector('.quick-tools') as HTMLElement | null;

  if (goal && tools) {
    let bottom = left.querySelector('.la-qb-bottom') as HTMLElement | null;
    if (!bottom) {
      bottom = document.createElement('div');
      bottom.className = 'la-qb-bottom';
      left.appendChild(bottom);
    }
    if (goal.parentElement !== bottom) bottom.appendChild(goal);
    if (tools.parentElement !== bottom) bottom.appendChild(tools);
    right.classList.add('la-qb-right-stretch');

    // 错题本：从快捷工具移到顶部动作行（联考小智同一行）
    const toolGrid = tools.querySelector('.tools-grid');
    if (toolGrid) {
      Array.from(toolGrid.querySelectorAll('.tool-item')).forEach((item) => {
        if ((item.textContent || '').includes('错题集') || (item.textContent || '').includes('错题本')) item.remove();
      });
    }
    const scroller = document.querySelector('.qb-actions .action-scroll') as HTMLElement | null;
    if (scroller && !scroller.querySelector('[data-la-wrongbook="1"]')) {
      scroller.appendChild(makeWrongbookAction());
    }
  }
}
