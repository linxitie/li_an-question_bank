/**
 * 联考小智（ai-assistant）域事件契约 —— 模块⑦「联考小智」实现
 *
 * 约束：
 *   1. 跨域只走事件总线，同域内部直接调用函数，不绕事件；
 *   2. 发布方在触发点调用 emit，订阅方在域入口 onEvent 并保留取消订阅函数。
 */

/** 本域发布事件：会话列表刷新后对外广播（供成就/金币等跨域消费） */
export const PUBLISHED_EVENTS = {
  /** 会话列表已刷新，载荷：{ total: number } */
  SESSIONS_UPDATED: 'ai-assistant:sessions-updated'
} as const;

/** 本域订阅事件：暂无 */
export const SUBSCRIBED_EVENTS = {} as const;

/** 本域向后端 record_user_action() 上报的 trigger_type：联考小智提问 */
export const TRIGGER_AI_ASSISTANT_ASK = 'ai.assistant.ask';

/** 本域消费的后端行为 trigger_type：无。 */
