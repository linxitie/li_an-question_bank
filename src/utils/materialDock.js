/**
 * 题组材料吸顶面板（教师端/管理端详情弹窗共用）
 * 说明：.vtj 的 raw 页面模板由用户在设计器维护，脚本层通过 DOM 挂载面板，
 * 避免直接修改 <template> 触发 raw 页保护。
 */

const LABEL_RE = /(^|\n|>)([ \t]*(?:材料|给定资料|资料)[ \t]*[0-9一二三四五六七八九十]+)[ \t]*[：:]?/g;

// 材料分段标注：只处理行首/段首的“材料一/资料二”，避免误伤正文中的同名词
export function formatMaterialHtml(html) {
  const source = String(html || '');
  return source.replace(LABEL_RE, function (_m, prefix, label) {
    return prefix + '<span class="qm-label">' + label.trim() + '</span>';
  });
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
