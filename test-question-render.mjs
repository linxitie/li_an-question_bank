/**
 * 渲染回归门禁（题目 + 新闻）
 *
 * 覆盖两个安全渲染单一真源：
 *   src/utils/questionRender.js  —— 题目内容（sanitizeHtml / renderQuestionContent）
 *   src/utils/newsRender.js     —— 新闻正文（[[IMG:n]] / 重复段落合并 / 划线高亮）
 *
 * 门禁要点：
 *   1. sanitizeHtml 必须剥离危险标签、on* 事件、javascript: 协议
 *   2. 新闻重复段落缺陷（news_id=1193：img0,P,img1,P,img2,P）必须收敛为 img0,P
 *   3. 划线高亮必须用白名单内的 <span>（mark 不在白名单，会被清洗掉）
 *
 * 运行：npx esbuild test-question-render.mjs --bundle --format=cjs --outfile=.tmp-render-gate.cjs
 *       node .tmp-render-gate.cjs
 */
import {
  sanitizeHtml,
  renderQuestionContent,
  renderQuestionSummary,
} from './src/utils/questionRender.js';
import {
  renderNewsContent,
  dedupeNewsImages,
  mergeAdjacentDuplicateParagraphs,
  resolveNewsImage,
} from './src/utils/newsRender.js';

let passed = 0;
let failed = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    passed++;
  } else {
    failed++;
    failures.push({ name, expected: e, actual: a });
  }
}

function checkTrue(name, cond, detail) {
  if (cond) passed++;
  else {
    failed++;
    failures.push({ name, expected: 'true', actual: detail || 'false' });
  }
}

// ============================================================
// 1. sanitizeHtml 安全清洗
// ============================================================
check('xss: script 标签及内容被剥离',
  sanitizeHtml('<p>ok</p><script>alert(1)</script>'), '<p>ok</p>');

check('xss: on* 事件属性被剥离',
  sanitizeHtml('<img src="/a.png" onerror="alert(1)" />'),
  '<img src="/a.png" />');

// 注意：<a> 不在 ALLOWED_TAGS 内，会整体降级为纯文本，href 随之消失，
// 用它断言 javascript: 剥离会得到误导性结果，故改用白名单内的 <img src>。
const jsProtoOut = sanitizeHtml('<img src="javascript:alert(1)" />');
checkTrue('xss: javascript: 协议被剥离',
  jsProtoOut.indexOf('javascript:') === -1, jsProtoOut);

check('xss: 非白名单标签降级为文本',
  sanitizeHtml('<marquee>hello</marquee>'), 'hello');

check('xss: 白名单标签被保留',
  sanitizeHtml('<p class="a"><strong>b</strong></p>'),
  '<p class="a"><strong>b</strong></p>');

check('mark 不在白名单（决定划线必须用 span）',
  sanitizeHtml('<mark>x</mark>'), 'x');

checkTrue('span 在白名单且保留 style 属性',
  sanitizeHtml('<span class="news-hl" style="color:red">x</span>')
    === '<span class="news-hl" style="color:red">x</span>',
  sanitizeHtml('<span class="news-hl" style="color:red">x</span>'));

// ============================================================
// 2. renderQuestionContent
// ============================================================
check('题目：[IMAGE:q_i] 标记转 img',
  renderQuestionContent('[IMAGE:12_1]').includes('/static/questions/12/12_1.png'),
  true);

check('题目：纯文本原样返回',
  renderQuestionContent('纯文本题干'), '纯文本题干');

check('题目：img 补 onerror 兜底',
  /onerror=/.test(renderQuestionContent('<img src="/a.png">')),
  true);

check('题目摘要：img 转 [图片] 占位',
  renderQuestionSummary('<img src="/a.png">'), '[图片]');

// ============================================================
// 3. renderNewsContent —— 核心缺陷回归
// ============================================================

// 3.1 用户报告的真实数据形态（news_id=1193）：
//     标记与正文只隔一个换行，重复段落被图片隔开
const dupContent = [
  '[[IMG:0]]',
  '近日，内蒙古自治区包头市公安局民警走进公园开展反诈宣传。',
  '[[IMG:1]]',
  '近日，内蒙古自治区包头市公安局民警走进公园开展反诈宣传。',
  '[[IMG:2]]',
  '近日，内蒙古自治区包头市公安局民警走进公园开展反诈宣传。',
].join('\n');

const dupImgs = [
  { order: 0, url: '/static/news/a.jpg' },
  { order: 1, url: '/static/news/b.jpg' },
  { order: 2, url: '/static/news/c.jpg' },
];

const dupOut = renderNewsContent(dupContent, dupImgs, []);

check('重复段落缺陷：3 张图收敛为 1 张',
  (dupOut.match(/<img /g) || []).length, 1);
check('重复段落缺陷：重复正文收敛为 1 段',
  (dupOut.match(/<p>/g) || []).length, 1);
checkTrue('重复段落缺陷：保留的是第一张图',
  dupOut.includes('/static/news/a.jpg'), dupOut);
checkTrue('重复段落缺陷：不含后两张图',
  !dupOut.includes('/static/news/b.jpg') && !dupOut.includes('/static/news/c.jpg'),
  dupOut);

