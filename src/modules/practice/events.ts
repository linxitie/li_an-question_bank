/**
 * 答题练习（practice）域事件契约外壳 —— scripts/scaffold-module.mjs 生成（P1-13）
 *
 * 当前状态：仅登记计划，不建立任何订阅，也不触发任何事件（P2 阶段实现）。
 *
 * 约束：
 *   1. 前端事件常量一律在 @/stores/event-bus 的 EVENT_NAMES 登记，禁止手写事件名字面量；
 *   2. 本文件不建立订阅，P2 阶段在域入口调用 onEvent 并保留取消订阅函数；
 *   3. 跨域只走事件总线，同域内部直接调用函数，不绕事件。
 */
import { EVENT_NAMES } from '@/stores/event-bus';

/**
 * 本域计划发布的前端事件（仅登记常量，不触发）：
 * - WRONG_QUESTIONS_CHANGED：作答提交成功后发布，通知错题域与成就域
 */
export const PUBLISHED_EVENTS = {
  WRONG_QUESTIONS_CHANGED: EVENT_NAMES.WRONG_QUESTIONS_CHANGED
} as const;

/** 本域不订阅前端事件。 */
export const SUBSCRIBED_EVENTS = {} as const;

/**
 * 本域向后端 record_user_action() 上报的 trigger_type（P2 阶段补齐调用点）：
 * - practice.submit：答题提交成功后上报（成就 E1）
 */

/** 本域消费的后端行为 trigger_type：无。 */
