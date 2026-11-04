/**
 * 题目内容安全渲染工具（题目渲染唯一事实来源）
 *
 * 题库数据来自 PDF/docx/JSON 多种入口，同一张图可能以五种形态出现：
 *   1. 规范 HTML：<img src="/static/questions/xxx_41_0.png">
 *   2. 文本占位符：[IMAGE:xxx_41_0] / [IMAGE:123_0]
 *   3. 被转义的 HTML：&lt;img src=&quot;...&quot; /&gt;
 *   4. 相对路径：static/questions/xxx.png
 *   5. 后端绝对地址：http://host:8000/static/questions/xxx.png
 *
 * 任何页面只要把题干/选项/解析直接插值（{{ }}）或只做半套清洗，就会把第 3 种
 * 形态原样显示成 "<img src=...>" 文本（用户截图中的根因）。本模块负责在
 * v-html 前把所有形态归一化为安全、可加载、可回退的 <img>。
 *
 * 处理顺序不可调换：
 *   转义 HTML 还原 → 图片占位符转换 → img 地址归一化 → 白名单清洗 → onerror 兜底
 */

var ALLOWED_TAGS = [
  'img', 'p', 'br', 'b', 'strong', 'em', 'i', 'u', 'span', 'div',
  'table', 'thead', 'tbody', 'tr', 'td', 'th', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'sub', 'sup', 'blockquote', 'code', 'pre'
];

// 缺图占位：内联 SVG，避免占位图文件本身缺失导致二次裂图
var PLACEHOLDER_SRC = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="120">' +
  '<rect width="100%" height="100%" fill="#f5f6f8" stroke="#dcdfe6"/>' +
  '<text x="50%" y="50%" fill="#909399" font-size="14" text-anchor="middle" dominant-baseline="middle">图片加载失败</text>' +
  '</svg>'
);

// 题干中的内联选项（如「A. 苹果 B. 香蕉」）需要剥离。
// 只匹配行首，避免误删材料正文中“A. 某公司”这类正常句子以外的内容。
var INLINE_OPTION_RE = /(^|\n)[ \t]*[A-H][.、．)）:：][ \t]*[^\n]*/g;

function hasImageMarker(s) {
  return /\[?IMAGE:[^\]]+\]?/i.test(s);
}

/**
 * 还原被 HTML 实体转义的标签。
 * 只还原白名单标签，避免把正文里的 &lt; 等数学符号整体解码成可执行标签。
 */
