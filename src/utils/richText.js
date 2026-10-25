/**
 * 富文本统一清洗/渲染工具（RT-1）
 *
 * 设计约束（与 questionRender.js 的关系）：
 *   1. 复用 questionRender 的 sanitizeHtml 作为唯一白名单清洗实现，本模块不另造一套。
 *   2. questionRender 当前白名单不含 <a>（题目语料里链接极罕见），若直接清洗会把链接
 *      降级为纯文本。本模块在调用 sanitizeHtml 之前先把合法 <a> 片段抽出占位，
 *      清洗后按白名单协议重建，保证 RT-A1：链接可点击 + target/rel + mailto。
 *   3. 只保留 href 一个属性，javascript:/data:/vbscript:/file: 等协议一律剥离；
 *      href 先做 HTML 实体解码再判定，阻断 `java&#115;cript:` 这类绕过。
 *   4. 所有 <img> 统一补 loading="lazy"，满足列表懒加载（RT-A2）。
 *
 * 本模块保持纯函数（无 DOM 依赖），可直接在 vitest node 环境测试。
 */

import { sanitizeHtml } from './questionRender';

/** 允许的绝对协议（相对路径 / 锚点 / 查询串无协议，另行放行） */
var SAFE_PROTOCOL_RE = /^(?:https?|mailto|tel):/i;

/** 危险协议（解码 + 去空白后判定） */
var DANGEROUS_PROTOCOL_RE = /^(?:javascript|data|vbscript|file):/i;

/** 带属性的 <a ...> 起始标签（属性值允许包含 > 字符） */
var ANCHOR_PAIR_RE = /<a\b((?:[^>"']|"[^"]*"|'[^']*')*)>([\s\S]*?)<\/a\s*>/gi;

/** 清洗过程中替换锚点用的占位符 */
var ANCHOR_TOKEN_RE = /\u0000RT_A_(\d+)\u0000/g;

var ENTITY_MAP = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' '
};

/**
 * 解码常见 HTML 实体（href 协议判定前必须做，防实体绕过）。
 * @param {string} input
 * @returns {string}
 */
function decodeEntities(input) {
  return String(input)
    .replace(/&#x([0-9a-f]+);/gi, function (_m, hex) {
      try {
        return String.fromCodePoint(parseInt(hex, 16));
      } catch (e) {
        return '';
      }
    })
    .replace(/&#(\d+);/g, function (_m, dec) {
      try {
        return String.fromCodePoint(parseInt(dec, 10));
      } catch (e) {
        return '';
      }
    })
    .replace(/&([a-z][a-z0-9]+);/gi, function (m, name) {
      var key = String(name).toLowerCase();
      return Object.prototype.hasOwnProperty.call(ENTITY_MAP, key) ? ENTITY_MAP[key] : m;
    });
}

/** HTML 属性值转义（只处理会破坏引号语义的字符） */
function escapeAttr(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * 从 <a> 属性串中提取 href。
 * @param {string} attrs
 * @returns {string}
 */
function extractHref(attrs) {
  var m = /\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i.exec(String(attrs || ''));
  if (!m) return '';
  return m[1] != null ? m[1] : m[2] != null ? m[2] : m[3] || '';
}

/**
 * 归一化并校验 href：实体解码 -> 去控制/空白字符 -> 协议白名单。
 * 不安全时返回空串。
 * @param {string} rawHref
 * @returns {string}
 */
function normalizeHref(rawHref) {
  if (!rawHref) return '';
  var decoded = decodeEntities(rawHref).trim();
  if (!decoded) return '';
  // 去掉所有控制字符与空白后再判定协议，阻断 `java\nscript:` / `java script:`
  var compact = decoded.replace(/[\u0000-\u0020\u007f]+/g, '');
  if (!compact) return '';
  if (DANGEROUS_PROTOCOL_RE.test(compact)) return '';
  var hasProtocol = /^[a-z][a-z0-9+.-]*:/i.test(compact);
  // 有协议但不是白名单协议（含 data:text/html、javascript 伪装）一律拒绝
  if (hasProtocol && !SAFE_PROTOCOL_RE.test(compact)) return '';
  return compact;
}

/**
 * 给全部 <img> 补 loading="lazy"（已有 loading 属性则保持原样）。
 * @param {string} html
 * @returns {string}
 */
function ensureLazyImages(html) {
  if (!html) return '';
  return String(html).replace(/<img\b((?:[^>"']|"[^"]*"|'[^']*')*)>/gi, function (match, attrs) {
    var cleanAttrs = String(attrs).replace(/\/\s*$/, '');
    if (/\bloading\s*=/i.test(cleanAttrs)) return '<img' + cleanAttrs + ' />';
    return '<img' + cleanAttrs + ' loading="lazy" />';
  });
}

/**
 * 富文本清洗：白名单标签 + 安全链接 + 图片懒加载。
 * 返回可直接用于 v-html 的 HTML 字符串。
 * @param {unknown} html
 * @returns {string}
 */
export function sanitizeRichText(html) {
  if (html == null || html === '') return '';
  var source = String(html);

  // 1. 先把完整 <a>...</a> 片段抽出占位，避免被 sanitizeHtml 的标签白名单降级
  var anchors = [];
  var tokenized = source.replace(ANCHOR_PAIR_RE, function (_match, attrs, inner) {
    var index = anchors.length;
    anchors.push({ attrs: attrs, inner: inner });
    return '\u0000RT_A_' + index + '\u0000';
  });

  // 2. 复用 questionRender 的唯一清洗实现
  var cleaned = sanitizeHtml(tokenized);

  // 3. 还原锚点：只保留安全 href，强制新窗口与 noopener
  cleaned = cleaned.replace(ANCHOR_TOKEN_RE, function (_match, index) {
    var anchor = anchors[Number(index)];
    if (!anchor) return '';
    var href = normalizeHref(extractHref(anchor.attrs));
    var inner = sanitizeHtml(anchor.inner);
    if (!href) return inner;
    return (
      '<a href="' +
      escapeAttr(href) +
      '" target="_blank" rel="noopener noreferrer">' +
      inner +
      '</a>'
    );
  });

  // 4. 图片懒加载（清洗之后再补，避免被视为非白名单属性）
  return ensureLazyImages(cleaned);
}

/**
 * 富文本渲染入口别名。
 * 保持纯函数：仅清洗，不依赖页面上下文（与 questionRender.renderQuestionContent 解耦）。
 * @param {unknown} html
 * @returns {string}
 */
export function renderRichText(html) {
  return sanitizeRichText(html);
}

/**
 * 富文本转纯文本，用于列表摘要 / 搜索预览 / 字数统计。
 * 图片统一转为「[图片]」占位，块级标签换行后压缩空白。
 * @param {unknown} html
 * @returns {string}
 */
export function stripRichText(html) {
  if (html == null || html === '') return '';
  var s = String(html);
  s = s.replace(/<img\b[^>]*>/gi, '[图片]');
  s = sanitizeHtml(s);
  s = s.replace(/<br\s*\/?>/gi, '\n');
  s = s.replace(/<\/(?:p|div|li|tr|h[1-6]|blockquote|pre)>/gi, '\n');
  s = s.replace(/<[^>]+>/g, '');
  s = decodeEntities(s);
  return s.replace(/\s+/g, ' ').trim();
}

export default {
  sanitizeRichText: sanitizeRichText,
  renderRichText: renderRichText,
  stripRichText: stripRichText
};
