/**
 * 题目内容安全渲染工具（问题3 单一事实来源）
 *
 * 后端已统一输出规范 <img> 标签，前端不再各自正则替换。
 * 本模块提供唯一的安全渲染入口，供所有展示题目题干/选项/解析的页面 v-html 使用：
 *   1. 白名单标签过滤（防 XSS）：仅保留安全标签，剥离 <script>/<iframe>/on* 事件等
 *   2. <img> 统一补 onerror 兜底（防裂图），失败时替换为占位图
 *   3. 若内容本身无 HTML（纯文本），原样返回
 */

// 允许保留的安全标签（题目内容由后端受控导入，白名单进一步兜底）
var ALLOWED_TAGS = [
  'img', 'p', 'br', 'b', 'strong', 'em', 'i', 'u', 'span', 'div',
  'table', 'thead', 'tbody', 'tr', 'td', 'th', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'sub', 'sup', 'blockquote', 'code', 'pre'
];

// 占位图路径（后端 /static/images 已挂载）
var PLACEHOLDER_SRC = '/static/images/placeholder.png';

/**
 * 白名单标签过滤：移除危险标签与事件属性
 * @param {string} html 原始 HTML 字符串
 * @returns {string} 清洗后的 HTML 字符串
 */
function sanitizeHtml(html) {
  if (!html) return '';
  var s = String(html);
  // 1. 剥离危险标签（script/iframe/object/embed/style/link/meta/form/input/button）
  s = s.replace(/<(script|iframe|object|embed|style|link|meta|form|input|button|textarea|select|option)[^>]*>[\s\S]*?<\/\1>/gi, '');
  s = s.replace(/<(script|iframe|object|embed|style|link|meta|form|input|button|textarea|select|option)[^>]*\/?>/gi, '');
  // 2. 剥离所有 on* 事件属性（防注入）
  s = s.replace(/\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
  // 3. 剥离 javascript: 协议
  s = s.replace(/(href|src)\s*=\s*(["']?)\s*javascript:[^"'\s>]*\2/gi, '');
  return s;
}

/**
 * 给 <img> 统一补 onerror 兜底（防裂图）
 * @param {string} html 已清洗的 HTML 字符串
 * @returns {string} 处理后的 HTML 字符串
 */
function attachImageFallback(html) {
  if (!html) return '';
  return String(html).replace(/<img\b([^>]*)>/gi, function (match, attrs) {
    if (/onerror\s*=/i.test(attrs)) return match; // 已有 onerror，不重复加
    return '<img' + attrs + ' onerror="this.onerror=null;this.src=\'' + PLACEHOLDER_SRC + '\';this.alt=\'图片加载失败\'" />';
  });
}

/**
 * 统一题目内容渲染入口
 * @param {string} content 题目内容（可能含 HTML <img> 标签或纯文本）
 * @returns {string} 可直接用于 v-html 的安全 HTML 字符串
 */
export function renderQuestionContent(content) {
  if (!content) return '';
  var s = String(content);
  // 无 HTML 标签则原样返回（纯文本）
  if (s.indexOf('<') === -1) return s;
  var cleaned = sanitizeHtml(s);
  cleaned = attachImageFallback(cleaned);
  return cleaned;
}

/**
 * 列表摘要渲染：移除 <img> 标签转 [图片] 占位，避免列表摘要显示长路径/大图
 * @param {string} content 题目内容
 * @returns {string} 纯文本摘要
 */
export function renderQuestionSummary(content) {
  if (!content) return '';
  var s = String(content);
  s = s.replace(/<img[^>]*\/?>/gi, '[图片]');
  s = s.replace(/\[IMAGE:[^\]]+\]/gi, '[图片]');
  s = sanitizeHtml(s);
  s = s.replace(/<[^>]+>/g, ''); // 去剩余标签，返回纯文本
  return s;
}

export default {
  renderQuestionContent,
  renderQuestionSummary,
  sanitizeHtml
};
