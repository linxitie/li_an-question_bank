/** 标题颜色只允许固定 token，禁止任意 CSS，避免样式注入。 */
export const TITLE_COLORS = [
  { key: 'default', name: '默认', value: '#1A365D' },
  { key: 'red', name: '红', value: '#C41E3A' },
  { key: 'gold', name: '金', value: '#B8860B' },
  { key: 'blue', name: '蓝', value: '#2563EB' },
  { key: 'green', name: '绿', value: '#15803D' },
  { key: 'purple', name: '紫', value: '#7C3AED' }
] as const;

export type TitleColorKey = (typeof TITLE_COLORS)[number]['key'];

export function normalizeTitleColor(token: string | null | undefined): TitleColorKey {
  const matched = TITLE_COLORS.find((item) => item.key === token);
  return matched ? matched.key : 'default';
}

export function titleColorValue(token: string | null | undefined): string {
  const key = normalizeTitleColor(token);
  return TITLE_COLORS.find((item) => item.key === key)?.value || TITLE_COLORS[0].value;
}
