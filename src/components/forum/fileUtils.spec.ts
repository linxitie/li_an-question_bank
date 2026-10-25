import { describe, expect, it } from 'vitest';

import {
  fileIcon,
  formatFileSize,
  getFileExt,
  isDocFile,
  isImageFile,
  splitAttachments
} from './fileUtils';

describe('forum file utils', () => {
  it('recognises supported document types', () => {
    expect(isDocFile('a.docx')).toBe(true);
    expect(isDocFile('a.PDF')).toBe(true);
    expect(isDocFile('a.rar')).toBe(true);
    expect(isDocFile('a.7z')).toBe(true);
    expect(isDocFile('a.exe')).toBe(false);
  });

  it('recognises images', () => {
    expect(isImageFile('a.PNG')).toBe(true);
    expect(isImageFile('a.docx')).toBe(false);
  });

  it('formats size and icon', () => {
    expect(formatFileSize(512)).toBe('512B');
    expect(formatFileSize(2048)).toBe('2.0KB');
    expect(fileIcon('a.pdf')).toBe('📕');
    expect(getFileExt('a.docx')).toBe('docx');
  });

  it('splits images and documents', () => {
    const result = splitAttachments([
      { name: 'a.png', url: '/uploads/a.png' },
      { name: 'b.pdf', url: '/uploads/b.pdf' }
    ]);
    expect(result.images).toEqual(['/uploads/a.png']);
    expect(result.files).toHaveLength(1);
  });
});
