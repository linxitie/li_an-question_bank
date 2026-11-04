/**
 * 全图查看器手势算法单测（纯函数，不依赖 DOM）
 * 背景：平板实测「无触摸手势」是 P1 问题，补实现后这些边界必须有回归。
 */
import { describe, expect, it } from 'vitest';
import {
  clampScale,
  distance,
  pinchScale,
  swipeDirection,
  MAX_SCALE,
  MIN_SCALE,
  SWIPE_THRESHOLD
} from '../lightboxGesture';

describe('clampScale', () => {
  it('夹在 1~3 之间', () => {
    expect(clampScale(0.2)).toBe(MIN_SCALE);
    expect(clampScale(9)).toBe(MAX_SCALE);
    expect(clampScale(1.75)).toBe(1.75);
  });

  it('保留两位小数', () => {
    expect(clampScale(1.23456)).toBe(1.23);
  });

  it('非数字兜底为最小值', () => {
    expect(clampScale(Number.NaN)).toBe(MIN_SCALE);
    expect(clampScale(Number.POSITIVE_INFINITY)).toBe(MAX_SCALE);
  });
});

describe('distance', () => {
  it('3-4-5 直角三角形', () => {
    expect(distance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5);
  });
});

describe('pinchScale', () => {
  it('两指张开 2 倍 → 缩放翻倍', () => {
    expect(pinchScale(1, 100, 200)).toBe(2);
  });

  it('两指捏合到一半 → 缩小但不下于 1', () => {
    expect(pinchScale(1, 100, 50)).toBe(1);
    expect(pinchScale(2, 100, 50)).toBe(1);
  });

  it('不会超过 3 倍上限', () => {
    expect(pinchScale(1, 100, 800)).toBe(MAX_SCALE);
  });

  it('起始间距为 0 时保持原值（避免除零）', () => {
    expect(pinchScale(1.5, 0, 200)).toBe(1.5);
    expect(pinchScale(1.5, Number.NaN, 200)).toBe(1.5);
  });
});

describe('swipeDirection', () => {
  it('向左滑 → 下一张', () => {
    expect(swipeDirection(-80, 4)).toBe('next');
  });

  it('向右滑 → 上一张', () => {
    expect(swipeDirection(80, -4)).toBe('prev');
  });

  it('不足阈值不切图', () => {
    expect(swipeDirection(SWIPE_THRESHOLD - 1, 0)).toBeNull();
    expect(swipeDirection(-20, 0)).toBeNull();
  });

  it('明显是竖向滑动时不算切图', () => {
    expect(swipeDirection(-60, 120)).toBeNull();
  });

  it('放大状态下不切图（避免和缩放抢手势）', () => {
    expect(swipeDirection(-120, 0, undefined, 1.5)).toBeNull();
    expect(swipeDirection(-120, 0, undefined, 1.02)).toBe('next');
  });

  it('非数字输入返回 null', () => {
    expect(swipeDirection(Number.NaN, 0)).toBeNull();
  });
});
