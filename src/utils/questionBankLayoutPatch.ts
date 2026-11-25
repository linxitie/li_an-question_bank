/**
 * 题库 PC 版布局补丁 V2（2026-11-24，零 .vtj 模板改动）。
 *
 * 目标布局（对齐用户截图）：
 * 1) 顶部动作行全宽：快速练习 / 历年试卷 / 智能组卷 / 学习计划 / 联考小智；
 * 2) 第二行工具条全宽且均匀分布：小模考 / 院校联考机考系统 / 笔记 / 收藏 / 成绩分析 / 错题本，搜索靠右；
 * 3) 三列主体：左任务列表 / 中科目 tabs + 题目分类 / 右练习统计。
 *
 * 只改容器和位置，不重写卡片 padding/圆角/字号；错题本复用 tool-item 克隆以保留 scoped 样式。
 */
let styleInjected = false;

function ensureStyle() {
  if (styleInjected) return;
  styleInjected = true;
  const style = document.createElement('style');
  style.id = 'la-qb-v2-style';
  style.textContent = [
    /* 顶动作行均分（卡片内边距/圆角不变，只分配宽度） */
    '.la-qb-v2 .action-scroll .action-btn{flex:1 1 0;justify-content:center;min-width:0}',
    /* 第二行工具条 */
    '.la-qb-tools-row{display:flex;align-items:center;gap:10px;margin:0 0 16px;padding:0;background:transparent;box-shadow:none}',
    '.la-qb-tools-row .sub-btn,.la-qb-tools-row .tool-item{flex:1 1 0;min-width:0;justify-content:center;height:44px;border:1px solid #e8eaf0;border-radius:10px;background:#fff;padding:0 10px;box-shadow:0 2px 10px rgba(26,43,95,.04);font-size:13px;font-weight:600;color:#1a2b5f}',
    '.la-qb-tools-row .tool-item{cursor:pointer;display:flex;flex-direction:row;align-items:center;justify-content:center;gap:8px}',
    '.la-qb-tools-row .tool-item span{white-space:nowrap}',
    '.la-qb-tools-row .sub-btn:hover,.la-qb-tools-row .tool-item:hover{border-color:#c41e3a}',
    '.la-qb-tools-row .search-box{flex:0 0 210px;margin-left:auto;height:44px;box-sizing:border-box}',
    '.la-qb-tools-row .la-qb-search-wrap{margin-left:auto;flex:0 0 210px;display:flex}',
    /* 宽屏容器：三列需要更宽，卡片本身参数不变 */
    '.la-qb-v2 .qb-main{max-width:1600px}',
    /* 平板/触控设备：题目分类 2 列（PC 保持 3 列） */
    '.la-qb-v2.la-touch .subcategory-grid{grid-template-columns:repeat(2,minmax(0,1fr))}',
    /* 三列主体 */
    '.qb-body.la-qb3-grid{display:grid;grid-template-columns:340px minmax(0,1fr) 360px;gap:20px;align-items:start}',
    '.la-qb-tasks{position:sticky;top:84px;overflow:hidden;min-width:0;display:flex;flex-direction:column}',
    '.la-qb-tasks .goal-card{width:100%;height:100%;display:flex;flex-direction:column;min-height:0}',
    '.la-qb-tasks .goal-card .goal-content{flex:1 1 auto;min-height:0;overflow-y:auto}',
    '.qb-body.la-qb3-grid .qb-right{position:sticky;top:84px;align-self:start;display:flex;flex-direction:column}',
    '.qb-body.la-qb3-grid .qb-right .right-card{flex:1 1 auto;min-height:0;overflow-y:auto}',
    '.qb-body.la-qb3-grid .qb-left{min-width:0}',
    '@media (min-width:1101px) and (max-width:1400px){.qb-body.la-qb3-grid{grid-template-columns:262px minmax(0,1fr) 289px;gap:16px}}',
    '@media (max-width:1100px){.qb-body.la-qb3-grid{grid-template-columns:280px minmax(0,1fr)}.qb-body.la-qb3-grid .qb-right{grid-column:2;position:static;max-height:none}}'
  ].join('\n');
  document.head.appendChild(style);
}

function makeWrongbookTool(source: HTMLElement | null): HTMLElement {
  const item = (source || document.createElement('div')).cloneNode(true) as HTMLElement;
  item.classList.add('tool-item', 'la-qb-wrongbook');
  item.removeAttribute('data-la-wrongbook');
  item.textContent = '';
  item.innerHTML = '<span class="action-icon" style="font-size:18px">📕</span><span class="la-qb-wrongbook-label">错题本</span>';
  // 克隆节点保留 .vtj scoped 的 data-v-*，新插入的子节点也要带上，否则字号/颜色样式不生效。
  const scopeAttr = Array.from(item.attributes).find((a) => a.name.startsWith('data-v-'))?.name;
  if (scopeAttr) {
    item.querySelectorAll('span').forEach((el) => el.setAttribute(scopeAttr, ''));
  }
  item.addEventListener('click', () => {
    window.location.hash = '#/page/wrong_questions';
  });
  return item;
}

