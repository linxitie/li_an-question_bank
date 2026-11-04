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

/** 补发事件：只带恢复刷新所需的最小字段，不携带 payload/他人隐私。 */
export interface SyncReplayEvent {
  domain: string;
  type: string;
  id?: number | string;
  oid: number;
}

export interface SyncReplay {
  reason: string;
  events: SyncReplayEvent[];
  latestOid: number;
  truncated: boolean;
}

/** data-changed 的 oid 游标；缺失/非法一律返回 null，旧报文继续可用。 */
export function extractOid(msg: WsEnvelope): number | null {
  const value = msg.data?.oid;
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return null;
  if (!Number.isInteger(value)) return null;
  return value;
}

/** 解析服务端 sync 补发回复；结构非法返回 null，由调用方走全量兜底。 */
export function extractSyncReply(msg: WsEnvelope): SyncReplay | null {
  if (msg.type !== 'sync' || !msg.data || typeof msg.data !== 'object') return null;
  const data = msg.data;
  const latest = data.latest_oid;
  if (typeof data.reason !== 'string') return null;
  if (typeof latest !== 'number' || !Number.isFinite(latest) || latest < 0) return null;
  const rawEvents = Array.isArray(data.events) ? data.events : [];
  const events: SyncReplayEvent[] = [];
  for (const raw of rawEvents) {
    if (!raw || typeof raw !== 'object') continue;
    const item = raw as Record<string, unknown>;
    if (typeof item.domain !== 'string' || typeof item.type !== 'string') continue;
    if (typeof item.oid !== 'number' || !Number.isInteger(item.oid) || item.oid <= 0) continue;
    events.push({
      domain: item.domain,
      type: item.type,
      id: item.id as number | string | undefined,
      oid: item.oid
    });
  }
  return {
    reason: data.reason,
    events,
    latestOid: latest,
    truncated: data.truncated === true
  };
}
