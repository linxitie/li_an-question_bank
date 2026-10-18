/**
 * 每日新闻（news）域事件契约（P2-34）。
 *
 * 本域不发布、不订阅前端事件总线事件：
 *   - 阅读上报由后端详情端点完成（`GET /api/news/{id}` 首次阅读发布 E7），
 *     前端不重复上报，避免「前端事件 + 后端事件」双写；
 *   - 与其他域无跨域事件耦合，故 PUBLISHED_EVENTS / SUBSCRIBED_EVENTS 均为空表。
 *
 * `NEWS_TRIGGER_TYPES` 仅登记本域写入的 trigger_type 字符串，
 * 与 backend/app/core/trigger_types.py 的 `TRIGGER_NEWS_READ` 保持一致。
 */

/** 本域不发布前端事件 */
export const PUBLISHED_EVENTS = {} as const;

/** 本域不订阅前端事件 */
export const SUBSCRIBED_EVENTS = {} as const;

/** 本域上报的后端行为 trigger_type（E7） */
export const NEWS_TRIGGER_TYPES = {
  READ: 'news.read'
} as const;

/** 便捷别名：阅读行为 trigger_type */
export const NEWS_READ_TRIGGER = NEWS_TRIGGER_TYPES.READ;
