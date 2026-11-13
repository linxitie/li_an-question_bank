/**
 * 有界并发（S-B，2026-11-13）。
 *
 * 为什么不用 `Promise.all(items.map(worker))`：批量上传一次最多 50 个文件，全并发会把
 * 50 个请求同时甩给后端（每个还要解析/写库），既容易超时也抢 CPU；
 * 这里固定"最多 N 个在飞"，其余排队。
 *
 * 与 `Promise.all` 的差别：某个 worker 抛错时**不会**取消其它在跑的（已发出的请求收不回来），
 * 错误会向上抛给调用方——批量上传里我们自己在 worker 内 try/catch，所以不会中断整批。
 */

export async function forEachConcurrent<T>(
  items: readonly T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>
): Promise<void> {
  const total = items.length;
  if (total === 0) return;
  const width = Math.max(1, Math.min(Math.floor(limit) || 1, total));
  let cursor = 0;

  const run = async (): Promise<void> => {
    for (;;) {
      const index = cursor;
      cursor += 1;
      if (index >= total) return;
      await worker(items[index], index);
    }
  };

  await Promise.all(Array.from({ length: width }, run));
}
