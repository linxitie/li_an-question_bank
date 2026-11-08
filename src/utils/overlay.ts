/**
 * 管理端浮层层级（2026-11-08，验收缺陷修复）。
 *
 * 问题现场：在「改信息」弹窗里点「删除原件」，Element Plus 的确认框跑到了弹窗**下面**，
 * 看不见也点不到——因为我们的浮层写死 `z-index: 3000/3100`，
 * 而 Element Plus 的浮层从 **2000** 起算（`ElMessageBox` / `ElMessage` / 下拉等）。
 *
 * 解决思路：把"我们自己的浮层"和"EP 浮层"分层排好，且**只用这一处定义数值**：
 *
 *   1000 以下  页面/布局（侧栏、顶栏）
 *   3000       预览抽屉（`.mpd-root`）
 *   3100       管理端对话框（`.mmd-root` / `.mbu-root`）
 *   3200       EP 弹层：确认框 / 消息提示（必须压在对话框之上）
 *
 * 说明：CSS 里仍然写死数值（scoped 样式拿不到 TS 常量），
 * 所以改动这里时**同步改三个 `.vue` 的 z-index**；`overlay.spec.ts` 有顺序断言防呆。
 */
import { ElMessage, ElMessageBox, type ElMessageBoxOptions, type MessageOptions } from 'element-plus';

/** 预览抽屉 */
export const OVERLAY_Z = 3000;
/** 管理端对话框（改信息 / 批量导入） */
export const DIALOG_Z = 3100;
/** Element Plus 浮层起始层级（main.ts 里通过 provideGlobalConfig 设置）——必须高于 DIALOG_Z */
export const EP_Z = 5000;

/**
 * 覆盖在自定义对话框之上的确认框。
 *
 * 用法与 `ElMessageBox.confirm` 相同，只是**强制带上 zIndex**；
 * 取消时 EP 会 reject，调用方按原有习惯 `.catch(() => false)` 即可。
 */
export function confirmOverlay(
  message: string,
  title: string,
  options: ElMessageBoxOptions = {}
): Promise<unknown> {
  // 不传 zIndex：EP 2.x 的 MessageBox 选项里没有这个键（传了会被忽略/类型报错），
  // 层级由 main.ts 的 provideGlobalConfig({ zIndex: EP_Z }) 统一抬高。
  return ElMessageBox.confirm(message, title, options);
}

/** 在自定义对话框打开期间用的消息提示（同样需要压在对话框之上）。 */
export function notify(
  type: 'success' | 'error' | 'info' | 'warning',
  message: string,
  options: MessageOptions = {}
): unknown {
  return ElMessage({ ...options, type, message, zIndex: EP_Z });
}
