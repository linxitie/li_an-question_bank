/**
 * 每日签到（checkin）域事件契约（P2-49）。
 *
 * 本域发布 `reward:coins-changed`：签到成功发放金币后广播，
 * 供「我的」与商城余额快照刷新；本域不订阅其他域事件。
 * 事件名一律取自 @/stores/event-bus 的 EVENT_NAMES，不手写字符串字面量。
 * 后端 E10 `checkin.done` 由签到 API 在事务提交后上报，前端不重复上报。
 */
import {
  EVENT_NAMES,
  emitEvent,
  type RewardCoinsChangedPayload
} from '@/stores/event-bus';

export const PUBLISHED_EVENTS = {
  REWARD_COINS_CHANGED: EVENT_NAMES.REWARD_COINS_CHANGED
} as const;

export const SUBSCRIBED_EVENTS = {} as const;

export const CHECKIN_TRIGGER_TYPES = {
  CHECKIN_DONE: 'checkin.done'
} as const;

export const CHECKIN_DONE_TRIGGER = CHECKIN_TRIGGER_TYPES.CHECKIN_DONE;

export function notifyCoinsChanged(
  payload: RewardCoinsChangedPayload
): void {
  emitEvent(EVENT_NAMES.REWARD_COINS_CHANGED, payload);
}
