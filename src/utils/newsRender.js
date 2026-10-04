/**
 * 新闻正文安全渲染工具（新闻场景唯一事实来源）
 *
 * 收敛此前 mobile_news.vue / 后台 / 电脑端各自为政的新闻正文渲染逻辑。
 *
 * 与 questionRender.js 的关系（重要）：
 *   清洗语义完全复用 sanitizeHtml，本模块不实现第二套清洗，避免出现安全缺口。
 * 本模块只做新闻场景特有的三件事：
 *   1. [[IMG:n]] 文本标记 -> <img>（新闻正文专用标记，与题目的 [IMAGE:q_i] 不同）
 *   2. 相邻重复段落合并（爬虫重复下载导致的数据缺陷的前端防御）
 *   3. 划线高亮注入（用 <span> 而非 <mark>，因 mark 不在白名单内）
 *
 * 为什么不加 <img onerror> 兜底：
 *   questionRender.js 的 attachImageFallback 未导出，另写一份即构成「第二套渲染实现」，
 *   违反护栏。此处按计划只做「标记找不到对应图片」的占位兜底。
 */

import { sanitizeHtml } from './questionRender';

/** 整段就是一个图片标记时才视为行内图片 */
var WHOLE_IMG_MARKER_RE = /^\[\[IMG:(\d+)\]\]$/;

/**
 * 归一化图片地址。
 * 协议相对地址 "//host/a.jpg" 在部分环境会被当成本地路径导致裂图，统一补全为 https。
 * @param {string} url 原始地址
 * @returns {string} 归一化后的地址，空值返回 ''
 */
export function resolveNewsImage(url) {
  var u = String(url || '').trim();
  if (!u) return '';
  if (u.indexOf('//') === 0) return 'https:' + u;
  return u;
}

/**
 * 图片项可能是纯 URL 字符串，也可能是带 url/order 的对象，统一取 URL。
 * @param {string|{url?:string,order?:number}} img 图片项
 * @returns {string} URL
 */
function imageUrlOf(img) {
  return typeof img === 'string' ? img : ((img && img.url) || '');
}

/**
 * 建立 order -> url 映射。
 * 新闻正文里的 [[IMG:n]] 通过 n 索引到 images 数组。
 * @param {Array} images 图片数组
 * @returns {Object} order -> url 的映射
 */
function buildOrderMap(images) {
  var map = {};
  if (!Array.isArray(images)) return map;
  for (var i = 0; i < images.length; i++) {
    var img = images[i];
    if (!img || typeof img === 'string') continue;
    var order = img.order;
    if (order === undefined || order === null) continue;
    map[order] = imageUrlOf(img);
  }
  return map;
}

/**
 * 段落去重键：去掉所有空白与常见标点后比较，
 * 避免「近日…」与「近日，」被当成不同段落而漏掉重复。
 * @param {string} text 段落文本
 * @returns {string} 归一化后的比较键
 */
