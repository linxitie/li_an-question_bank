/**
 * 教师端 / 管理端题目编辑弹窗的富文本预览（script-only）。
 *
 * 背景：teacher_questions.vue 与 admin_questions.vue 都是 raw 页面，按项目红线
 * 不能由 AI 直接改 <template>。但编辑弹窗里的题干、选项、解析、题组材料此前
 * 只以 textarea/纯文本形式出现，<img> 标签会原样显示成字符串，教师无法判断
 * 图片是否挂对、材料是否完整。
 *
 * 本模块在编辑弹窗 DOM 上追加预览块，不改模板结构：
 *   1. 所有 HTML 统一经过 renderQuestionContent 白名单清洗，避免第二套 XSS 缺口；
 *   2. 题组材料隐藏原来的纯文本预览，改为富文本；
 *   3. 选项按 key 逐条渲染，支持选项本身是图片；
 *   4. 答案解析独立预览，不再依赖「实时预览」开关是否展开。
 */
import { renderQuestionContent } from './questionRender';

var STYLE_ID = 'q-edit-preview-style';

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return;
  var style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = [
    '.q-edit-preview{margin-top:10px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#fff;}',
    '.q-edit-preview__head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 12px;background:#f5f8fc;border-bottom:1px solid #e2e8f0;font-size:13px;font-weight:600;color:#1A3C6D;}',
    '.q-edit-preview__badge{font-weight:400;font-size:12px;color:#64748b;}',
    '.q-edit-preview__body{padding:12px 14px;line-height:1.85;font-size:14px;color:#333;max-height:460px;overflow:auto;}',
    '.q-edit-preview__body img{max-width:100%;height:auto;display:block;margin:8px 0;border-radius:6px;}',
    '.q-edit-preview__body table{border-collapse:collapse;max-width:100%;}',
    '.q-edit-preview__body td,.q-edit-preview__body th{border:1px solid #dcdfe6;padding:4px 8px;}',
    '.q-edit-preview__muted{color:#94a3b8;font-size:13px;}',
    '.q-edit-preview__error{color:#C41E3A;font-size:13px;}',
    '.q-edit-preview__option{display:flex;gap:8px;padding:7px 9px;margin-bottom:5px;border:1px solid #eef2f7;border-radius:6px;background:#fafcff;}',
    '.q-edit-preview__key{font-weight:700;color:#1A3C6D;min-width:22px;}',
    '.q-edit-preview__val{flex:1;min-width:0;}'
  ].join('');
  document.head.appendChild(style);
}

function fieldGroupByLabel(root, keywords) {
  var labels = root.querySelectorAll('label');
  for (var i = 0; i < labels.length; i++) {
    var text = String(labels[i].textContent || '');
    for (var j = 0; j < keywords.length; j++) {
      if (text.indexOf(keywords[j]) >= 0) {
        return labels[i].closest('.form-group') || labels[i].closest('.fg') || labels[i].parentElement;
      }
    }
  }
  return null;
}

function ensureBlock(group, key, title) {
  if (!group) return null;
  var block = group.querySelector('[data-edit-preview="' + key + '"]');
  if (block) return block;
  block = document.createElement('div');
  block.className = 'q-edit-preview';
  block.setAttribute('data-edit-preview', key);
  block.innerHTML = '<div class="q-edit-preview__head"><span>' + title + '</span>'
    + '<span class="q-edit-preview__badge"></span></div>'
    + '<div class="q-edit-preview__body"></div>';
  group.appendChild(block);
  return block;
}

function setBlock(block, html, badge) {
  if (!block) return;
  var body = block.querySelector('.q-edit-preview__body');
  if (body) body.innerHTML = html || '<span class="q-edit-preview__muted">暂无内容</span>';
  var badgeEl = block.querySelector('.q-edit-preview__badge');
  if (badgeEl) badgeEl.textContent = badge || '';
}

function renderRichText(text) {
  var raw = String(text == null ? '' : text);
  if (!raw.trim()) return '';
  return renderQuestionContent(raw);
}

