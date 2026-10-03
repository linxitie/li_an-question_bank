/**
 * `src/utils/questionRender.js` 的类型声明。
 * 该实现为无类型 JavaScript 模块，此处按其实际导出签名提供类型，
 * 避免 TS7016（隐式 any）污染调用方。
 */

/** 题目内容渲染选项 */
export interface RenderQuestionContentOptions {
  /**
   * 剥离题干中内联的 `A. xxx` / `B. xxx` 选项文本。
   * 题干场景传 true；选项、解析等场景不要传。
   */
  stripInlineOption?: boolean;
}

/**
 * 题目内容渲染：返回可直接用于 v-html 的安全 HTML 字符串。
 *
 * 会把内容中的 `[IMAGE:题号_序号]` 文本标记转换为 `<img>` 标签，
 * 并对 `<img>` 补 onerror 占位图兜底。
 */
export function renderQuestionContent(
  content: unknown,
  options?: RenderQuestionContentOptions
): string;

/** 列表摘要渲染：移除图片标签并剥离 HTML，返回纯文本 */
export function renderQuestionSummary(content: unknown): string;

/** HTML 清洗 */
export function sanitizeHtml(html: string): string;

declare const _default: {
  renderQuestionContent: (
    content: unknown,
    options?: RenderQuestionContentOptions
  ) => string;
  renderQuestionSummary: (content: unknown) => string;
  sanitizeHtml: (html: string) => string;
};

export default _default;
