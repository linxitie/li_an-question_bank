/**
 * 共享事件总线（P1-09）
 *
 * 规则（强制）：
 *   1. 事件名一律采用 `<域>:<过去式动作>`，域用 kebab-case，冒号分隔。
 *   2. **新增事件常量必须在本文件 EVENT_NAMES 中登记**，禁止在组件 / store / 模块内
 *      手写事件字符串字面量（`emit('xxx')` / `on('xxx')` 一律不允许）。
 *   3. 跨域通信只走本总线；同域内部调用直接调函数，不绕事件。
 *
 * 用法：
 *   import { emitEvent, onEvent, EVENT_NAMES } from '@/stores/event-bus';
 *   emitEvent(EVENT_NAMES.REWARD_COINS_CHANGED, { coins: 120 });
 *   const off = onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (p) => { ... });
 *   off(); // 取消订阅
 */
import mitt, { type Emitter, type Handler } from 'mitt';

/** 事件常量登记表（唯一事实来源） */
export const EVENT_NAMES = {
  /** 错题集合发生变化（练习提交、错题重练、掌握度变更） */
  WRONG_QUESTIONS_CHANGED: 'wrong-questions:changed',
  /** 金币余额发生变化（奖励发放、消费） */
  REWARD_COINS_CHANGED: 'reward:coins-changed',
  /** 成就解锁（成长域广播，通知 / 徽章消费） */
  GROWTH_ACHIEVEMENT_UNLOCKED: 'growth:achievement-unlocked'
} as const;

/** 全部合法事件名 */
export type EventName = (typeof EVENT_NAMES)[keyof typeof EVENT_NAMES];

/** 错题变更载荷 */
export interface WrongQuestionsChangedPayload {
  /** 题目 ID（可选，批量变更时可缺省） */
  questionId?: number | string;
  /** 变更类型 */
  action?: 'added' | 'removed' | 'reviewed' | 'mastered';
  /** 触发来源域，便于排查链路 */
  source?: string;
}

/** 金币变更载荷 */
export interface RewardCoinsChangedPayload {
  /** 变更后的余额快照 */
  coins?: number;
  /** 本次增减量（正数增加、负数扣减） */
  delta?: number;
  /** 变更原因 */
  reason?: string;
}

/** 成就解锁载荷 */
export interface GrowthAchievementUnlockedPayload {
  achievementId?: number | string;
  title?: string;
  /** 解锁时间戳（毫秒） */
  unlockedAt?: number;
}

/** 事件名 -> 载荷类型映射（键取自 EVENT_NAMES，不重复字面量） */
export interface EventPayloads {
  [EVENT_NAMES.WRONG_QUESTIONS_CHANGED]: WrongQuestionsChangedPayload;
  [EVENT_NAMES.REWARD_COINS_CHANGED]: RewardCoinsChangedPayload;
  [EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED]: GrowthAchievementUnlockedPayload;
}

/** mitt 要求的事件表类型 */
export type EventMap = { [K in EventName]: EventPayloads[K] };

/** 全局唯一 mitt 实例 */
export const eventBus: Emitter<EventMap> = mitt<EventMap>();

/**
 * 发布事件（类型化封装，禁止直接用 eventBus.emit）
 */
export function emitEvent<K extends EventName>(type: K, payload: EventPayloads[K]): void {
  eventBus.emit(type, payload);
}

/**
 * 订阅事件（类型化封装）
 * @returns 取消订阅函数
 */
export function onEvent<K extends EventName>(
  type: K,
  handler: Handler<EventPayloads[K]>
): () => void {
  eventBus.on(type, handler);
  return () => {
    eventBus.off(type, handler);
  };
}

/** 取消订阅（对称于 onEvent） */
export function offEvent<K extends EventName>(
  type: K,
  handler: Handler<EventPayloads[K]>
): void {
  eventBus.off(type, handler);
}

/** 清空所有订阅（仅测试 / 应用销毁时使用） */
export function clearAllEvents(): void {
  eventBus.all.clear();
}

// 便于调用方直接按常量名引用（与 EVENT_NAMES 完全等价，不产生第二份字面量）
export const WRONG_QUESTIONS_CHANGED = EVENT_NAMES.WRONG_QUESTIONS_CHANGED;
export const REWARD_COINS_CHANGED = EVENT_NAMES.REWARD_COINS_CHANGED;
export const GROWTH_ACHIEVEMENT_UNLOCKED = EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED;
