/**
 * 管理端资料「批量操作」的纯逻辑（A7，2026-11-08）。
 *
 * 为什么单独抽出来：批量条的状态（全选/半选/要改哪些行/结果文案）容易写错，
 * 抽成纯函数后可以直接单测，页面里只负责调接口与刷新。
 * 注意：**只作用于当前页**（不做跨页选择），这是 2026-11-08 定的范围。
 */
import type { AdminMaterialListItem } from '@/modules/library/api';

/** 批量上下架的目标状态（1=上架，0=下架） */
export type BatchStatus = 0 | 1;

/** 当前页是否全选（空列表不算全选） */
export function isAllSelected(
  rows: readonly AdminMaterialListItem[],
  selectedIds: readonly number[]
): boolean {
  if (rows.length === 0) return false;
  const picked = new Set(selectedIds);
  return rows.every((row) => picked.has(row.id));
}

/** 是否处于"半选"（有选中但没全选）——用于表头 indeterminate */
export function isPartialSelected(
  rows: readonly AdminMaterialListItem[],
  selectedIds: readonly number[]
): boolean {
  const picked = new Set(selectedIds);
  const hit = rows.filter((row) => picked.has(row.id)).length;
  return hit > 0 && hit < rows.length;
}

/** 点表头复选框：全选 ↔ 全不选（只影响当前页） */
export function toggleAll(
  rows: readonly AdminMaterialListItem[],
  selectedIds: readonly number[]
): number[] {
  return isAllSelected(rows, selectedIds) ? [] : rows.map((row) => row.id);
}

/** 点某行复选框 */
export function toggleOne(selectedIds: readonly number[], id: number): number[] {
  const picked = new Set(selectedIds);
  if (picked.has(id)) picked.delete(id);
  else picked.add(id);
  return [...picked];
}

/**
 * 批量上下架要真正请求的行：**状态已经等于目标值的跳过**，
 * 避免"批量上架 5 条"里有 3 条本来就在架上、白打 3 次请求（还会刷一次审计）。
 */
export function targetsForStatus(
  rows: readonly AdminMaterialListItem[],
  status: BatchStatus
): AdminMaterialListItem[] {
  return rows.filter((row) => row.status !== status);
}

/** 选中的行对象（保持列表顺序，便于结果提示与日志对齐） */
export function pickSelected(
  rows: readonly AdminMaterialListItem[],
  selectedIds: readonly number[]
): AdminMaterialListItem[] {
  const picked = new Set(selectedIds);
  return rows.filter((row) => picked.has(row.id));
}

export interface BatchOutcome {
  ok: number;
  fails: string[];
}

/**
 * 批量结果的提示文案。
 * 部分失败**不回滚已成功的部分**（服务端逐条提交），所以提示必须把"成功几条/失败几条"都说清，
 * 并列出前两条失败原因（更多折叠成「等 N 条」），避免只弹一句"操作失败"让人以为全挂了。
 */
export function batchSummary(
  label: string,
  outcome: BatchOutcome
): { level: 'success' | 'warning'; text: string } {
  const { ok, fails } = outcome;
  if (fails.length === 0) {
    return { level: 'success', text: `已批量${label} ${ok} 条` };
  }
  const head = fails.slice(0, 2).join('；');
  const more = fails.length > 2 ? `；等 ${fails.length} 条` : '';
  const okPart = ok > 0 ? `成功 ${ok} 条，` : '';
  return { level: 'warning', text: `${okPart}失败 ${fails.length} 条：${head}${more}` };
}
