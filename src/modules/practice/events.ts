/**
 * 答题练习（practice）域事件契约。
 *
 * 跨域只走 @/stores/event-bus；事件名一律取自 EVENT_NAMES，
 * 本文件不手写事件字符串字面量，也不建立常驻订阅。
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

export const SUBSCRIBED_EVENTS = {} as const;

export const PRACTICE_TRIGGER_TYPES = {
  SUBMIT: 'practice.submit'
} as const;

export function emitWrongQuestionsChanged(
  payload: WrongQuestionsChangedPayload = {}
): void {
  emitEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, {
    source: 'practice',
    action: 'added',
    ...payload
  });
}

export function onWrongQuestionsChanged(
  handler: (payload: WrongQuestionsChangedPayload) => void
): () => void {
  return onEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, handler);
}
