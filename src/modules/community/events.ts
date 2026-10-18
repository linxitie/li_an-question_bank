/**
 * 论坛社区（community）域事件契约。
 *
 * 本域不发布、也不订阅前端事件总线事件：论坛写操作成功后由页面/本域 store
 * 直接刷新，没有跨域消费方（事件丢失不影响正确性）。
 * 后端行为 trigger_type `forum.posted`（E6）由服务端按 post id 幂等上报，
 * 前端只登记契约，不重复上报。
 */
export const PUBLISHED_EVENTS = {} as const;

export const SUBSCRIBED_EVENTS = {} as const;

export const COMMUNITY_TRIGGER_TYPES = {
  FORUM_POSTED: 'forum.posted'
} as const;
