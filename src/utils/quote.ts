/** 金句出处展示：避免“杜牧 · 杜牧·泊秦淮”的重复。 */
export function displayQuoteSource(author?: string, source?: string): string {
  const a = (author || '').trim();
  const s = (source || '').trim();
  if (!a || !s || !s.startsWith(a)) return s;
  return s
    .slice(a.length)
    .replace(/^[\s·•—\-/|:：]+/, '')
    .trim();
}

export function quoteAttribution(author?: string, source?: string): string {
  const a = (author || '').trim();
  const s = displayQuoteSource(author, source);
  if (a && s) return `${a} · ${s}`;
  return a || s || '暂无出处';
}
