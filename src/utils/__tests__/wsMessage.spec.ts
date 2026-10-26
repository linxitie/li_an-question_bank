import { describe, expect, it, beforeEach } from 'vitest';
import {
  acceptSeq,
  classify,
  deriveScope,
  parseWsMessage,
  resetSeq,
  toPapersEvent
} from '../wsMessage';

const dataChanged = {
  v: 2,
  type: 'data-changed',
  seq: 42,
  scope: 'exam.paper.published',
  domain: 'exam',
  entity: 'paper.published',
  id: 7,
  data: { domain: 'exam', type: 'paper.published', id: 7 },
  timestamp: '2026-10-26T12:00:00'
};

beforeEach(() => resetSeq());

describe('parseWsMessage', () => {
  it('解析 JSON 字符串', () => {
    const msg = parseWsMessage(JSON.stringify({ type: 'sync', data: { a: 1 } }));
    expect(msg?.type).toBe('sync');
    expect(msg?.data?.a).toBe(1);
  });

  it('非法输入返回 null', () => {
    expect(parseWsMessage('not-json')).toBeNull();
    expect(parseWsMessage(null)).toBeNull();
    expect(parseWsMessage({ nope: 1 })).toBeNull();
    expect(parseWsMessage({ type: '' })).toBeNull();
  });
});

describe('classify / deriveScope', () => {
  it('区分三类报文', () => {
    expect(classify({ type: 'sync' })).toBe('sync');
    expect(classify({ type: 'data-changed' })).toBe('data-changed');
    expect(classify({ type: 'heartbeat' })).toBe('other');
  });

  it('scope 优先取显式值，其次按 domain/entity/id 推导', () => {
    expect(deriveScope({ type: 'sync', scope: 'given' })).toBe('given');
    expect(deriveScope({ type: 'sync' })).toBe('global');
    expect(deriveScope({ type: 'data-changed', domain: 'exam' })).toBe('exam');
    expect(deriveScope(dataChanged)).toBe('exam.paper.published');
    expect(deriveScope({ type: 'sync', domain: 'exam', entity: 'paper', id: 3 })).toBe(
      'exam.paper.3'
    );
  });
});

describe('acceptSeq', () => {
  it('同 scope 递增通过、重复与回退丢弃', () => {
    expect(acceptSeq('exam', 2)).toBe(true);
    expect(acceptSeq('exam', 2)).toBe(false);
    expect(acceptSeq('exam', 1)).toBe(false);
    expect(acceptSeq('exam', 3)).toBe(true);
  });

  it('不同 scope 各自计数', () => {
    expect(acceptSeq('a', 1)).toBe(true);
    expect(acceptSeq('b', 1)).toBe(true);
    expect(acceptSeq('a', 2)).toBe(true);
  });

  it('缺 seq 的旧报文一律接受', () => {
    expect(acceptSeq('exam', undefined)).toBe(true);
    expect(acceptSeq('exam', undefined)).toBe(true);
    expect(acceptSeq('exam', Number.NaN)).toBe(true);
  });
});

describe('toPapersEvent', () => {
  it('试卷发布事件映射为 papers 载荷', () => {
    expect(toPapersEvent(dataChanged)).toEqual({
      domain: 'exam',
      type: 'paper.published',
      id: 7,
      source: 'ws'
    });
  });

  it('非试卷域或非发布事件返回 null', () => {
    expect(toPapersEvent({ type: 'data-changed', domain: 'question', id: 1 })).toBeNull();
    expect(
      toPapersEvent({
        type: 'data-changed',
        domain: 'exam',
        entity: 'paper.completed',
        id: 1
      })
    ).toBeNull();
  });

  it('旧报文把业务类型放在 data 中也能识别', () => {
    expect(
      toPapersEvent({
        type: 'data-changed',
        domain: 'exam',
        data: { type: 'paper.published', id: 9 }
      })
    ).toEqual({ domain: 'exam', type: 'paper.published', id: 9, source: 'ws' });
  });
});
