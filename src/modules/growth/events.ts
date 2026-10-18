/**
 * 成就成长（growth）域事件契约外壳 —— scripts/scaffold-module.mjs 生成（P1-13）
 *
 * 当前状态：仅登记计划，不建立任何订阅，也不触发任何事件（P2 阶段实现）。
 *
 * 说明：本域是成就枢纽：只消费后端行为事件，禁止 import 任何业务域。
 *
 * 约束：
 *   1. 前端事件常量一律在 @/stores/event-bus 的 EVENT_NAMES 登记，禁止手写事件名字面量；
 *   2. 本文件不建立订阅，P2 阶段在域入口调用 onEvent 并保留取消订阅函数；
 *   3. 跨域只走事件总线，同域内部直接调用函数，不绕事件。
 */
import { EVENT_NAMES } from '@/stores/event-bus';

/**
 * 本域计划发布的前端事件（仅登记常量，不触发）：
 * - GROWTH_ACHIEVEMENT_UNLOCKED：成就解锁后发布，供「我的」通知与成就墙消费
 */
export const PUBLISHED_EVENTS = {
  GROWTH_ACHIEVEMENT_UNLOCKED: EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED
} as const;

/** 本域不订阅前端事件。 */
export const SUBSCRIBED_EVENTS = {} as const;

/** 本域向后端 record_user_action() 上报的 trigger_type（P2 阶段补齐调用点）：无。 */

/**
 * 本域消费的后端行为 trigger_type：
 * - practice.submit：E1 答题练习
 * - practice.record.created：E2 练习记录
 * - paper.completed：E3 整卷完成
 * - wrong.reviewed：E4 错题复习
 * - note.created：E5 笔记创建
 * - favorite.added：E5 收藏新增
 * - forum.posted：E6 论坛发帖
 * - news.read：E7 新闻阅读
 * - material.opened：E8 资料学习
 * - shop.purchased：E9 商城消费
 * - checkin.done：E10 每日签到
 */
