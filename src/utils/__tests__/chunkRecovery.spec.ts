// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { isChunkLoadError } from '../chunkRecovery';

describe('chunkRecovery', () => {
  it('识别动态 import 失败（含浏览器缓存错误）', () => {
    expect(isChunkLoadError(new Error('Failed to fetch dynamically imported module: http://x/a.vue'))).toBe(true);
    expect(isChunkLoadError(new Error('net::ERR_CACHE_READ_FAILURE'))).toBe(true);
    expect(isChunkLoadError(new Error('ChunkLoadError: Loading chunk 3 failed'))).toBe(true);
  });

  it('业务异常不触发自动重载', () => {
    expect(isChunkLoadError(new Error('Cannot read properties of undefined'))).toBe(false);
    expect(isChunkLoadError('某个业务错误')).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
  });
});