function buildToolsRow(top: HTMLElement, tools: HTMLElement | null): HTMLElement {
  const row = document.createElement('div');
  row.className = 'la-qb-tools-row';
  row.dataset.laQbTools = '1';

  const subActions = top.querySelector('.qb-sub-actions') as HTMLElement | null;
  // 小模考、院校联考机考系统
  if (subActions) {
    Array.from(subActions.querySelectorAll('.sub-btn')).forEach((el) => row.appendChild(el));
  }

  // 笔记 / 收藏 / 成绩分析
  const toolGrid = tools?.querySelector('.tools-grid') as HTMLElement | null;
  let firstTool: HTMLElement | null = null;
  if (toolGrid) {
    Array.from(toolGrid.querySelectorAll('.tool-item')).forEach((el) => {
      const text = (el.textContent || '').trim();
      // 旧快捷工具里可能已有「错题集/错题本」，统一由下方新按钮承担，避免重复。
      if (text.includes('错题集') || text.includes('错题本')) {
        el.remove();
        return;
      }
      firstTool = firstTool || (el as HTMLElement);
      row.appendChild(el);
    });
  }

  // 错题本（截图中在工具条内，不在顶部动作行）
  row.appendChild(makeWrongbookTool(firstTool));

  // 搜索保持在最右
  const search = subActions?.querySelector('.search-box') as HTMLElement | null;
  if (search) row.appendChild(search);

  // 工具条占满宽度，插到动作行与三列主体之间
  const main = top.parentElement;
  if (main) main.insertBefore(row, top.nextSibling);
  return row;
}

let resizeBound = false;

function fitColumnsHeight(): void {
  const body = document.querySelector('.qb-body.la-qb3-grid') as HTMLElement | null;
  const left = body?.querySelector('.la-qb-tasks') as HTMLElement | null;
  const right = body?.querySelector('.qb-right') as HTMLElement | null;
  if (!body || !left || !right) return;
  if (window.innerWidth < 1101) {
    left.style.height = '';
    left.style.maxHeight = '';
    right.style.height = '';
    right.style.maxHeight = '';
    return;
  }
  const top = Math.round(body.getBoundingClientRect().top);
  const height = Math.max(420, Math.round(window.innerHeight - top - 16));
  left.style.height = height + 'px';
  left.style.maxHeight = height + 'px';
  right.style.height = height + 'px';
  right.style.maxHeight = height + 'px';
}

export function applyQuestionBankLayout(): void {
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash.startsWith('/page/question_bank')) return;
  const main = document.querySelector('.qb-main') as HTMLElement | null;
  const body = document.querySelector('.qb-body') as HTMLElement | null;
  const top = document.querySelector('.qb-top') as HTMLElement | null;
  if (!main || !body || !top) return;
  ensureStyle();
  const qbRoot = document.querySelector('.question-bank');
  qbRoot?.classList.add('la-qb-v2');
  // 只认主指针为 coarse（平板/触屏）；Windows 触屏笔记本的 maxTouchPoints 也可能是 10，
  // 单看 maxTouchPoints 会把 PC 误判成平板。
  const isTouch = window.matchMedia('(pointer: coarse)').matches;
  if (isTouch) qbRoot?.classList.add('la-touch');

  // 清理 V1：把任务/工具从 la-qb-bottom 取出，移除旧包装和旧顶部错题本按钮
  const oldBottom = main.querySelector('.la-qb-bottom') as HTMLElement | null;
  let goal = main.querySelector('.goal-card') as HTMLElement | null;
  let tools = main.querySelector('.quick-tools') as HTMLElement | null;
  if (oldBottom) {
    goal = oldBottom.querySelector('.goal-card') || goal;
    tools = oldBottom.querySelector('.quick-tools') || tools;
    oldBottom.remove();
  }
  main.querySelectorAll('[data-la-wrongbook="1"]').forEach((el) => el.remove());

  // 工具行只构建一次
  let toolsRow = main.querySelector('[data-la-qb-tools="1"]') as HTMLElement | null;
  if (!toolsRow) {
    toolsRow = buildToolsRow(top, tools);
    // 已被搬空的快捷工具卡不再占位
    if (tools) tools.remove();
  }

  // 左任务列
  if (goal) {
    let left = body.querySelector('.la-qb-tasks') as HTMLElement | null;
    if (!left) {
      left = document.createElement('div');
      left.className = 'la-qb-tasks';
      body.insertBefore(left, body.firstChild);
    }
    if (goal.parentElement !== left) left.appendChild(goal);
  }

  body.classList.add('la-qb3-grid');
  fitColumnsHeight();
  if (!resizeBound) {
    resizeBound = true;
    window.addEventListener('resize', () => fitColumnsHeight());
  }
}
