/**
 * 成就成长（growth）域事件契约（P2-55）。
 *
 * - 发布 `growth:achievement-unlocked`：成就从「未获得」变为「已获得」时广播；
 * - 订阅 `wrong-questions:changed`：只触发成就页增量刷新，不重拉目标/任务；
 * - 事件名一律取自 `@/stores/event-bus`，不手写字符串字面量；
 * - 本域是成就枢纽，禁止 import 任何业务域，事件是唯一跨域入口。
 */
import {
  EVENT_NAMES,
  emitEvent,
  onEvent,
  type GrowthAchievementUnlockedPayload
} from '@/stores/event-bus';

export const PUBLISHED_EVENTS = {
  GROWTH_ACHIEVEMENT_UNLOCKED: EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED
} as const;

export const SUBSCRIBED_EVENTS = {
  WRONG_QUESTIONS_CHANGED: EVENT_NAMES.WRONG_QUESTIONS_CHANGED
} as const;

export const GROWTH_TRIGGER_TYPES = [
  'practice.submit',
  'practice.record.created',
  'paper.completed',
  'wrong.reviewed',
  'note.created',
  'favorite.added',
  'forum.posted',
  'news.read',
  'material.opened',
  'shop.purchased',
  'checkin.done'
] as const;

export type GrowthTriggerType = (typeof GROWTH_TRIGGER_TYPES)[number];

export function notifyAchievementUnlocked(
  payload: GrowthAchievementUnlockedPayload
): void {
  emitEvent(EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED, payload);
}

export function subscribeGrowthEvents(
  onWrongQuestionsChanged: () => void
): () => void {
  return onEvent(EVENT_NAMES.WRONG_QUESTIONS_CHANGED, () => {
    onWrongQuestionsChanged();
  });
}
