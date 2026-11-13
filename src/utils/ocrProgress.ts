/**
 * OCR 进度的展示口径（P2，2026-11-12）。
 *
 * 为什么单独抽：后端只回 `{done,total,percent,phase,truncated,failed_pages}` 这种裸数据，
 * "该显示什么字"是纯展示逻辑，容易写出 `12/0 页` 这种边界，必须可单测。
 */

export interface OcrProgress {
  done: number;
  total: number;
  percent: number;
  phase?: string;
  truncated?: boolean;
  failed_pages?: number[];
}

/** 秒 → `m:ss`（超过 1 小时退化成分） */
export function formatElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(s / 60);
  const rest = s % 60;
  return `${m}:${String(rest).padStart(2, '0')}`;
}

/**
 * 解析中那一行的进度文案：`OCR 12/24 页 · 已用 1:36`；
 * 还没拿到页数（刚入队）返回「OCR 排队中」；`total=0` 不显示 `x/0`。
 */
export function ocrProgressText(p?: OcrProgress | null, elapsedSeconds?: number): string {
  if (!p) return 'OCR 排队中';
  const done = Number.isFinite(p.done) ? p.done : 0;
  const total = Number.isFinite(p.total) ? p.total : 0;
  const parts: string[] = [];
  parts.push(total > 0 ? `OCR ${done}/${total} 页` : 'OCR 识别中');
  if (typeof elapsedSeconds === 'number' && elapsedSeconds >= 0) {
    parts.push(`已用 ${formatElapsed(elapsedSeconds)}`);
  }
  if (p.failed_pages && p.failed_pages.length) {
    parts.push(`${p.failed_pages.length} 页未识别`);
  }
  return parts.join(' · ');
}

/**
 * 成功之后的补充说明：截断/部分失败要告诉用户，别让人以为整篇都识别了。
 * 全部正常时返回空串（不占版面）。
 */
export function ocrResultNote(p?: OcrProgress | null, chars?: number): string {
  if (!p) return '';
  const notes: string[] = [];
  if (p.total > 0) notes.push(`已 OCR ${p.done}/${p.total} 页`);
  if (typeof chars === 'number' && chars > 0) notes.push(`正文 ${chars.toLocaleString('zh-CN')} 字`);
  if (p.truncated) notes.push('仅识别前 60 页');
  if (p.failed_pages && p.failed_pages.length) notes.push(`${p.failed_pages.length} 页未识别`);
  return notes.join(' · ');
}
