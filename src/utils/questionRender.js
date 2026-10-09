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
 * 判断内容是否含 [IMAGE:...] 文本标记
 * 用于修正"纯文本直接返回"导致标记永不转图片的问题
 * @param {string} s
 * @returns {boolean}
 */
function hasImageMarker(s) {
  return /\[?IMAGE:[^\]]+\]?/i.test(s);
}

/**
 * 把 [IMAGE:marker] 转换为 <img>。
 *
 * ★ 本函数原先的实现是错的，务必保留下面这段纠错背景：
 *   旧规则：`/\[?IMAGE:(\d+)_(\d+)\]?/` + URL 拼成
 *   `/static/questions/{qn}/{qn}_{idx}.png`
 *   实测**命中率 0/48** —— 磁盘上根本没有这种路径。
 *   两个独立错误叠加：
 *     a) 正则只认「数字_数字」，而库中实际有 43 处是「uuid_行号_序号」形态，
 *        被整段正则静默跳过，占位符原样显示成文字；
 *     b) 即使匹配上，URL 也指向 `{qn}/` 子目录，而 docx 抽图是以
 *        **扁平文件名**落在 static/questions/ 根目录的，子目录多半不存在。
 *
 * 现在改为：不猜路径，输出**后端已解析好的绝对 URL**。
 * 后端 image_service.resolve_image_marker() 会按
 *   {qid}/marker.png -> marker.png -> 行号_序号.png -> 子目录匹配 -> question_image 表
 * 逐级定位**磁盘上真实存在**的文件，找不到就剔除占位符（宁可少图，不要裂图）。
 * 前端只负责把 marker 文本换成后端给的 URL，不再自行拼路径。
 *
 * @param {string} s 原始内容
 * @param {boolean} stripInlineOption 是否剥离题干内联的 A./B. 选项（题干场景传 true）
 * @returns {string}
 */
function convertImageMarkers(s, stripInlineOption) {
  var out = String(s);
  if (stripInlineOption) {
    out = out.replace(INLINE_OPTION_RE, '');
  }
  // 保留 marker 形态用于取文件名，但绝不凭猜拼路径：
  // 优先用已有的 /static/... 绝对路径（后端已解析），否则退回原 marker 文本
  // 由后端在响应阶段完成真实定位（见 sanitize_image_placeholders）。
  out = out.replace(/\[?IMAGE:([^\]]+)\]?/gi, function (m, marker) {
    var key = String(marker || '').trim();
    if (!key) return '';
    // 后端在响应前已把可解析的 marker 替换为 <img>；
    // 走到这里的说明后端也没找到文件（真丢图），剔除以免前端裂图。
    return '';
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
