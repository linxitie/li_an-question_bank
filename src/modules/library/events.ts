/**
 * 备考资料（library）域事件契约（P2-38）。
 *
 * 本域不发布、不订阅前端事件总线事件：
 *   - 打开行为由后端详情端点完成（`GET /api/materials/{id}` 首次打开发布 E8），
 *     前端不重复上报，避免「前端事件 + 后端事件」双写；
 *   - 与其他域无跨域事件耦合，故 PUBLISHED_EVENTS / SUBSCRIBED_EVENTS 均为空表。
 *
 * `LIBRARY_TRIGGER_TYPES` 仅登记本域写入的 trigger_type 字符串，
 * 与 backend/app/core/trigger_types.py 的 `TRIGGER_MATERIAL_OPENED` 保持一致。
 */

/** 本域不发布前端事件 */
export const PUBLISHED_EVENTS = {} as const;

/** 本域不订阅前端事件 */
export const SUBSCRIBED_EVENTS = {} as const;

/** 本域上报的后端行为 trigger_type（E8） */
export const LIBRARY_TRIGGER_TYPES = {
  MATERIAL_OPENED: 'material.opened'
} as const;

/** 便捷别名：打开资料行为 trigger_type */
export const LIBRARY_MATERIAL_OPENED_TRIGGER =
  LIBRARY_TRIGGER_TYPES.MATERIAL_OPENED;
