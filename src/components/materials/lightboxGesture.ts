/**
 * 全图查看器的触摸手势算法（纯函数，便于单测）
 *
 * 抽出来的原因：缩放/滑动判定塞在组件里只能靠人肉在浏览器里试，
 * 边界（放大后不该切图、竖滑误判、超出 3 倍上限）都没法回归。
 */

export const MIN_SCALE = 1;
export const MAX_SCALE = 3;
/** 横向滑动判定阈值（px） */
export const SWIPE_THRESHOLD = 50;
/** 放大到这个倍数以上就不再响应左右滑动，避免和缩放/平移抢手势 */
export const SWIPE_MAX_SCALE = 1.05;

export type Point = { x: number; y: number };
export type SwipeDirection = 'prev' | 'next' | null;

/**
 * 把缩放值夹在 [min, max] 并保留两位小数
 * - NaN 兜底为 min（没有有效输入时回到原始大小）
 * - ±Infinity 交给 min/max 处理（放大到无穷 → 取上限 3，反向 → 取下限 1）
 */
export function clampScale(v: number, min = MIN_SCALE, max = MAX_SCALE): number {
  if (Number.isNaN(v)) return min;
  return Math.min(max, Math.max(min, Number(v.toFixed(2))));
}

/** 两点距离（双指捏合用） */
export function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/**
 * 双指捏合后的缩放值：`startScale × (当前距离 / 起始距离)`，再夹到 [1,3]
 * 起始距离为 0（两指重合）时保持原值，避免除零得到 Infinity。
 */
export function pinchScale(startScale: number, startDistance: number, currentDistance: number): number {
  if (!startDistance || !Number.isFinite(startDistance) || !Number.isFinite(currentDistance)) {
    return clampScale(startScale);
  }
  return clampScale(startScale * (currentDistance / startDistance));
}

/**
 * 横向滑动判定：
 * - 放大状态下（> SWIPE_MAX_SCALE）不切图；
 * - 横向位移不足阈值不切图；
 * - 竖向分量超过横向的 1/1.2（即明显在上下滑）不切图；
 * - 手指向左拖（dx < 0）→ 下一张，向右拖 → 上一张。
 */
export function swipeDirection(
  dx: number,
  dy: number,
  threshold = SWIPE_THRESHOLD,
  scale = MIN_SCALE
): SwipeDirection {
  if (scale > SWIPE_MAX_SCALE) return null;
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return null;
  if (Math.abs(dx) < threshold) return null;
  if (Math.abs(dx) <= Math.abs(dy) * 1.2) return null;
  return dx < 0 ? 'next' : 'prev';
}
