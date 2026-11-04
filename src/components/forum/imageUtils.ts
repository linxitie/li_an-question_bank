/**
 * 论坛图片通用规则。
 *
 * 业务上发帖/评论都不限制张数；这里只负责“怎么展示”和“上传前校验”，
 * 真正的安全阈值（大小/频率/体积）由后端兜底。
 */
import { apiClient } from '@/services/api/client';

export interface ForumImageAttachment {
  name: string;
  url: string;
  size?: number;
  type?: string;
}

export const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
export const COMMENT_COLLAPSE_AT = 3;
export const POST_PREVIEW_MAX = 9;

/** 单条评论图片达到阈值即折叠（含阈值本身）。 */
export function shouldCollapse(count: number, threshold = COMMENT_COLLAPSE_AT): boolean {
  return count >= threshold;
}

/** 发帖图片超过预览上限时，只显示前 N 张并给出剩余数量。 */
export function previewImages(
  images: string[],
  max = POST_PREVIEW_MAX
): { visible: string[]; more: number } {
  const safe = Array.isArray(images) ? images : [];
  return {
    visible: safe.slice(0, max),
    more: Math.max(0, safe.length - max)
  };
}

export function isImageUrl(url: string): boolean {
  return /\.(png|jpe?g|gif|webp)(\?.*)?$/i.test(url || '');
}

export async function uploadForumImage(file: File): Promise<ForumImageAttachment> {
  if (!file) throw new Error('未选择图片');
  if (!isImageUrl(file.name)) throw new Error('仅支持 jpg/png/gif/webp');
  if (file.size > MAX_IMAGE_SIZE) throw new Error('图片不能超过 5MB');

  const form = new FormData();
  form.append('file', file);
  const response = await apiClient.request({
    url: '/api/media/image',
    method: 'POST',
    data: form,
    baseURL: ''
  });
  const data = response.data as { url: string; name?: string; size?: number; type?: string };
  return {
    name: data.name || file.name,
    url: data.url,
    size: data.size ?? file.size,
    type: data.type || file.type
  };
}
