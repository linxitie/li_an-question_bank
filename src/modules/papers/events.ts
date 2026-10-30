/**
 * 组卷与历年试卷（papers）域事件契约。
 *
 * 后端在试卷发布后推送 `data-changed`（domain=exam, type=paper.published, id=paper_id）；
 * 前端桥接为 `papers:data-changed`，本域订阅后做增量刷新。
 * 事件只是加速器：页面 onMounted 仍须主动 load()，事件丢失不影响正确性。
 */
import {
  EVENT_NAMES,
  emitEvent,
  onEvent,
  type PapersDataChangedPayload
} from '@/stores/event-bus';
import { toPapersEvent, type WsEnvelope } from '@/utils/wsMessage';

export const PUBLISHED_EVENTS = {} as const;

export const SUBSCRIBED_EVENTS = {
  PAPERS_DATA_CHANGED: EVENT_NAMES.PAPERS_DATA_CHANGED
} as const;

export const PAPERS_TRIGGER_TYPES = {
  COMPLETED: 'paper.completed'
} as const;

export function emitPapersDataChanged(
  payload: PapersDataChangedPayload = {}
): void {
  emitEvent(EVENT_NAMES.PAPERS_DATA_CHANGED, {
    source: 'papers',
    ...payload
  });
}

export function onPapersDataChanged(
  handler: (payload: PapersDataChangedPayload) => void
): () => void {
  return onEvent(EVENT_NAMES.PAPERS_DATA_CHANGED, handler);
}

/**
 * WS data-changed → papers:data-changed 桥接（F2）。
 * 只处理 exam.paper.published；返回是否命中，便于调用方统计。
 */
export function bridgeWsMessageToPapers(msg: WsEnvelope): boolean {
  const payload = toPapersEvent(msg);
  if (!payload) return false;
  emitPapersDataChanged(payload);
  return true;
}
