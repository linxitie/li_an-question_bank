/**
 * 试卷题目排序纯函数。
 *
 * 拖拽排序和序号展示都依赖这里，抽出来是为了：
 * 1. 组件里只做事件绑定，不把下标运算散落在模板和异步回调里；
 * 2. 用 vitest 覆盖向前/向后/首尾/越界等边界，避免“拖完序号错一位”。
 */

export interface PaperQuestionLike {
  question_id: number;
}

/**
 * 把 from 位置的元素移动到 to 位置，返回新数组。
 * to 是“移除 from 之后的最终下标”，与 HTML5 拖拽的插入语义一致。
 */
export function moveItem<T>(list: readonly T[], from: number, to: number): T[] {
  const next = list.slice();
  if (from < 0 || from >= next.length || to < 0 || to >= next.length || from === to) {
    return next;
  }
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/**
 * 在 index 处插入 item，返回新数组；index 越界时夹到首/尾。
 */
export function insertAt<T>(list: readonly T[], item: T, index: number): T[] {
  const next = list.slice();
  const at = Math.max(0, Math.min(index, next.length));
  next.splice(at, 0, item);
  return next;
}

/**
 * 用“全量试卷题目”计算真实序号，避免卷内搜索过滤后序号从 1 重排。
 * 找不到时返回 0，调用方应显式处理，而不是静默显示 1。
 */
export function displayOrder(list: readonly PaperQuestionLike[], questionId: number): number {
  const index = list.findIndex((item) => Number(item.question_id) === Number(questionId));
  return index >= 0 ? index + 1 : 0;
}
