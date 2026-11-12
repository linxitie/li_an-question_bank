/**
 * 补答案草稿的计数纯函数（2026-11-12）。
 *
 * 背景：`AnswerDraftDrawer` 原来用 `items.filter(i => i.answer).length` 当按钮数字，
 * 那是"**识别到答案的题数**"，不是"**这次会写进库的题数**"。
 * 当库里已有相同答案时（例如重复上传同一份答案解析），按钮显示 97、实际写 0（保留 97），
 * 用户会以为"没写进去"。这里把两种口径拆开，组件只负责展示。
 */

export interface AnswerItemLike {
  /** 本次解析到的答案（A–D，可能为空） */
  answer?: string;
  /** 库里现有的答案（list 接口带出来；无则视为空位） */
  current?: string;
}

function norm(value?: string): string {
  return String(value || '').replace(/[^A-Za-z]/g, '').toUpperCase();
}

/**
 * 本次**会写入**的题数：
 * - 答案为空 → 不算（只有解析的走"仅补解析"，不算答案写入）；
 * - 库里没有答案 → 算（填空）；
 * - 库里答案不同 → 只有勾了「覆盖已有答案」才算（否则按决策 Q1 保留）；
 * - 库里答案相同 → 不算（已经是这个答案，写它没意义）。
 */
export function countWritable(items: AnswerItemLike[], overwrite = false): number {
  return items.filter((it) => {
    const answer = norm(it.answer);
    if (!answer) return false;
    const current = norm(it.current);
    if (!current) return true;
    if (current === answer) return false;
    return Boolean(overwrite);
  }).length;
}

/** 本次解析里"与库里已有答案完全一致"的题数（用于成功提示，避免"解析 97 / 可写 0"的困惑） */
export function countIdentical(items: AnswerItemLike[]): number {
  return items.filter((it) => {
    const answer = norm(it.answer);
    if (!answer) return false;
    return norm(it.current) === answer;
  }).length;
}

/** 有答案的题数（上传成功提示里的"识别 N 题"用它，与 item_count 对齐） */
export function countAnswered(items: AnswerItemLike[]): number {
  return items.filter((it) => norm(it.answer)).length;
}

/** 与库里**不同**的题数（勾「覆盖」才会写；提示文案据此区分"要不要勾覆盖"） */
export function countDiffering(items: AnswerItemLike[]): number {
  return items.filter((it) => {
    const answer = norm(it.answer);
    if (!answer) return false;
    const current = norm(it.current);
    return Boolean(current) && current !== answer;
  }).length;
}
