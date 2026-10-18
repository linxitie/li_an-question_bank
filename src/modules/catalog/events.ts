/**
 * 题库浏览（catalog）域事件契约（P2-73）。
 *
 * 结论：本域**无成就入边**，不发布也不订阅任何前端事件，
 * 也不向后端 `record_user_action()` 上报任何 trigger_type。
 *
 * 特别说明（C6）：
 *   ⑱ 联考小智 / ⑲ 院校联考机考系统 / ⑳ 小模考 均**未开发**，
 *   入口只保留提示，不发布事件、不新增端点调用；后续需求走独立 spec → plan → implement。
 *
 * 约束：
 *   1. 前端事件常量一律在 @/stores/event-bus 的 EVENT_NAMES 登记，禁止手写事件名字面量；
 *   2. 本文件不建立订阅；
 *   3. 跨域只走事件总线，同域内部直接调用函数，不绕事件。
 */

/** 本域不发布前端事件。 */
export const PUBLISHED_EVENTS = {} as const;

/** 本域不订阅前端事件。 */
export const SUBSCRIBED_EVENTS = {} as const;

/** 本域不产生成就事件（显式声明，便于审计「零事件」结论）。 */
export const ACHIEVEMENT_EVENTS = [] as const;

/** 本域向后端 record_user_action() 上报的 trigger_type：无。 */
export const REPORTED_TRIGGER_TYPES = [] as const;

/** 本域消费的后端行为 trigger_type：无。 */
export const CONSUMED_TRIGGER_TYPES = [] as const;