// 3.2 相邻重复段落（无图片）
check('相邻重复段落合并',
  mergeAdjacentDuplicateParagraphs(['段落A', '段落A', '段落B']),
  ['段落A', '段落B']);

// 3.3 标点差异不应被当成不同段落
check('标点差异视为同一段落',
  mergeAdjacentDuplicateParagraphs(['近日，记者走访。', '近日，记者走访']),
  ['近日，记者走访。']);

// 3.4 无重复时图片必须全部保留
const noDup = ['[[IMG:0]]', '第一段。', '[[IMG:1]]', '第二段。'].join('\n');
const noDupImgs = [
  { order: 0, url: '/x/1.jpg' },
  { order: 1, url: '/x/2.jpg' },
];
const noDupOut = renderNewsContent(noDup, noDupImgs, []);
check('无重复段落时图片不被误删',
  (noDupOut.match(/<img /g) || []).length, 2);

// 3.5 连续重复行（无标记、无空行）也必须合并。
//     这条曾被漏判：flush 会把「重复正文」「重复正文」合并成一个 text 块
//     '重复正文\n重复正文'，去重键变成两段连写，于是永不匹配。
check('连续重复行合并（无标记无空行）',
  (renderNewsContent('重复正文\n重复正文', [], []).match(/<p>/g) || []).length, 1);

// 3.6 多行且互不相同的段落必须保持为单个 <p>，内部以 <br/> 连接。
//     若去重时把多行拆成多个 <p>，正文首行缩进会逐行错位（中文段落规则）。
const multiLineOut = renderNewsContent('第一行内容\n第二行内容', [], []);
checkTrue('多行不同段落保持单个 <p> 且内含 <br/>',
  (multiLineOut.match(/<p>/g) || []).length === 1 && multiLineOut.indexOf('<br/>') !== -1,
  multiLineOut);

// 3.7 标记存在但图片缺失 -> 占位，而不是裸标记
const missingOut = renderNewsContent('[[IMG:9]]\n正文。', [], []);
checkTrue('缺图输出占位而非裸标记',
  missingOut.includes('news-img-missing') && !missingOut.includes('[[IMG:'),
  missingOut);

// 3.6 单换行分隔的标记也必须被识别（不能只按空行分段）
check('单换行分隔的标记可识别',
  renderNewsContent('[[IMG:0]]\n正文。', dupImgs, []).includes('<img '),
  true);

// 3.7 XSS：正文中的脚本必须被清洗
// 新闻正文来自爬虫，脚本必须被转义成惰性可见文本，而不是可执行标签。
// 这里不能用 includes('script') 判断：转义后的文本里仍然含有 "script" 这个单词，
// 但它是惰性的。真正要断言的是「不存在可执行标签」且「尖括号已被转义」。
const xssOut = renderNewsContent('正文<script>alert(1)</script>', [], []);
checkTrue('新闻正文 XSS：不存在可执行 script 标签',
  xssOut.indexOf('<script') === -1, xssOut);
checkTrue('新闻正文 XSS：尖括号被转义为惰性文本',
  xssOut.indexOf('&lt;script&gt;') !== -1, xssOut);

// ============================================================
// 4. 划线高亮注入
// ============================================================
const hlOut = renderNewsContent(
  '近日民警走进公园开展反诈宣传。',
  [],
  [{ quote_text: '反诈宣传', color: '#4CAF50', line_style: 'wavy' }]
);
checkTrue('划线高亮：quote 被 span 包裹',
  hlOut.includes('<span class="news-hl"'), hlOut);
checkTrue('划线高亮：颜色被应用',
  hlOut.includes('#4CAF50'), hlOut);

// quote 中含特殊字符时不能破坏 HTML 结构
const hlEscOut = renderNewsContent(
  '他说 A<B 且 C&D。',
  [],
  [{ quote_text: 'A<B 且 C&D', color: '#2196F3' }]
);
checkTrue('划线：quote 含尖括号时结构不被破坏',
  hlEscOut.includes('&lt;') && !hlEscOut.includes('<B 且'), hlEscOut);

// quote 未出现在正文中时不应注入
const hlMissOut = renderNewsContent('完全不同的正文。', [], [{ quote_text: '不存在', color: '#fff' }]);
checkTrue('划线：quote 不命中时不注入',
  !hlMissOut.includes('news-hl'), hlMissOut);

// ============================================================
// 5. 图片工具
// ============================================================
check('协议相对地址补全为 https',
  resolveNewsImage('//cdn.example.com/a.jpg'),
  'https://cdn.example.com/a.jpg');

check('图片按 URL 去重',
  dedupeNewsImages([
    { order: 0, url: '/a.jpg' },
    { order: 1, url: '/a.jpg' },
    { order: 2, url: '/b.jpg' },
    '/c.jpg',
  ]),
  ['/a.jpg', '/b.jpg', '/c.jpg']);

// ============================================================
// 汇总
// ============================================================
console.log('----------------------------------------');
console.log('passed: ' + passed + ', failed: ' + failed);
if (failures.length) {
  console.log('');
  failures.forEach((f) => {
    console.log('FAIL ' + f.name);
    console.log('  expected: ' + f.expected);
    console.log('  actual  : ' + f.actual);
  });
}
console.log('----------------------------------------');

if (failed > 0) {
  console.error('RENDER GATE FAILED');
  process.exit(1);
}
console.log('RENDER GATE PASSED');