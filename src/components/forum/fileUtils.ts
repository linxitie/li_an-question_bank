import { apiClient } from '@/services/api/client';
import { isImageUrl, type ForumImageAttachment } from './imageUtils';

export const DOC_EXTENSIONS = [
  'doc', 'docx', 'pdf', 'xls', 'xlsx', 'ppt', 'pptx',
  'txt', 'csv', 'zip', 'rar', '7z'
] as const;

export const MAX_DOC_SIZE = 20 * 1024 * 1024;

export function getFileExt(name: string): string {
  return (name.split('.').pop() || '').toLowerCase();
}

export function isDocFile(name: string): boolean {
  return (DOC_EXTENSIONS as readonly string[]).includes(getFileExt(name));
}

export function isImageFile(name: string): boolean {
  return ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(getFileExt(name));
}

export function formatFileSize(size?: number): string {
  if (!size || size < 0) return '';
  if (size < 1024) return `${size}B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
  return `${(size / 1024 / 1024).toFixed(1)}MB`;
}

export function fileIcon(name: string): string {
  const ext = getFileExt(name);
  if (['pdf'].includes(ext)) return '📕';
  if (['doc', 'docx'].includes(ext)) return '📘';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return '📗';
  if (['ppt', 'pptx'].includes(ext)) return '📙';
  if (['zip', 'rar', '7z'].includes(ext)) return '🗜️';
  return '📄';
}

export async function uploadForumFile(file: File): Promise<ForumImageAttachment> {
  if (!isDocFile(file.name)) throw new Error(`不支持的文件格式：${getFileExt(file.name)}`);
  if (file.size > MAX_DOC_SIZE) throw new Error(`${file.name} 超过 20MB`);

  const form = new FormData();
  form.append('file', file);
  const response = await apiClient.request({
    url: '/api/forum/upload',
    method: 'POST',
    data: form,
    baseURL: ''
  });
  const data = response.data as { url: string; name?: string; size?: number; type?: string };
  return {
    name: data.name || file.name,
    url: data.url,
    size: data.size ?? file.size,
    type: data.type || getFileExt(file.name)
  };
}

export function splitAttachments(attachments: ForumImageAttachment[] = []) {
  const images: string[] = [];
  const files: ForumImageAttachment[] = [];
  for (const att of attachments) {
    if (isImageUrl(att.url)) images.push(att.url);
    else files.push(att);
  }
  return { images, files };
}