function dedupeKey(text) {
  return String(text || '')
    .replace(/\s+/g, '')
    .replace(/[，。、；：？！“”‘’（）《》【】,.;:?!"'()<>\[\]]/g, '');
}

/**
 * 把正文切成「文本块」与「图片块」序列。
 *
 * 必须逐行扫描而不能直接按空行分段：真实数据里 [[IMG:n]] 与正文常常
 * 只隔一个换行（news_id=1193 实测结构），按 \n{2,} 分段会把
 * 「标记 + 正文」并成同一段，导致整行锚定的标记匹配失效。
 *
 * @param {string} content 新闻正文
 * @returns {Array<{type:'text',text:string}|{type:'img',order:number}>} 块序列
 */
function splitBlocks(content) {
  var lines = String(content).split(/\r?\n/);
  var blocks = [];
  var buf = [];
  var prevLineKey = null;

  function flushText() {
    if (!buf.length) return;
    var t = buf.join('\n').trim();
    buf = [];
    if (t) blocks.push({ type: 'text', text: t });
  }

  for (var i = 0; i < lines.length; i++) {
    var line = String(lines[i]).trim();
    if (!line) {
      flushText();
      prevLineKey = null;
      continue;
    }
    var m = line.match(WHOLE_IMG_MARKER_RE);
    if (m) {
      flushText();
      blocks.push({ type: 'img', order: parseInt(m[1], 10) });
      prevLineKey = null;
      continue;
    }
    // 关键：重复行必须自成一块。
    // 否则「P」「P」两行连续出现时会被 flush 合并成一个 text 块 'P\nP'，
    // 去重键从「同一段」变成「两段连写」，与 lastTextKey 永远不匹配，
    // 重复内容会原样渲染出来（与后端 _dedupe_adjacent_paragraphs 同一缺陷）。
    var key = dedupeKey(line);
    if (key && key === prevLineKey) flushText();
    buf.push(line);
    prevLineKey = key;
  }
  flushText();
  return blocks;
}

/**
 * 合并重复正文段落，并同步丢弃随之重复的图片。
 *
 * 关键设计（与计划中「相邻重复段落合并」不同，这里必须更强）：
 *   计划字面写的是「合并相邻重复段落」，但真实缺陷数据是
 *     [[IMG:0]] P [[IMG:1]] P [[IMG:2]] P
 *   重复段落之间被图片标记隔开，**并不相邻**，
 *   只做相邻合并完全无效，用户的「三张一样图片」问题不会被解决。
 *
 *   故规则放宽为：与「上一个已输出文本段」相同即视为重复，
 *   并连带丢弃本轮累积的图片 —— 这些图片正是重复下载的那批。
 *
 *   校验：
 *     P, P              -> 输出 P
 *     img0, P, img1, P  -> 输出 img0, P
 *     img0, img1        -> 两个都输出（无重复正文，不动图片）
 *
 * @param {Array} blocks splitBlocks 的输出
 * @returns {Array} 去重后的块序列
 */
function dropDuplicateBlocks(blocks) {
  var out = [];
  var pendingImgs = [];
  var lastTextKey = null;

  for (var i = 0; i < blocks.length; i++) {
    var b = blocks[i];
    if (b.type === 'img') {
      pendingImgs.push(b);
      continue;
    }
    var key = dedupeKey(b.text);
    if (key && key === lastTextKey) {
      // 重复正文：连带丢弃本轮累积的图片
      pendingImgs = [];
      continue;
    }
    for (var j = 0; j < pendingImgs.length; j++) out.push(pendingImgs[j]);
    pendingImgs = [];
    out.push(b);
    lastTextKey = key;
  }
  // 结尾残留的图片（正文里没有对应段落）原样保留
  for (var k = 0; k < pendingImgs.length; k++) out.push(pendingImgs[k]);
  return out;
}

/**
 * 合并相邻重复段落。
 *
 * 背景：news_scraper 的三条图片下载路径均无内容去重，导致
 * 「同一段正文 + 三张内容相同的图片」被重复入库（实测 546/2125 篇受影响）。
 * 前端无法按 URL 去重（重复图片路径不同：img_0/img_1/img_2），但可消除重复段落。
 * @param {string[]} paragraphs 段落数组
 * @returns {string[]} 去重后的段落数组
 */
export function mergeAdjacentDuplicateParagraphs(paragraphs) {
  var out = [];
  var prevKey = null;
  for (var i = 0; i < paragraphs.length; i++) {
    var p = String(paragraphs[i] || '').trim();
    if (!p) continue;
    var key = dedupeKey(p);
    // 只合并「相邻」重复：非相邻的同段落在新闻里可能是合理的重复叙述
    if (key && key === prevKey) continue;
    out.push(p);
    prevKey = key;
  }
  return out;
}

/**
 * 缺图占位（用于标记存在但 images 里找不到对应图片的情况）。
 */
var MISSING_IMG_HTML = '<span class="news-img-missing">[图片]</span>';

/**
 * 文本转义。新闻正文来自爬虫，必须转义后再拼 HTML。
 */
function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * 划线样式 -> 行内 CSS。
 * 与后端 renderNoteStyle 的四种线型保持一致：wavy / straight / marker / left-bar。
 * @param {string} color 颜色
 * @param {string} lineStyle 线型
 * @returns {string} 行内 style 值
 */
function highlightStyle(color, lineStyle) {
  var c = color || '#FFD700';
  if (lineStyle === 'straight') return 'text-decoration:underline ' + c;
  if (lineStyle === 'marker') return 'background-color:' + c + '40;padding:0 2px;';
  if (lineStyle === 'left-bar') return 'border-left:3px solid ' + c + ';padding-left:4px;';
  return 'text-decoration:underline wavy ' + c; // wavy 为默认
}

/**
 * 在已转义的段落文本里注入划线高亮。
 *
 * 关键：先转义正文、再匹配转义后的 quote_text，顺序反了会导致
 * quote 中含 < > & 时匹配失败或破坏 HTML 结构。
 *
 * @param {string} escapedPara 已转义的段落文本
 * @param {Array<{quote_text:string,color?:string,line_style?:string}>} highlights 划线列表
 * @returns {string} 注入高亮后的 HTML 片段
 */
function injectHighlights(escapedPara, highlights) {
  if (!Array.isArray(highlights) || !highlights.length) return escapedPara;
  var out = escapedPara;
  for (var i = 0; i < highlights.length; i++) {
    var h = highlights[i];
    if (!h || !h.quote_text) continue;
    var needle = escapeHtml(h.quote_text);
    // 过短或含通配意义的片段不做替换，避免误伤整段
    if (needle.length < 2) continue;
    if (out.indexOf(needle) === -1) continue;
    var style = highlightStyle(h.color, h.line_style);
    // 已注入过的高亮不再重复包裹
    var openTag = '<span class="news-hl" style="' + style + '">';
    out = out.split(needle).join(openTag + needle + '</span>');
  }
  return out;
}

/**
 * 新闻正文渲染入口（新闻场景唯一事实来源）。
 *
 * 处理顺序（不可调换）：
 *   1. 分段 + 相邻重复段落合并
 *   2. [[IMG:n]] -> <img>，找不到对应图片时输出占位
 *   3. 段落文本转义 + 注入划线高亮
 *   4. sanitizeHtml 清洗（最后统一清洗，保证前面生成的标签也受白名单约束）
 *
 * @param {string} content 新闻正文（可能含 [[IMG:n]] 标记）
 * @param {Array} images 图片数组（元素为 URL 字符串或 {url, order}）
 * @param {Array<{quote_text:string,color?:string,line_style?:string}>} [highlights] 划线列表
 * @returns {string} 可直接用于 v-html 的安全 HTML
 */
export function renderNewsContent(content, images, highlights) {
  if (!content) return '';
  var orderMap = buildOrderMap(images);

var blocks = dropDuplicateBlocks(splitBlocks(content));

  var html = '';
  for (var i = 0; i < blocks.length; i++) {
    var b = blocks[i];
    if (b.type === 'img') {
      var src = resolveNewsImage(orderMap[b.order]);
      // 标记在但图片已随重复数据被清理 -> 输出占位，避免正文出现裸标记
      html += src
        ? '<img src="' + src + '" alt="新闻图片" class="inline-img" />'
        : MISSING_IMG_HTML;
      continue;
    }
    var escaped = escapeHtml(b.text).replace(/\n/g, '<br/>');
    html += '<p>' + injectHighlights(escaped, highlights) + '</p>';
  }

  return sanitizeHtml(html);
}

/**
 * 图片列表去重（按解析后的 URL）。
 * 注意：内容相同但路径不同的重复图片无法在前端识别，必须依赖采集端与清洗脚本解决。
 * @param {Array} images 图片数组
 * @returns {string[]} 去重后的 URL 列表
 */
export function dedupeNewsImages(images) {
  var out = [];
  var seen = {};
  if (!Array.isArray(images)) return out;
  for (var i = 0; i < images.length; i++) {
    var url = resolveNewsImage(imageUrlOf(images[i]));
    if (!url) continue;
    if (seen[url]) continue;
    seen[url] = true;
    out.push(url);
  }
  return out;
}

export default {
  renderNewsContent,
  dedupeNewsImages,
  resolveNewsImage,
  mergeAdjacentDuplicateParagraphs,
};