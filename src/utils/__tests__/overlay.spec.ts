import { describe, expect, it, vi } from 'vitest';

/**
 * 层级不变量（2026-11-08 验收缺陷）：改信息弹窗里点「删除原件」，EP 确认框跑到弹窗下面，
 * 看不见也点不到。根因：自绘浮层写死 3000/3100，而 Element Plus 浮层默认从 2000 起算。
 * 修法：`main.ts` 里 `provideGlobalConfig({ zIndex: 5000 })` 抬高整族 EP 浮层。
 * 本用例锁死"数值顺序"，改了常量却忘了改 CSS/全局配置时会红。
 */
vi.mock('element-plus', async (orig) => {
  const actual = await orig<typeof import('element-plus')>();
  return {
    ...actual,
    ElMessage: vi.fn(),
    ElMessageBox: { confirm: vi.fn(async () => 'confirm') }
  };
});

import { ElMessage, ElMessageBox } from 'element-plus';
import { confirmOverlay, DIALOG_Z, EP_Z, notify, OVERLAY_Z } from '../overlay';

describe('overlay 层级不变量', () => {
  it('预览抽屉 < 对话框 < Element Plus 浮层', () => {
    expect(OVERLAY_Z).toBeLessThan(DIALOG_Z);
    expect(DIALOG_Z).toBeLessThan(EP_Z);
    expect(EP_Z - DIALOG_Z).toBeGreaterThanOrEqual(1000);
  });

  it('confirmOverlay 透传选项，但不塞 EP 不支持的 zIndex', async () => {
    await confirmOverlay('确定删除？', '删除原件', { confirmButtonText: '删除' });
    const call = vi.mocked(ElMessageBox.confirm).mock.calls[0];
    expect(call[1]).toBe('删除原件');
    expect(call[2]).toMatchObject({ confirmButtonText: '删除' });
    expect(call[2]).not.toHaveProperty('zIndex');
  });

  it('notify 统一带上 EP_Z（压在自绘对话框之上）', () => {
    notify('success', '已保存');
    expect(vi.mocked(ElMessage)).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'success', message: '已保存', zIndex: EP_Z })
    );
  });
});
