import { describe, expect, it } from 'vitest';
import { extractOid, extractSyncReply } from '../wsMessage';

describe('extractOid', () => {
  it('只接受正整数 oid', () => {
    expect(extractOid({ type: 'data-changed', data: { oid: 12 } })).toBe(12);
    expect(extractOid({ type: 'data-changed', data: { oid: '12' } })).toBeNull();
    expect(extractOid({ type: 'data-changed', data: { oid: 0 } })).toBeNull();
    expect(extractOid({ type: 'data-changed', data: {} })).toBeNull();
  });
});

describe('extractSyncReply', () => {
  it('解析合法补发回复', () => {
    const reply = extractSyncReply({
      v: 2,
      type: 'sync',
      scope: 'sync',
      data: {
        reason: 'replay',
        events: [{ domain: 'exam', type: 'practice.submit', id: 'e1', oid: 9 }],
        latest_oid: 9,
        truncated: false
      }
    });
    expect(reply).toEqual({
      reason: 'replay',
      events: [{ domain: 'exam', type: 'practice.submit', id: 'e1', oid: 9 }],
      latestOid: 9,
      truncated: false
    });
  });

  it('truncated 或非法结构返回明确降级结果', () => {
    expect(
      extractSyncReply({
        type: 'sync',
        data: { reason: 'replay-truncated', events: [], latest_oid: 20, truncated: true }
      })
    ).toMatchObject({ truncated: true, reason: 'replay-truncated', latestOid: 20 });
    expect(extractSyncReply({ type: 'data-changed' })).toBeNull();
    expect(extractSyncReply({ type: 'sync', data: null as any })).toBeNull();
  });

  it('过滤掉缺 oid 的脏事件，避免污染游标', () => {
    const reply = extractSyncReply({
      type: 'sync',
      data: {
        reason: 'replay',
        events: [{ domain: 'exam', type: 'x', oid: 1 }, { domain: 'exam', type: 'y' }],
        latest_oid: 2,
        truncated: false
      }
    });
    expect(reply?.events).toHaveLength(1);
    expect(reply?.events[0].oid).toBe(1);
  });
});
