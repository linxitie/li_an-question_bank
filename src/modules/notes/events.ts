/**
 * 笔记与收藏（notes）域事件契约。
 *
 * 本域不发布、也不订阅前端事件总线事件：笔记/收藏没有跨域消费方，
 * 写操作成功后由页面直接刷新本域 store 即可（事件丢失不影响正确性）。
 * 后端行为 trigger_type 仅由服务端在创建成功后上报一次（见 events 注释与 P2-24）。
 */
export const PUBLISHED_EVENTS = {} as const;

export const SUBSCRIBED_EVENTS = {} as const;

export const NOTES_TRIGGER_TYPES = {
  NOTE_CREATED: 'note.created',
  FAVORITE_ADDED: 'favorite.added'
} as const;
