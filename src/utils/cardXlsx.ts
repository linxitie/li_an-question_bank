/**
 * xlsx 卡片智能导入的"列映射"纯函数（S3，2026-11-12）。
 *
 * 为什么单独抽出来：映射猜错 = 整批卡片建错（正面背面颠倒、分类全丢）。
 * 猜法必须可单测、可回放，所以只做纯字符串匹配，不做任何 IO。
 *
 * 后端契约（`POST /admin/import/{id}/confirm`）：`column_mapping` 里
 * `front` / `back` 必填（0 基列号），`category` / `point` / `cover` 可空。
 */

/** 表头 → 列号的猜测结果；`null` = 没猜到 */
export interface XlsxMapping {
  front: number | null;
  back: number | null;
  category: number | null;
  point: number | null;
  cover: number | null;
}

/** 字段顺序 = 猜测优先级（正面/背面先占坑，避免"答案背面"被分类抢走） */
export const MAPPING_FIELDS = ['front', 'back', 'category', 'point', 'cover'] as const;
export type MappingField = (typeof MAPPING_FIELDS)[number];

export const MAPPING_LABEL: Record<MappingField, string> = {
  front: '正面',
  back: '背面',
  category: '分类',
  point: '考点',
  cover: '封面'
};

/** 判断表头属于哪个字段的关键词（全部小写、去空格后做 includes） */
const KEYWORDS: Record<MappingField, string[]> = {
  front: ['正面', '题干', '问题', '词条', '关键词', 'front', 'question'],
  back: ['背面', '答案', '释义', '解析', '口诀', '要点', 'back', 'answer'],
  category: ['分类', '类别', '模块', 'category', 'class'],
  point: ['考点', '知识点', 'point', 'knowledge'],
  cover: ['封面', '配图', '图片', 'cover', 'image', 'img']
};

function norm(text: string): string {
  return String(text ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s\u3000]+/g, '');
}

/**
 * 猜列映射。
 *
 * 规则：按 `MAPPING_FIELDS` 顺序逐字段找"第一个还没被占用的表头"，
 * 命中即占坑（同一列不会被两个字段同时用掉）。
 */
export function guessXlsxMapping(headers: readonly string[]): XlsxMapping {
  const used = new Set<number>();
  const out: XlsxMapping = { front: null, back: null, category: null, point: null, cover: null };
  for (const field of MAPPING_FIELDS) {
    for (let i = 0; i < headers.length; i += 1) {
      if (used.has(i)) continue;
      const h = norm(headers[i]);
      if (!h) continue;
      if (KEYWORDS[field].some((k) => h.includes(k))) {
        out[field] = i;
        used.add(i);
        break;
      }
    }
  }
  return out;
}

/** 正面/背面都选了、且不是同一列 → 才能入库（与后端 400 的条件一致） */
export function isMappingReady(m: XlsxMapping): boolean {
  return (
    Number.isInteger(m.front) &&
    Number.isInteger(m.back) &&
    m.front !== null &&
    m.back !== null &&
    m.front !== m.back
  );
}

/** 组件 → 后端：转成 `{front: 0, back: 1, ...}`，没填的字段不传（后端按 None 处理） */
export function mappingPayload(m: XlsxMapping): Record<string, number> {
  const out: Record<string, number> = {};
  for (const field of MAPPING_FIELDS) {
    const idx = m[field];
    if (Number.isInteger(idx) && idx !== null) out[field] = idx as number;
  }
  return out;
}

/** 给界面用的可读摘要：`正面=第1列 · 背面=第2列 · 分类=第3列` */
export function mappingSummary(m: XlsxMapping, headers: readonly string[]): string {
  const parts: string[] = [];
  for (const field of MAPPING_FIELDS) {
    const idx = m[field];
    if (!Number.isInteger(idx) || idx === null) continue;
    parts.push(`${MAPPING_LABEL[field]}=第${(idx as number) + 1}列「${headers[idx as number] ?? ''}」`);
  }
  return parts.join(' · ');
}
