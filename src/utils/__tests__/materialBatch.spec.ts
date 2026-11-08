import { describe, expect, it } from 'vitest';
import type { AdminMaterialListItem } from '@/modules/library/api';
import {
  batchSummary,
  isAllSelected,
  isPartialSelected,
  pickSelected,
  targetsForStatus,
  toggleAll,
  toggleOne
} from '../materialBatch';

function row(id: number, status: number): AdminMaterialListItem {
  return { id, status } as AdminMaterialListItem;
}

const rows = [row(1, 1), row(2, 0), row(3, 1)];

describe('批量选择（A7）', () => {
  it('全选/半选判定', () => {
    expect(isAllSelected(rows, [])).toBe(false);
    expect(isAllSelected(rows, [1, 2, 3])).toBe(true);
    expect(isPartialSelected(rows, [2])).toBe(true);
    expect(isPartialSelected(rows, [1, 2, 3])).toBe(false);
    expect(isAllSelected([], [])).toBe(false);
  });

  it('表头复选框：全选 ↔ 全不选，只影响当前页', () => {
    expect(toggleAll(rows, [])).toEqual([1, 2, 3]);
    expect(toggleAll(rows, [1, 2, 3])).toEqual([]);
    // 半选时点表头 = 全选（不是清空）
    expect(toggleAll(rows, [9])).toEqual([1, 2, 3]);
  });

  it('单行勾选/取消，保持已选顺序', () => {
    expect(toggleOne([1], 2)).toEqual([1, 2]);
    expect(toggleOne([1, 2], 1)).toEqual([2]);
  });
});

describe('批量上下架的目标筛选', () => {
  it('跳过已经处于目标状态的行（避免白打请求 + 白刷审计）', () => {
    expect(targetsForStatus(rows, 1).map((r) => r.id)).toEqual([2]);
    expect(targetsForStatus(rows, 0).map((r) => r.id)).toEqual([1, 3]);
  });

  it('全部同状态时目标为空', () => {
    expect(targetsForStatus([row(1, 1)], 1)).toEqual([]);
  });

  it('pickSelected 保持列表顺序（不是勾选顺序）', () => {
    expect(pickSelected(rows, [3, 1]).map((r) => r.id)).toEqual([1, 3]);
  });
});

describe('批量结果文案', () => {
  it('全部成功 → success', () => {
    expect(batchSummary('上架', { ok: 5, fails: [] }))
      .toEqual({ level: 'success', text: '已批量上架 5 条' });
  });

  it('部分失败 → warning，含成功数与前两条原因', () => {
    const r = batchSummary('下架', { ok: 3, fails: ['A：网络错误', 'B：403', 'C：404'] });
    expect(r.level).toBe('warning');
    expect(r.text).toContain('成功 3 条');
    expect(r.text).toContain('失败 3 条');
    expect(r.text).toContain('A：网络错误');
    expect(r.text).toContain('等 3 条');
  });

  it('全部失败 → warning，不出现"成功 0 条"', () => {
    const r = batchSummary('删除', { ok: 0, fails: ['X：失败'] });
    expect(r.level).toBe('warning');
    expect(r.text.startsWith('失败 1 条')).toBe(true);
    expect(r.text).not.toContain('成功 0 条');
  });
});
