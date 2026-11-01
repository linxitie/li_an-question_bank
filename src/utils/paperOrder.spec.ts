import { describe, expect, it } from 'vitest';
import { displayOrder, insertAt, moveItem } from './paperOrder';

describe('paperOrder.moveItem', () => {
  it('向后移动时按移除后的目标下标落位', () => {
    expect(moveItem(['a', 'b', 'c', 'd'], 0, 2)).toEqual(['b', 'c', 'a', 'd']);
    expect(moveItem(['a', 'b', 'c', 'd'], 0, 3)).toEqual(['b', 'c', 'd', 'a']);
  });

  it('向前移动时保持目标下标语义', () => {
    expect(moveItem(['a', 'b', 'c', 'd'], 3, 1)).toEqual(['a', 'd', 'b', 'c']);
    expect(moveItem(['a', 'b', 'c', 'd'], 2, 0)).toEqual(['c', 'a', 'b', 'd']);
  });

  it('同位置或越界时返回等值的新数组', () => {
    const source = ['a', 'b'];
    expect(moveItem(source, 1, 1)).toEqual(source);
    expect(moveItem(source, -1, 1)).toEqual(source);
    expect(moveItem(source, 0, 2)).toEqual(source);
    expect(moveItem(source, 1, 1)).not.toBe(source);
  });
});

describe('paperOrder.insertAt', () => {
  it('插入首/中/尾', () => {
    expect(insertAt(['a', 'b'], 'x', 0)).toEqual(['x', 'a', 'b']);
    expect(insertAt(['a', 'b'], 'x', 1)).toEqual(['a', 'x', 'b']);
    expect(insertAt(['a', 'b'], 'x', 2)).toEqual(['a', 'b', 'x']);
  });

  it('越界时夹到两端', () => {
    expect(insertAt(['a'], 'x', -5)).toEqual(['x', 'a']);
    expect(insertAt(['a'], 'x', 99)).toEqual(['a', 'x']);
  });
});

describe('paperOrder.displayOrder', () => {
  it('用全量数组计算真实序号', () => {
    const list = [{ question_id: 11 }, { question_id: 22 }, { question_id: 33 }];
    expect(displayOrder(list, 11)).toBe(1);
    expect(displayOrder(list, 22)).toBe(2);
    expect(displayOrder(list, 33)).toBe(3);
  });

  it('找不到时返回 0，避免误显示为 1', () => {
    expect(displayOrder([{ question_id: 11 }], 99)).toBe(0);
  });
});
