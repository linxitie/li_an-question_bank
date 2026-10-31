/**
 * 题组材料吸顶面板（教师端/管理端详情弹窗共用）
 * 说明：.vtj 的 raw 页面模板由用户在设计器维护，脚本层通过 DOM 挂载面板，
 * 避免直接修改 <template> 触发 raw 页保护。
 */

const LABEL_RE = /(?:材料|给定资料|资料)[ \t]*[0-9一二三四五六七八九十]+/g;

const MATERIAL_CSS = `
  .qm-material-sep { display: block; margin: 12px 0; border-top: 1px dashed #dbe4f0; }
  .qm-label { display: inline-block; max-width: 100%; margin: 2px 6px 8px 0; padding: 2px 11px;
    border-radius: 999px; background: #e8f0fb; color: #1a3c6d; font-weight: 700;
    font-size: 13px; line-height: 1.7; }
  .qm-material body p { margin: 8px 0; }
  .qm-material img, .qm-material table { max-width: 100%; height: auto; }
`;

export function ensureMaterialStyles(doc) {
  const d = doc || (typeof document !== 'undefined' ? document : null);
  if (!d || d.querySelector('style[data-qm-material]')) return;
  const style = d.createElement('style');
  style.setAttribute('data-qm-material', '1');
  style.textContent = MATERIAL_CSS;
  (d.head || d.documentElement).appendChild(style);
}

// 材料分段：不能像旧实现那样在 HTML 字符串里插 </div>，否则会拆坏 <p>/<table>
// 的嵌套（教师端曾出现材料错位）。这里只遍历文本节点，在「材料N」前插入分隔线、
// 给标签套高亮胶囊，原有标签结构完全不动，因此任何来源的富文本都安全。
export function formatMaterialHtml(html) {
  const source = String(html || '');
  if (!source || source.indexOf('qm-label') >= 0) return source;
  if (typeof document === 'undefined') return source;
  const tpl = document.createElement('template');
  tpl.innerHTML = source;
  const walker = document.createTreeWalker(tpl.content, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  let firstLabel = true;
  nodes.forEach(function (node) {
    const text = node.nodeValue || '';
    LABEL_RE.lastIndex = 0;
    let match;
    let last = 0;
    let frag = null;
    while ((match = LABEL_RE.exec(text))) {
      if (!frag) frag = document.createDocumentFragment();
      if (match.index > last) frag.appendChild(document.createTextNode(text.slice(last, match.index)));
      if (!firstLabel) {
        const sep = document.createElement('span');
        sep.className = 'qm-material-sep';
        frag.appendChild(sep);
      }
      const label = document.createElement('span');
      label.className = 'qm-label';
      label.textContent = match[0];
      frag.appendChild(label);
      last = match.index + match[0].length;
      firstLabel = false;
    }
    if (frag && last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    if (frag && node.parentNode) node.parentNode.replaceChild(frag, node);
  });
  return tpl.innerHTML;
}

export function removeMaterialDock(host, dockClass) {
  if (!host) return;
  const old = host.querySelector('.' + (dockClass || 'qm-dock'));
  if (old && old.parentNode) old.parentNode.removeChild(old);
}

/**
 * @param {HTMLElement} host 滚动容器（.detail-modal / .modal-xlarge）
 * @param {{html:string,title?:string,dockClass?:string}} options
 */
export function mountMaterialDock(host, options) {
  if (!host || !options || !options.html) return null;
  const dockClass = options.dockClass || 'qm-dock';
  ensureMaterialStyles();
  removeMaterialDock(host, dockClass);
  const dock = document.createElement('div');
  dock.className = 'qm-dock ' + dockClass;
  const title = options.title || '📄 本组材料';
  dock.innerHTML =
    '<div class="qm-dock-head"><span class="qm-dock-title">' + title + '</span>' +
    '<button type="button" class="qm-dock-toggle">收起</button></div>' +
    '<div class="qm-dock-body">' + formatMaterialHtml(options.html) + '</div>';
  const style = document.createElement('style');
  style.setAttribute('data-qm-dock', '1');
  style.textContent = `
    .qm-dock { position: sticky; top: 0; z-index: 30; margin: -2px -2px 16px; background: #fff;
      border: 1px solid #e2e8f0; border-left: 3px solid #1a3c6d; border-radius: 8px;
      box-shadow: 0 4px 14px rgba(15,35,70,.08); }
    .qm-dock-head { display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 8px 14px; background: #f7f9fc; border-bottom: 1px solid #e8eef6; border-radius: 8px 8px 0 0; }
    .qm-dock-title { font-size: 13px; font-weight: 700; color: #1a3c6d; }
    .qm-dock-toggle { border: 1px solid #cfdae8; background: #fff; color: #1a3c6d;
      border-radius: 999px; padding: 2px 10px; font-size: 12px; cursor: pointer; }
    .qm-dock-body { max-height: 32vh; overflow: auto; overscroll-behavior: contain;
      padding: 12px 16px; line-height: 1.9; font-size: 15px; color: #334155; white-space: pre-wrap; }
    .qm-dock-body img, .qm-dock-body table { max-width: 100%; height: auto; }
    .qm-dock-body .qm-label { display: block; width: fit-content; max-width: 100%;
      margin: 18px 0 8px; padding: 2px 10px; border-radius: 999px; background: #e8f0fb;
      color: #1a3c6d; font-weight: 700; font-size: 13px; line-height: 1.6; }
    .qm-dock-body .qm-label:first-child { margin-top: 0; }
    @media (prefers-reduced-motion: reduce) { .qm-dock, .qm-dock-toggle { transition: none; } }
  `;
  if (!document.querySelector('style[data-qm-dock]')) document.head.appendChild(style);
  host.insertBefore(dock, host.firstChild);
  const body = dock.querySelector('.qm-dock-body');
  const btn = dock.querySelector('.qm-dock-toggle');
  if (btn && body) {
    btn.addEventListener('click', function () {
      const hidden = body.style.display === 'none';
      body.style.display = hidden ? '' : 'none';
      btn.textContent = hidden ? '收起' : '展开';
    });
  }
  return dock;
}
