/**
 * 论坛分类的唯一事实来源。
 *
 * 三端（PC / 平板 / 手机）都从这里取分类，避免再次出现
 * 「手机有、平板没有、PC 完全没有」和 key 与后端枚举对不上的问题。
 * 后端合法值见 `backend/app/models/models.py` 的 `forum_post.share_type`。
 */
import type { ForumShareType } from './api';

export type ForumCategoryKey = 'all' | ForumShareType;

export interface ForumCategoryTab {
  key: ForumCategoryKey;
  name: string;
}

export const FORUM_CATEGORY_TABS: readonly ForumCategoryTab[] = [
  { key: 'all', name: '全部' },
  { key: 'DISCUSSION', name: '学习讨论' },
  { key: 'EXPERIENCE', name: '经验分享' },
  { key: 'QUESTION', name: '答疑解惑' },
  { key: 'RESOURCE', name: '资料分享' },
  { key: 'FEELING', name: '心情打卡' }
];

/**
 * 分类 chip 的 key 转成接口参数。
 * `all` 以及任何非法值都返回空串，表示不筛选。
 */
export function toShareTypeParam(
  key: ForumCategoryKey | string | null | undefined
): ForumShareType | '' {
  if (!key || key === 'all') return '';
  const matched = FORUM_CATEGORY_TABS.find((tab) => tab.key === key);
  return matched && matched.key !== 'all' ? (matched.key as ForumShareType) : '';
}
