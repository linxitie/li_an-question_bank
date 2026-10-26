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
}

const token = 'eyJhbGciOiJub25lIn0.eyJleHAiOjk5OTk5OTk5OTl9.';

function auth() {
  return (window as any).__VTJ_AUTH__;
}

async function flush() {
  await new Promise((resolve) => setTimeout(resolve, 20));
}

beforeEach(() => {
  FakeSocket.instances = [];
  localStorage.clear();
  vi.stubGlobal('WebSocket', FakeSocket);
});

afterEach(() => {
  auth().closeSyncSocket();
  vi.unstubAllGlobals();
});

describe('auth 同步 WebSocket', () => {
  it('同 scope 重复 seq 去重，重连后清空去重表并补一次全量同步', async () => {
    const events: any[] = [];
    const onSync = (event: Event) => events.push((event as CustomEvent).detail);
    window.addEventListener('__VTJ_SYNC__', onSync);

    auth().loginWithToken(token, '', 'tester');
    const first = FakeSocket.instances[0];
    first.open();

    const msg = { v: 2, type: 'data-changed', seq: 5, scope: 'question', domain: 'question', entity: 'updated', id: 1 };
    first.message(msg);
    first.message(msg);
    await flush();
    expect(events).toHaveLength(1);

    // 模拟网络断开：连接已关闭但 onclose 尚未把 _syncConnected 置回 false
    first.readyState = 3;
    auth().initSyncSocket();
    const second = FakeSocket.instances[1];
    second.open();
    await flush();
    expect(events[events.length - 1]).toMatchObject({ type: 'sync', data: { reason: 'ws-reconnect' } });

    second.message(msg);
    await flush();
    expect(events).toHaveLength(3);
    expect(events[events.length - 1]).toMatchObject({ type: 'data-changed', seq: 5 });

    window.removeEventListener('__VTJ_SYNC__', onSync);
  });
});
