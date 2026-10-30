// @vitest-environment jsdom
import { describe, expect, it, afterEach, vi } from 'vitest';
import { createDataSyncListener, type DataSyncEvent } from '@/composables/useDataSync';

function emit(detail: Record<string, unknown>) {
  window.dispatchEvent(new CustomEvent('__VTJ_DATA_CHANGED__', { detail }));
}

afterEach(() => {
  vi.useRealTimers();
});

describe('useDataSync 监听器', () => {
  it('按 domain/type 过滤，并在防抖窗口内合并同事件', () => {
    vi.useFakeTimers();
    const batches: DataSyncEvent[][] = [];
    const listener = createDataSyncListener({
      domains: ['exam'],
      types: ['practice.submit'],
      debounceMs: 50,
      handler: (events) => batches.push(events)
    });

    emit({ type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 1 });
    emit({ type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 1 });
    emit({ type: 'data-changed', domain: 'exam', entity: 'paper.completed', id: 2 });
    emit({ type: 'data-changed', domain: 'news', entity: 'practice.submit', id: 3 });

    vi.advanceTimersByTime(49);
    expect(batches).toHaveLength(0);
    vi.advanceTimersByTime(1);
    expect(batches).toEqual([[{ domain: 'exam', type: 'practice.submit', id: 1 }]]);
    listener.stop();
  });

  it('不同 id 的同类型事件都会保留，stop 后不再回调', () => {
    vi.useFakeTimers();
    const batches: DataSyncEvent[][] = [];
    const listener = createDataSyncListener({
      debounceMs: 10,
      handler: (events) => batches.push(events)
    });

    emit({ type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 1 });
    emit({ type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 2 });
    vi.advanceTimersByTime(10);
    expect(batches[0]).toHaveLength(2);

    listener.stop();
    emit({ type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 3 });
    vi.advanceTimersByTime(10);
    expect(batches).toHaveLength(1);
  });

  it('缺少 domain/type 的脏事件被忽略', () => {
    vi.useFakeTimers();
    const handler = vi.fn();
    const listener = createDataSyncListener({ debounceMs: 10, handler });
    emit({ type: 'data-changed' });
    emit({ type: 'data-changed', domain: 'exam' });
    emit({ type: 'data-changed', domain: 'exam', entity: '' });
    vi.advanceTimersByTime(20);
    expect(handler).not.toHaveBeenCalled();
    listener.stop();
  });
});
