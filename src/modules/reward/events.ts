/**
 * 金币商城（reward）域事件契约（P2-43）
 *
 * 本域发布 `reward:coins-changed`：兑换成功或金币余额变化后广播，
 * 供 user-profile 只读快照刷新；本域不订阅其他域事件。
 * 事件名一律取自 @/stores/event-bus 的 EVENT_NAMES，不手写字符串字面量。
 * 后端行为 trigger_type `shop.purchased`（E9）由 API 在兑换事务提交后上报，
 * 前端不重复上报，避免「前端事件 + 后端事件」双写。
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

export const REWARD_TRIGGER_TYPES = {
  SHOP_PURCHASED: 'shop.purchased'
} as const;

export const REWARD_SHOP_PURCHASED_TRIGGER =
  REWARD_TRIGGER_TYPES.SHOP_PURCHASED;

/** 广播金币余额变化（兑换成功、任务奖励等） */
export function notifyCoinsChanged(payload: RewardCoinsChangedPayload): void {
  emitEvent(EVENT_NAMES.REWARD_COINS_CHANGED, payload);
}
