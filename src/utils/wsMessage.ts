/**
 * WebSocket 消息解析与去重（F2 协议 v2）
 *
 * 后端信封：{ v, type, seq, scope, domain, entity, id, data, timestamp, origin }
 * 约束：只读解析，不依赖 window；旧字段 type/data/timestamp 永久兼容。
 */
import type { PapersDataChangedPayload } from '@/stores/event-bus';

/** 前端需要处理的报文类型；heartbeat/ack 等归为 other */
export type WsMessageKind = 'sync' | 'data-changed' | 'other';

/** v2 信封的可选字段形态（旧报文只有 type/data/timestamp） */
export interface WsEnvelope {
  v?: number;
  type: string;
  seq?: number;
  scope?: string;
  domain?: string;
  entity?: string;
  id?: number | string;
  data?: Record<string, unknown>;
  timestamp?: string;
  origin?: string;
}

/**
 * 把 WebSocket 原始数据解析成信封。
 * 非 JSON、非对象、缺 type 一律返回 null，由调用方静默忽略。
 */
export function parseWsMessage(raw: unknown): WsEnvelope | null {
  let value = raw;
  if (typeof raw === 'string') {
    try {
      value = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== 'object') return null;
  const msg = value as Record<string, unknown>;
  if (typeof msg.type !== 'string' || msg.type.length === 0) return null;
  return msg as unknown as WsEnvelope;
}

/** 报文分类：只区分 sync / data-changed / 其它 */
export function classify(msg: WsEnvelope): WsMessageKind {
  if (msg.type === 'sync') return 'sync';
  if (msg.type === 'data-changed') return 'data-changed';
  return 'other';
}

/**
 * 推导 scope：显式 scope 优先，其次 domain.entity.id / domain.entity / domain。
 * 与后端 derive_scope 保持同一规则，保证去重键一致。
 */
export function deriveScope(msg: WsEnvelope): string {
  if (typeof msg.scope === 'string' && msg.scope.length > 0) return msg.scope;
  if (!msg.domain) return 'global';
  if (typeof msg.id === 'number' || typeof msg.id === 'string') {
    return msg.entity ? msg.domain + '.' + msg.entity + '.' + msg.id : msg.domain + '.' + msg.id;
  }
  return msg.entity ? msg.domain + '.' + msg.entity : msg.domain;
}

const lastSeqByScope = new Map<string, number>();

/**
 * 同 scope 的 seq 去重：小于等于已见值的丢弃。
 * 无 seq（旧后端 / 旧报文）一律接受，避免升级期丢消息。
 */
export function acceptSeq(scope: string, seq?: number): boolean {
  if (typeof seq !== 'number' || !Number.isFinite(seq)) return true;
  const last = lastSeqByScope.get(scope);
  if (last !== undefined && seq <= last) return false;
  lastSeqByScope.set(scope, seq);
  return true;
}

/** 断线重连后清空，服务端 seq 回退时也能重新接收 */
export function resetSeq(): void {
  lastSeqByScope.clear();
}

/**
 * data-changed(domain=exam, entity=paper.published) → 试卷域事件载荷。
 * 业务事件类型在 entity（后端 v2 信封），旧报文可能只放在 data.type。
 */
export function toPapersEvent(msg: WsEnvelope): PapersDataChangedPayload | null {
  if (msg.type !== 'data-changed' || msg.domain !== 'exam') return null;
  const eventType =
    msg.entity ??
    (typeof msg.data?.type === 'string' ? msg.data.type : undefined);
  if (eventType !== 'paper.published') return null;
  const eventId =
    msg.id ??
    (typeof msg.data?.id === 'number' || typeof msg.data?.id === 'string'
      ? (msg.data.id as number | string)
      : undefined);
  return { domain: 'exam', type: 'paper.published', id: eventId, source: 'ws' };
}
