/**
 * 从各种 rejection 里取出**给用户看的那句话**（2026-11-08）。
 *
 * 为什么需要它：`apiClient` 的错误经过拦截器归一化后是 **普通对象**
 * （`{ type, message, status, code, details }`，见 `services/api/types.ts`），
 * **不是 `Error` 实例**。所以业务代码里写 `e instanceof Error ? e.message : '保存失败'`
 * 会永远走到兜底分支——用户只看到「保存失败」，看不到后端 400 的真实原因
 * （如「year 需在 1990–2100 之间，收到 1800」）。C2b 验收时就是这样暴露的。
 *
 * 兼容的四种形态：
 *   1. `Error` 实例 → `message`
 *   2. 归一化对象 `{ message }` → `message`（为空再看 `details.detail`）
 *   3. 后端原始错误体 `{ error: { message } }` → `error.message`
 *   4. 字符串 → 原样
 * 都没有才用调用方给的兜底文案。
 */
export function errorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'string') return error.trim() || fallback;
  if (error && typeof error === 'object') {
    const obj = error as Record<string, unknown>;
    const own = obj.message;
    if (typeof own === 'string' && own.trim()) return own.trim();

    const nested = obj.error as Record<string, unknown> | undefined;
    if (nested && typeof nested.message === 'string' && nested.message.trim()) {
      return nested.message.trim();
    }
    const details = obj.details as Record<string, unknown> | undefined;
    if (details && typeof details.detail === 'string' && details.detail.trim()) {
      return details.detail.trim();
    }
  }
  return fallback;
}