function decodeEscapedTags(html) {
  if (!html) return '';
  var s = String(html);
  var tagNames = 'img|p|br|table|thead|tbody|tr|td|th|ul|ol|li|div|span|b|strong|em|i|u|sub|sup|blockquote|code|pre|h[1-6]';
  var re = new RegExp('&lt;(\\/?(?:' + tagNames + ')\\b[\\s\\S]*?)&gt;', 'gi');
  return s.replace(re, function (m, inner) {
    var decoded = String(inner)
      .replace(/&quot;/gi, '"')
      .replace(/&#0*34;/g, '"')
      .replace(/&#x0*22;/gi, '"')
      .replace(/&#0*39;/g, "'")
      .replace(/&#x0*27;/gi, "'")
      .replace(/&amp;/gi, '&');
    return '<' + decoded + '>';
  });
}

/**
 * 把 [IMAGE:marker] 转换为 <img>。
 * marker 兼容两段（123_0）与三段（uuid_115_0）形态，统一走已实测存在的
 * 扁平落盘路径 /static/questions/{marker}.png。
 */
function convertImageMarkers(s, stripInlineOption) {
  var out = String(s);
  if (stripInlineOption) {
    out = out.replace(INLINE_OPTION_RE, '');
  }
  out = out.replace(/\[?IMAGE:([^\]]+)\]?/gi, function (m, marker) {
    var key = String(marker || '').trim();
    if (!key) return '';
    if (/^[a-z0-9][a-z0-9_-]*_\d+(?:_\d+)?$/i.test(key)) {
      return '<img src="/static/questions/' + key + '.png" class="q-img" />';
    }
    // 后端已解析的 URL 被包在 IMAGE: 中时，直接取 URL
    if (/^(?:https?:)?\/\//i.test(key) || key.charAt(0) === '/') {
      return '<img src="' + key + '" class="q-img" />';
    }
    return '';
  });
  return out;
}

/**
 * 归一化单个图片地址。
 * - 空值/IMAGE 占位符 → 从 marker 推导 /static/questions/{marker}.png
 * - 后端绝对地址 → 取 /static 之后的部分，避免 http://localhost 写死
 * - 相对路径 → 补前导 /
 * - 纯文件名 → 落到 /static/questions/
 */
export function normalizeImageUrl(raw) {
  var src = String(raw || '').trim().replace(/^["']|["']$/g, '');
  if (!src) return '';
  var markerMatch = src.match(/\[?IMAGE:([^\]]+)\]?/i);
  if (markerMatch) src = markerMatch[1].trim();
  if (!src) return '';
  if (/^data:image\//i.test(src)) return src;
  // 从任意绝对/相对地址中截取 /static/ 之后的部分
  var staticAt = src.indexOf('/static/');
  if (staticAt >= 0) src = src.slice(staticAt);
  src = src.replace(/^https?:\/\/[^/]+/i, '');
  if (src.indexOf('static/') === 0) src = '/' + src;
  // 纯文件名（可能带目录）落到题目图目录
  if (src.charAt(0) !== '/' && !/^[a-z]+:/i.test(src)) {
    src = '/static/questions/' + src.replace(/^.*\//, '');
  }
  return src;
}

/**
 * 统一清洗 <img> 标签：补 q-img 类、alt、loading，并修正 src。
 * 在 sanitizeHtml 之前执行，保证清洗后仍是合法 img。
 */
function normalizeImageTags(html) {
  if (!html) return '';
  return String(html).replace(/<img\b([^>]*)>/gi, function (m, attrs) {
    var srcMatch = attrs.match(/\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);
    var rawSrc = srcMatch ? (srcMatch[1] || srcMatch[2] || srcMatch[3] || '') : '';
    var src = normalizeImageUrl(rawSrc);
    if (!src) return '';
    var rest = attrs
      .replace(/\bsrc\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, '')
      .replace(/\bclass\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, '')
      .replace(/\bloading\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, '')
      .replace(/\balt\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, '')
      .replace(/\bonerror\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, '')
      .replace(/\/\s*$/, '')
      .trim();
    return '<img src="' + src + '" class="q-img" alt="题目图片" loading="lazy"' +
      (rest ? ' ' + rest : '') + ' />';
  });
}

/**
 * 白名单标签过滤：移除危险标签与事件属性
 */
export function sanitizeHtml(html) {
  if (!html) return '';
  var s = String(html);
  s = s.replace(/<(script|iframe|object|embed|style|link|meta|form|input|button|textarea|select|option)[^>]*>[\s\S]*?<\/\1>/gi, '');
  s = s.replace(/<(script|iframe|object|embed|style|link|meta|form|input|button|textarea|select|option)[^>]*\/?>/gi, '');
  s = s.replace(/\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
  s = s.replace(/(href|src)\s*=\s*(["']?)\s*javascript:[^"'\s>]*\2/gi, '');
  s = s.replace(/<\/?([a-z][a-z0-9-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/gi, function (m, tagName) {
    var tag = String(tagName).toLowerCase();
    if (ALLOWED_TAGS.indexOf(tag) >= 0) return m;
    return '';
  });
  return s;
}

/**
 * 给 <img> 统一补 onerror 兜底（必须在 sanitizeHtml 之后，否则会被 on* 清洗掉）。
 */
function attachImageFallback(html) {
  if (!html) return '';
  return String(html).replace(/<img\b([^>]*)>/gi, function (match, attrs) {
    if (/\bonerror\s*=/i.test(attrs)) return match;
    var cleanAttrs = attrs.replace(/\/\s*$/, '').trim();
    var classAttr = /\bclass\s*=\s*("([^"]*)"|'([^']*)')/i.exec(cleanAttrs);
    var classes = classAttr ? (classAttr[2] || classAttr[3] || '') : '';
    if (classes.indexOf('q-img') < 0) {
      if (classAttr) {
        cleanAttrs = cleanAttrs.replace(classAttr[0], 'class="' + (classes + ' q-img').trim() + '"');
      } else {
        cleanAttrs += ' class="q-img"';
      }
    }
    return '<img ' + cleanAttrs +
      ' onerror="this.onerror=null;this.src=\'' + PLACEHOLDER_SRC + '\';this.classList.add(\'q-img-broken\');" />';
  });
}

/**
 * 统一题目内容渲染入口。
 * @param {string} content 题干/选项/解析原文
 * @param {{stripInlineOption?: boolean}} [options]
 * @returns {string} 可直接 v-html 的安全 HTML
 */
/**
 * 材料/长文本分段格式化（展示层，不改原文）。
 *
 * PDF 抽取的段落是“按版面宽度硬换行”，材料正文因此没有空行；直接 v-html
 * 会挤成一整段。这里只在已经 sanitize 的 HTML 上做启发式分段：
 *   · 空行 / <br> 强制断段；
 *   · 独占一行的「材料N」「（一）」等作为标题块；
 *   · 独占一行的纯图片作为 figure 块；
 *   · 编号/列表行单独成块；
 *   · 上一行以句末标点结尾且不足 48 字时才断段，否则视为软换行合并。
 *
 * 这是启发式而非 PDF 版面还原：宁可少断段，也不把一句话拆开。已有块级
 * 标签或已格式化的内容直接原样返回，保证幂等，避免二次包裹。
 */
var RICH_BLOCK_RE = /<(p|div|ul|ol|li|table|thead|tbody|tr|td|th|blockquote|h[1-6])\b/i;
var RICH_HEAD_RE = /^(?:给定材料[一二三四五六七八九十\d]*|材料\s*[一二三四五六七八九十\d]{1,3}|[一二三四五六七八九十]{1,3}、|（[一二三四五六七八九十]{1,3}）)\s*$/;
var RICH_SUBHEAD_RE = /^（[一二三四五六七八九十]{1,3}）[^。！？!?；;]{0,28}$/;
var RICH_LIST_RE = /^(?:\d{1,2}[.、．](?!\d)|[（(]\d{1,2}[）)])\s*/;

export function formatRichContent(html) {
  var source = String(html || '');
  if (!source) return '';
  if (source.indexOf('qr-rich') >= 0 || RICH_BLOCK_RE.test(source)) return source;

  var lines = source.replace(/<br\s*\/?>/gi, '\n').split('\n');
  var parts = [];
  var para = [];
  var lastLine = '';

  function flushPara() {
    if (!para.length) return;
    parts.push('<p class="qr-p">' + para.join('') + '</p>');
    para = [];
  }

  function appendLine(line) {
    var sep = '';
    if (para.length) {
      var prev = para[para.length - 1];
      if (/[A-Za-z0-9]$/.test(prev) && /^[A-Za-z0-9]/.test(line)) sep = ' ';
    }
    para.push(sep + line);
    lastLine = line;
  }

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (!line) { flushPara(); lastLine = ''; continue; }
    var plain = line.replace(/<img\b[^>]*>/gi, '').replace(/<[^>]*>/g, '').trim();
    if (!plain && /<img/i.test(line)) {
      flushPara();
      parts.push('<div class="qr-figure">' + line + '</div>');
      lastLine = '';
      continue;
    }
    if (RICH_HEAD_RE.test(plain) || (plain.length <= 30 && RICH_SUBHEAD_RE.test(plain))) {
      flushPara();
      parts.push('<div class="qr-heading">' + line + '</div>');
      lastLine = '';
      continue;
    }
    if (RICH_LIST_RE.test(plain)) {
      flushPara();
      parts.push('<p class="qr-p qr-li">' + line + '</p>');
      lastLine = '';
      continue;
    }
    if (para.length && /[。！？!?；;：:…”"]$/.test(lastLine) && lastLine.length <= 48) {
      flushPara();
    }
    appendLine(line);
  }
  flushPara();
  return parts.length ? '<div class="qr-rich">' + parts.join('') + '</div>' : source;
}

export function renderQuestionContent(content, options) {
  if (content === null || content === undefined || content === '') return '';
  var s = String(content);
  var strip = !!(options && options.stripInlineOption);
  var hasMarkup = s.indexOf('<') >= 0 || s.indexOf('&lt;') >= 0 || hasImageMarker(s);
  // 材料/长文本可能只有换行、没有任何标签；旧逻辑会在这里直接 return，
  // 导致分段样式永远不生效。只对含换行的内容启用格式化，避免改变短选项布局。
  var needsFormat = /\n/.test(s);
  if (!hasMarkup && !strip && !needsFormat) return s;
  s = decodeEscapedTags(s);
  s = convertImageMarkers(s, strip);
  s = normalizeImageTags(s);
  s = sanitizeHtml(s);
  s = formatRichContent(s);
  s = attachImageFallback(s);
  return s;
}

/**
 * 列表摘要渲染：移除图片转 [图片] 占位，避免列表显示长路径/大图。
 */
export function renderQuestionSummary(content) {
  if (!content) return '';
  var s = String(content);
  s = decodeEscapedTags(s);
  s = s.replace(/<img[^>]*\/?>/gi, '[图片]');
  s = s.replace(/\[IMAGE:[^\]]+\]/gi, '[图片]');
  s = sanitizeHtml(s);
  s = s.replace(/<[^>]+>/g, '');
  return s;
}

export default {
  renderQuestionContent,
  renderQuestionSummary,
  sanitizeHtml,
  normalizeImageUrl
};
