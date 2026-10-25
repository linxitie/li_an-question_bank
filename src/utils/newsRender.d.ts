/**
 * `src/utils/newsRender.js` 的类型声明。
 *
 * 该模块负责「每日新闻」正文渲染（图片标记 → <img>、划线高亮注入、HTML 清洗），
 * 是无类型 JavaScript，此处按实际导出签名补声明。
 */

/** 图片项：纯 URL 字符串，或带 url/order 的对象 */
export type NewsImageItem = string | { url?: string; order?: number };

/** 划线项：quote_text 必填，颜色/线型可选 */
export interface NewsHighlight {
  quote_text: string;
  color?: string;
  line_style?: string;
}

/** 协议相对地址补全为 https，空值返回 '' */
export function resolveNewsImage(url: string): string;

/** 合并相邻重复段落 */
export function mergeAdjacentDuplicateParagraphs(paragraphs: string[]): string[];

/** 正文 → 可直接用于 v-html 的安全 HTML（已 sanitizeHtml） */
export function renderNewsContent(
  content: string,
  images: NewsImageItem[],
  highlights?: NewsHighlight[]
): string;

/** 按解析后的 URL 去重，返回 URL 列表 */
export function dedupeNewsImages(images: NewsImageItem[]): string[];

declare const _default: {
  renderNewsContent: typeof renderNewsContent;
  dedupeNewsImages: typeof dedupeNewsImages;
  resolveNewsImage: typeof resolveNewsImage;
  mergeAdjacentDuplicateParagraphs: typeof mergeAdjacentDuplicateParagraphs;
};

export default _default;
