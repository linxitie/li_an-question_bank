/**
 * 错题集（wrongbook）域事件契约。
 *
 * 本域在掌握度流转（标记掌握 / 斩题）成功后发布 `wrong-questions:changed`，
 * 并订阅同一事件对其他域产生的错题变更做增量刷新。
 * 事件只是加速器：页面 onMounted 仍须主动 load()，事件丢失不影响正确性。
 */
import {
  EVENT_NAMES,
  emitEvent,
  onEvent,
  type WrongQuestionsChangedPayload
} from '@/stores/event-bus';

export const PUBLISHED_EVENTS = {
  WRONG_QUESTIONS_CHANGED: EVENT_NAMES.WRONG_QUESTIONS_CHANGED
} as const;

export const SUBSCRIBED_EVENTS = {
  WRONG_QUESTIONS_CHANGED: EVENT_NAMES.WRONG_QUESTIONS_CHANGED
} as const;

export const WRONGBOOK_TRIGGER_TYPES = {
  REVIEWED: 'wrong.reviewed'
} as const;

export function emitWrongQuestionsChanged(
  payload: WrongQuestionsChangedPayload = {}
): void {
  emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, {
    source: 'wrongbook',
    ...payload
  });
}

export function onWrongQuestionsChanged(
  handler: (payload: WrongQuestionsChangedPayload) => void
): () => void {
  return onEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, handler);
}
