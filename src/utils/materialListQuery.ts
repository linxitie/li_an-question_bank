/**
 * 资料管理页的地址栏查询参数解析（A4 补充，2026-11-07）
 *
 * 为什么单独抽出来：`/admin/papers` 被改成 redirect 到 `/admin/materials?type=paper`
 * （试卷收敛 P4=A，旧书签不 404）。但 A4 首版页面**没有读 route.query**，
 * 实测跳转后类型下拉仍是「全部类型」、列表仍是 112 条 —— 等于"跳对了位置但没筛"。
 * 把解析写成纯函数：① 可单元测试；② 白名单集中一处，手改 URL 塞垃圾值不会把列表刷空。
 *
 * 白名单原则：**只接受登记过的值**，非法值一律当"没传"（返回空串），不报错、不 400。
 * 这与后端 `Query(pattern=...)` 的处理方式一致（后端会 422），前端这里选择"宽容忽略"，
 * 因为地址栏是用户可以随手改的输入，报错弹窗对他没有任何帮助。
 */

/** 预约筛选项（与页面 filters 同名，便于直接 Object.assign） */
export interface MaterialListQuery {
  subject: string;
  type: string;
  status: string;
  createdWithin: '' | '7d' | '30d';
  /** C3：试卷年份（空串=不筛） */
  paperYear: string;
  /** C3：试卷地区（代码或中文，空串=不筛） */
  region: string;
  /** C3：试卷卷别 T/A/J（空串=不筛） */
  bookKind: string;
}

const SUBJECTS = ['xingce', 'shenlun', 'gongzhuan'];
/** 与 `src/modules/library/materialTypes.ts` 的 key 同集（6 类） */
const TYPES = ['video_intro', 'video_advanced', 'article', 'card', 'lecture', 'paper'];
/** 1=已上架 / 0=未上架 / -1=回收站 */
const STATUSES = ['1', '0', '-1'];
const WINDOWS = ['7d', '30d'];
/** C3：地区白名单与后端 `paper_meta_parser.REGIONS` 同源（代码 + 中文名都收） */
const REGIONS = [
  'BJ', 'JS', 'ZJ', 'GD', 'SD', 'SH', 'TJ', 'CQ', 'HE', 'HA', 'HB', 'HN',
  'SC', 'FJ', 'AH', 'JX', 'SX', 'SN', 'LN', 'JL', 'HLJ', 'GX', 'YN', 'GZ',
  'NM', 'GS', 'XJ', 'NX', 'QH', 'HI', 'XZ', 'GK', 'LK',
  '北京', '江苏', '浙江', '广东', '山东', '上海', '天津', '重庆', '河北', '河南',
  '湖北', '湖南', '四川', '福建', '安徽', '江西', '山西', '陕西', '辽宁', '吉林',
  '黑龙江', '广西', '云南', '贵州', '内蒙古', '甘肃', '新疆', '宁夏', '青海', '海南',
  '西藏', '国考', '联考'
];
const BOOK_KINDS = ['T', 'A', 'J'];

/** 年份：只接受 1900–2100 的整数（与后端 `paper_year` 校验一致） */
function pickYear(v: unknown): string {
  const s = firstString(v).trim();
  if (!/^\d{4}$/.test(s)) return '';
  const n = Number(s);
  return n >= 1900 && n <= 2100 ? s : '';
}

/** router 的 query 值可能是 string / string[] / null / undefined，统一取第一个字符串 */
function firstString(v: unknown): string {
  if (typeof v === 'string') return v;
  if (Array.isArray(v) && typeof v[0] === 'string') return v[0];
  return '';
}

function pick(v: unknown, allowed: string[]): string {
  const s = firstString(v).trim();
  return allowed.includes(s) ? s : '';
}

/**
 * 解析地址栏 query → 筛选项。
 *
 * 支持的参数：`subject` / `type` / `status` / `created_within`（与后端 `admin_list` 同名）。
 * 例：`#/admin/materials?type=paper` → `{ type: 'paper' }`，其余为空串（=不筛）。
 */
export function parseListQuery(query: Record<string, unknown> | null | undefined): MaterialListQuery {
  const q = query || {};
  const win = pick(q.created_within, WINDOWS);
  return {
    subject: pick(q.subject, SUBJECTS),
    type: pick(q.type, TYPES),
    status: pick(q.status, STATUSES),
    createdWithin: (win as '' | '7d' | '30d') || '',
    paperYear: pickYear(q.year),
    region: pick(q.region, REGIONS),
    bookKind: pick(q.book_kind, BOOK_KINDS)
  };
}

/** 这批筛选项里是否有任何一个生效（用于决定要不要在页头提示"来自地址栏"） */
export function hasListQuery(q: MaterialListQuery): boolean {
  return !!(q.subject || q.type || q.status || q.createdWithin
    || q.paperYear || q.region || q.bookKind);
}
