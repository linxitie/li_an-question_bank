import type { ForumReactionCode } from './api';

export const REACTION_ORDER: ForumReactionCode[] = [
  'like',
  'love',
  'haha',
  'wow',
  'sad',
  'angry'
];

export const REACTION_META: Record<
  ForumReactionCode,
  { emoji: string; label: string }
> = {
  like: { emoji: '👍', label: '点赞' },
  love: { emoji: '❤️', label: '喜欢' },
  haha: { emoji: '😄', label: '哈哈' },
  wow: { emoji: '😮', label: '惊讶' },
  sad: { emoji: '😢', label: '难过' },
  angry: { emoji: '😠', label: '生气' }
};

export function reactionTotal(
  reactions: Record<string, number> | null | undefined
): number {
  if (!reactions) return 0;
  return REACTION_ORDER.reduce(
    (total, code) => total + Math.max(0, Number(reactions[code]) || 0),
    0
  );
}

export function formatReactionSummary(
  reactions: Record<string, number> | null | undefined
): string {
  if (!reactions) return '';
  return REACTION_ORDER.filter((code) => Number(reactions[code]) > 0)
    .map((code) => `${REACTION_META[code].emoji}${Number(reactions[code])}`)
    .join(' ');
}
