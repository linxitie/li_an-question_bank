/**
 * 练习记录（records）域事件契约。
 *
 * 本域不发布前端事件；订阅 `wrong-questions:changed` 作为练习提交后的
 * 增量刷新加速器（该事件由 ③ 答题练习在提交成功且新增错题时发出）。
 * 页面 onMounted 仍须主动 load()，事件丢失不影响正确性。
 */
import {
  EVENT_NAMES,
  onEvent,
  type WrongQuestionsChangedPayload
} from '@/stores/event-bus';

export const PUBLISHED_EVENTS = {} as const;

export const SUBSCRIBED_EVENTS = {
  WRONG_QUESTIONS_CHANGED: EVENT_NAMES.WRONG_QUESTIONS_CHANGED
} as const;

/** 后端行为 trigger_type（本域消费，不手写于调用点）。 */
export const RECORDS_TRIGGER_TYPES = {
  CREATED: 'practice.record.created'
} as const;

export function onRecordsChanged(
  handler: (payload: WrongQuestionsChangedPayload) => void
): () => void {
  return onEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, handler);
}
