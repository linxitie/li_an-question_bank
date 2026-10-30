// @vitest-environment jsdom
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import '@/auth';

class FakeSocket {
  static instances: FakeSocket[] = [];
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  message(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  sentJson() {
    return this.sent.map((raw) => JSON.parse(raw));
  }
}

const token = 'eyJhbGciOiJub25lIn0.eyJleHAiOjk5OTk5OTk5OTl9.';

function auth() {
  return (window as any).__VTJ_AUTH__;
}

async function flush() {
  await new Promise((resolve) => setTimeout(resolve, 20));
}

function collect(): { sync: any[]; typed: any[]; off: () => void } {
  const sync: any[] = [];
  const typed: any[] = [];
  const onSync = (event: Event) => sync.push((event as CustomEvent).detail);
  const onTyped = (event: Event) => typed.push((event as CustomEvent).detail);
  window.addEventListener('__VTJ_SYNC__', onSync);
  window.addEventListener('__VTJ_DATA_CHANGED__', onTyped);
  return {
    sync,
    typed,
    off: () => {
      window.removeEventListener('__VTJ_SYNC__', onSync);
      window.removeEventListener('__VTJ_DATA_CHANGED__', onTyped);
    }
  };
}

/** 建连 -> 收到一条带 oid 的在线事件 -> 断网重连，返回新连接 */
function reconnectAfterLiveEvent(oid: number): FakeSocket {
  auth().loginWithToken(token, '', 'tester');
  const first = FakeSocket.instances[0];
  first.open();
  first.message({
    v: 2,
    type: 'data-changed',
    seq: 1,
    scope: 'exam.practice.submit.1',
    domain: 'exam',
    entity: 'practice.submit',
    id: 1,
    data: { oid }
  });
  first.readyState = 3;
  auth().initSyncSocket();
  const second = FakeSocket.instances[1];
  second.open();
  return second;
}

beforeEach(() => {
  FakeSocket.instances = [];
  localStorage.clear();
  vi.stubGlobal('WebSocket', FakeSocket);
});

afterEach(() => {
  auth().closeSyncSocket();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('auth 同步 WebSocket', () => {
  it('同 scope 重复 seq 去重，重连后清空去重表并补一次全量同步', async () => {
    const seen = collect();
    auth().loginWithToken(token, '', 'tester');
    const first = FakeSocket.instances[0];
    first.open();

    const msg = { v: 2, type: 'data-changed', seq: 5, scope: 'question', domain: 'question', entity: 'updated', id: 1 };
    first.message(msg);
    first.message(msg);
    await flush();
    expect(seen.sync).toHaveLength(1);

    first.readyState = 3;
    auth().initSyncSocket();
    const second = FakeSocket.instances[1];
    second.open();
    await flush();
    expect(seen.sync[seen.sync.length - 1]).toMatchObject({ type: 'sync', data: { reason: 'ws-reconnect' } });

    second.message(msg);
    await flush();
    expect(seen.sync).toHaveLength(3);
    expect(seen.sync[seen.sync.length - 1]).toMatchObject({ type: 'data-changed', seq: 5 });
    seen.off();
  });

  it('有游标时重连发 sync since，补发非空时兼容旧页并逐条发 typed 事件', async () => {
    const seen = collect();
    const second = reconnectAfterLiveEvent(7);
    seen.sync.length = 0;
    seen.typed.length = 0;

    expect(second.sentJson()).toContainEqual({ type: 'sync', data: { since: 7, limit: 200 } });
    second.message({
      v: 2,
      type: 'sync',
      scope: 'sync',
      data: {
        reason: 'replay',
        events: [{ domain: 'exam', type: 'practice.submit', id: 2, oid: 8 }],
        latest_oid: 8,
        truncated: false
      }
    });
    await flush();
    expect(seen.sync.filter((d) => d.type === 'sync')).toHaveLength(1);
    expect(seen.typed).toEqual([{ type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 2 }]);

    // 游标推进到 latest_oid，下次重连从 8 开始
    second.readyState = 3;
    auth().initSyncSocket();
    const third = FakeSocket.instances[2];
    third.open();
    expect(third.sentJson()).toContainEqual({ type: 'sync', data: { since: 8, limit: 200 } });
    seen.off();
  });

  it('truncated 只做一次全量并推进游标，不逐条 typed 刷新', async () => {
    const seen = collect();
    const second = reconnectAfterLiveEvent(5);
    seen.sync.length = 0;
    seen.typed.length = 0;

    second.message({
      v: 2,
      type: 'sync',
      data: { reason: 'replay-truncated', events: [], latest_oid: 9, truncated: true }
    });
    await flush();
    expect(seen.sync.filter((d) => d.type === 'sync')).toHaveLength(1);
    expect(seen.typed).toHaveLength(0);

    second.readyState = 3;
    auth().initSyncSocket();
    const third = FakeSocket.instances[2];
    third.open();
    expect(third.sentJson()).toContainEqual({ type: 'sync', data: { since: 9, limit: 200 } });
    seen.off();
  });

  it('旧服务端不识别 sync 时 2.5s 兜底全量', async () => {
    vi.useFakeTimers();
    const seen = collect();
    reconnectAfterLiveEvent(3);
    seen.sync.length = 0;
    expect(seen.sync).toHaveLength(0);

    vi.advanceTimersByTime(2500);
    expect(seen.sync).toHaveLength(1);
    expect(seen.sync[0]).toMatchObject({ type: 'sync', data: { reason: 'ws-reconnect' } });
    seen.off();
  });

  it('在线 oid 乱序/重复时游标只增不回退', async () => {
    auth().loginWithToken(token, '', 'tester');
    const first = FakeSocket.instances[0];
    first.open();
    const base = { v: 2, type: 'data-changed', domain: 'exam', entity: 'practice.submit', id: 1 };
    first.message({ ...base, seq: 1, scope: 'exam.practice.submit.1', data: { oid: 9 } });
    first.message({ ...base, seq: 2, scope: 'exam.practice.submit.1', data: { oid: 4 } });
    first.message({ ...base, seq: 3, scope: 'exam.practice.submit.1', data: { oid: 9 } });

    first.readyState = 3;
    auth().initSyncSocket();
    const second = FakeSocket.instances[1];
    second.open();
    expect(second.sentJson()).toContainEqual({ type: 'sync', data: { since: 9, limit: 200 } });
  });

  it('登出清空游标：重新登录后的重连不再发 sync', async () => {
    auth().loginWithToken(token, '', 'tester');
    const first = FakeSocket.instances[0];
    first.open();
    first.message({
      v: 2,
      type: 'data-changed',
      seq: 1,
      scope: 'exam.practice.submit.1',
      domain: 'exam',
      entity: 'practice.submit',
      id: 1,
      data: { oid: 12 }
    });

    auth().logout();
    auth().loginWithToken(token, '', 'tester');
    const relogin = FakeSocket.instances[1];
    relogin.open();
    relogin.readyState = 3;
    auth().initSyncSocket();
    const next = FakeSocket.instances[2];
    next.open();

    // 游标已清空 -> 走 F2 全量兜底，而不是携带旧游标发 sync
    expect(next.sentJson().some((m: any) => m.type === 'sync' && m.data && 'since' in m.data)).toBe(false);
  });
});