function escapeText(text) {
  return String(text == null ? '' : text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderOptions(items) {
  if (!items || !items.length) {
    return '<span class="q-edit-preview__muted">暂无选项</span>';
  }
  var rows = items.map(function (item) {
    var key = escapeText(item && item.key ? item.key : '');
    var value = item && item.value != null ? item.value : '';
    return '<div class="q-edit-preview__option">'
      + '<span class="q-edit-preview__key">' + key + '.</span>'
      + '<span class="q-edit-preview__val">' + (renderRichText(value) || '<span class="q-edit-preview__muted">（空）</span>') + '</span>'
      + '</div>';
  });
  return rows.join('');
}

function countImages(html) {
  var m = String(html || '').match(/<img\b/gi);
  return m ? m.length : 0;
}

/**
 * 找到当前可见的「编辑题目」弹窗。预览弹窗的 h3 是「题目预览」，不会被命中。
 */
export function findEditModalRoot() {
  var nodes = document.querySelectorAll('.modal-content');
  for (var i = 0; i < nodes.length; i++) {
    var h3 = nodes[i].querySelector('h3');
    if (h3 && String(h3.textContent || '').indexOf('编辑题目') >= 0 && nodes[i].getClientRects().length > 0) {
      return nodes[i];
    }
  }
  return null;
}

/**
 * 刷新编辑弹窗的全部预览块。
 * @param {Element} root 编辑弹窗根节点
 * @param {{material?:string, question?:string, options?:Array, optionsError?:string, analysis?:string}} payload
 */
export function refreshEditPreviews(root, payload) {
  if (!root) return;
  ensureStyle();
  var data = payload || {};

  // 题组材料：隐藏模板里的纯文本 .material-preview，避免同一份材料出现两次
  var materialGroup = fieldGroupByLabel(root, ['题组材料']);
  if (materialGroup) {
    var plain = materialGroup.querySelector('.material-preview');
    if (plain) plain.style.display = 'none';
    var materialHtml = renderRichText(data.material);
    var materialBlock = ensureBlock(materialGroup, 'material', '📄 题组材料预览');
    setBlock(materialBlock, materialHtml, materialHtml ? ('图片 ' + countImages(materialHtml) + ' 张') : '');
  }

  // 题干：教师端模板已有 v-html 实时预览，不重复注入；管理端没有，需补一个
  var questionGroup = fieldGroupByLabel(root, ['题干内容', '题目内容']);
  if (questionGroup && !questionGroup.querySelector('.edit-preview-block') && !questionGroup.querySelector('.edit-preview-body')) {
    var questionHtml = renderRichText(data.question);
    var questionBlock = ensureBlock(questionGroup, 'question', '🖼 题干预览');
    setBlock(questionBlock, questionHtml, questionHtml ? ('图片 ' + countImages(questionHtml) + ' 张') : '');
  }

  // 选项：教师端是逐项 input，管理端是 JSON textarea，两者都补富文本预览
  var optionsGroup = fieldGroupByLabel(root, ['选项']);
  if (optionsGroup) {
    var optionsBlock = ensureBlock(optionsGroup, 'options', '🖼 选项预览');
    if (data.optionsError) {
      setBlock(optionsBlock, '<span class="q-edit-preview__error">' + escapeText(data.optionsError) + '</span>', '');
    } else {
      var optionHtml = renderOptions(data.options);
      setBlock(optionsBlock, optionHtml, (data.options && data.options.length ? data.options.length + ' 项' : ''));
    }
  }

  // 答案解析：教师端模板的原预览受 editPreviewOpen 控制，这里固定补一份，保证默认可见
  var analysisGroup = fieldGroupByLabel(root, ['答案解析']);
  if (analysisGroup) {
    var nativePreview = analysisGroup.querySelector('.edit-preview-body');
    if (nativePreview) nativePreview.style.display = 'none';
    var analysisHtml = renderRichText(data.analysis);
    var analysisBlock = ensureBlock(analysisGroup, 'analysis', '🖼 答案解析预览');
    setBlock(analysisBlock, analysisHtml, analysisHtml ? ('图片 ' + countImages(analysisHtml) + ' 张') : '');
  }
}

export default { findEditModalRoot, refreshEditPreviews };
