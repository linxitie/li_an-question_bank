import { describe, expect, it } from 'vitest';

import { formatElapsed, ocrProgressText, ocrResultNote } from '../ocrProgress';

describe('formatElapsed', () => {
  it('秒数 → m:ss', () => {
    expect(formatElapsed(0)).toBe('0:00');
    expect(formatElapsed(96)).toBe('1:36');
    expect(formatElapsed(600)).toBe('10:00');
  });
});

describe('ocrProgressText', () => {
  it('有页数时显示 12/24 页 + 已用时间', () => {
    expect(ocrProgressText({ done: 12, total: 24, percent: 50 }, 96))
      .toBe('OCR 12/24 页 · 已用 1:36');
  });

  it('刚入队（total=0）不显示 x/0', () => {
    expect(ocrProgressText({ done: 0, total: 0, percent: 0 })).toBe('OCR 识别中');
    expect(ocrProgressText(null)).toBe('OCR 排队中');
  });

  it('有失败页时补一句', () => {
    const t = ocrProgressText({ done: 22, total: 24, percent: 92, failed_pages: [7, 9] }, 200);
    expect(t).toContain('22/24 页');
    expect(t).toContain('2 页未识别');
  });
});

describe('ocrResultNote', () => {
  it('正常完成：页数 + 字数', () => {
    expect(ocrResultNote({ done: 24, total: 24, percent: 100 }, 31542))
      .toBe('已 OCR 24/24 页 · 正文 31,542 字');
  });

  it('截断与部分失败要明确写出来', () => {
    const s = ocrResultNote({ done: 60, total: 88, percent: 100, truncated: true, failed_pages: [7] }, 1000);
    expect(s).toContain('仅识别前 60 页');
    expect(s).toContain('1 页未识别');
  });

  it('没有进度信息时返回空串', () => {
    expect(ocrResultNote(null)).toBe('');
  });
});
