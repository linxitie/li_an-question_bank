import { describe, expect, it } from 'vitest';

import { forEachConcurrent } from '../concurrency';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe('forEachConcurrent', () => {
  it('每个元素恰好处理一次，顺序按索引', async () => {
    const seen: number[] = [];
    await forEachConcurrent([1, 2, 3, 4, 5], 2, async (n) => {
      seen.push(n);
    });
    expect(seen.sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5]);
  });

  it('并发数不超过 limit', async () => {
    let running = 0;
    let peak = 0;
    await forEachConcurrent([1, 2, 3, 4, 5, 6], 2, async () => {
      running += 1;
      peak = Math.max(peak, running);
      await sleep(5);
      running -= 1;
    });
    expect(peak).toBe(2);
  });

  it('limit 大于元素数时按元素数并发', async () => {
    let peak = 0;
    let running = 0;
    await forEachConcurrent([1, 2], 8, async () => {
      running += 1;
      peak = Math.max(peak, running);
      await sleep(5);
      running -= 1;
    });
    expect(peak).toBe(2);
  });

  it('空数组直接返回', async () => {
    let called = 0;
    await forEachConcurrent([], 2, async () => {
      called += 1;
    });
    expect(called).toBe(0);
  });

  it('worker 抛错会向上冒泡（调用方自己 try/catch）', async () => {
    await expect(
      forEachConcurrent([1, 2, 3], 2, async (n) => {
        if (n === 2) throw new Error('boom');
      })
    ).rejects.toThrow('boom');
  });
});
