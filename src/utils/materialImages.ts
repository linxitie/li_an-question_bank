/**
 * 卡片配图收集（详情页 / 全图查看器共用）
 *
 * 一轮设计里「一卡两图」的落位是：
 *   第 1 张 → `cover_image`（列表与详情封面）
 *   第 2 张 → `content` 里的 `<img>`（详情正文附图）
 * 所以详情页要看的图 = cover_image + content 里所有 img，按出现顺序去重。
 */

export interface CardImageLike {
  cover_image?: string | null;
  content?: string | null;
  /** 后端 `_item_brief` 直接给出的全套配图（封面 + 正文附图），优先使用 */
  image_urls?: string[] | null;
}

const IMG_SRC_RE = /<img[^>]*?src=["']([^"']+)["']/gi;

/** 从卡片记录里取出全部配图 URL（封面优先，其次正文内嵌图，去重保序） */
export function collectCardImages(card?: CardImageLike | null): string[] {
  if (!card) return [];
  // 列表/详情接口已算好 image_urls（列表接口不返回 content，只能靠它）
  const explicit = (card.image_urls || []).map((u) => (u || '').trim()).filter(Boolean);
  if (explicit.length) {
    return Array.from(new Set(explicit));
  }
  const out: string[] = [];
  const cover = (card.cover_image || '').trim();
  if (cover) out.push(cover);
  const html = card.content || '';
  if (html.includes('<img')) {
    IMG_SRC_RE.lastIndex = 0;
    let hit = IMG_SRC_RE.exec(html);
    while (hit) {
      const src = (hit[1] || '').trim();
      if (src && !out.includes(src)) out.push(src);
      hit = IMG_SRC_RE.exec(html);
    }
  }
  return out;
}
