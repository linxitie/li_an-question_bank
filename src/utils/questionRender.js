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

// 题干中的内联选项（如「A. 苹果 B. 香蕉」）需要剥离，图片以标记形式内嵌在选项之间
// 分隔符取并集：电脑端原内联正则为 [.、．)）]，此处补上 :： 以覆盖更多题库写法
var INLINE_OPTION_RE = /\n?\s*[A-H]\s*[.、．)）:：]\s*.+/g;

/**
 * 判断内容是否含 [IMAGE:题号_序号] 文本标记
 * 用于修正"纯文本直接返回"导致标记永不转图片的问题
 * @param {string} s
 * @returns {boolean}
 */
function hasImageMarker(s) {
  return /\[?IMAGE:(\d+)_(\d+)\]?/i.test(s);
}

/**
 * 把 [IMAGE:题号_序号] 文本标记转换为 <img> 标签
 *
 * 该转换原先只内联在电脑端 answer_page.vue 中，导致手机端
 * （错题本 / 答题卡）题目图片全部丢失。现下沉到本工具作为唯一事实来源。
 * @param {string} s 原始内容
 * @param {boolean} stripInlineOption 是否剥离题干内联的 A./B. 选项（题干场景传 true）
 * @returns {string}
 */
function convertImageMarkers(s, stripInlineOption) {
  var out = String(s);
  if (stripInlineOption) {
    out = out.replace(INLINE_OPTION_RE, '');
  }
  out = out.replace(/\[?IMAGE:(\d+)_(\d+)\]?/gi, function (m, qn, idx) {
    return '<img src="/static/questions/' + qn + '/' + qn + '_' + idx +
      '.png" class="q-img" loading="lazy" />';
  });
  return out;
}

/**
 * 白名单标签过滤：移除危险标签与事件属性
 *
 * 实现方式：真正启用 ALLOWED_TAGS 白名单（先剥离含内容的危险标签，
 * 再把不在白名单内的标签降级为无标签的纯文本），并叠加 on* 事件与
 * javascript: 协议的补充剥离。
 * @param {string} html 原始 HTML 字符串
 * @returns {string} 清洗后的 HTML 字符串
 */
export function sanitizeHtml(html) {
  if (!html) return '';
  var s = String(html);
  // 1. 剥离危险标签及其内容（script/iframe/object/embed/style/link/meta/form/input/button）
  s = s.replace(/<(script|iframe|object|embed|style|link|meta|form|input|button|textarea|select|option)[^>]*>[\s\S]*?<\/\1>/gi, '');
  s = s.replace(/<(script|iframe|object|embed|style|link|meta|form|input|button|textarea|select|option)[^>]*\/?>/gi, '');
  // 2. 剥离所有 on* 事件属性（防注入）
  s = s.replace(/\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
  // 3. 剥离 javascript: 协议
  s = s.replace(/(href|src)\s*=\s*(["']?)\s*javascript:[^"'\s>]*\2/gi, '');
  // 4. 真正的白名单：不在 ALLOWED_TAGS 中的标签降级为纯文本（丢弃标签本身，保留内容）
  //    例：<marquee>text</marquee> -> text；<svg onload=...>...</svg> -> ...
  s = s.replace(/<\/?([a-z][a-z0-9-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/gi, function (m, tagName, attrs) {
    var tag = String(tagName).toLowerCase();
    var isClosing = m.charAt(1) === '/';
    if (ALLOWED_TAGS.indexOf(tag) >= 0) return m;
    if (isClosing) return '';
    // 自闭合或普通开始标签：丢弃标签，保留其内容
    return '';
  });
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
    // 自闭合写法 <img ... /> 捕获到的 attrs 末尾会带一个 "/"，直接拼接会产出
    // `<img ... / onerror=...>` 这种非法属性，故先去掉尾部斜杠
    var cleanAttrs = attrs.replace(/\/\s*$/, '');
    return '<img' + cleanAttrs + ' onerror="this.onerror=null;this.src=\'' + PLACEHOLDER_SRC + '\';this.alt=\'图片加载失败\'" />';
  });
}

/**
 * 统一题目内容渲染入口（题目渲染唯一事实来源）
 *
 * 处理顺序（不可调换）：
 *   1. [IMAGE:题号_序号] 文本标记 -> <img>（必须最先，否则标记会原样显示为文字）
 *   2. sanitizeHtml 白名单清洗（此时 img 已是合法标签，得以保留）
 *   3. attachImageFallback 给 <img> 补 onerror 兜底（必须在清洗之后，
 *      因为 onerror 本身是 on* 属性，放前面会被清洗掉）
 *
 * @param {string} content 题目内容（可能含 HTML <img> 标签、[IMAGE:] 标记或纯文本）
 * @param {{stripInlineOption?: boolean}} [options]
 *        stripInlineOption=true 时剥离题干内联的 A./B. 选项（题干场景使用）
 * @returns {string} 可直接用于 v-html 的安全 HTML 字符串
 */
export function renderQuestionContent(content, options) {
  if (!content) return '';
  var s = String(content);
  var strip = !!(options && options.stripInlineOption);
  // 无 HTML 标签且无 [IMAGE:] 标记则原样返回（纯文本）。
  // 但若要求剥离内联选项，则仍需继续处理，不能提前返回。
  if (s.indexOf('<') === -1 && !hasImageMarker(s) && !strip) return s;
  // 先转换图片标记
  s = convertImageMarkers(s, strip);
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
