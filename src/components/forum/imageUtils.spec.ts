import { describe, expect, it } from 'vitest';

import { isImageUrl, previewImages, shouldCollapse } from './imageUtils';

describe('forum image rules', () => {
  it('collapses comment images at 3', () => {
    expect(shouldCollapse(0)).toBe(false);
    expect(shouldCollapse(2)).toBe(false);
    expect(shouldCollapse(3)).toBe(true);
    expect(shouldCollapse(8)).toBe(true);
  });

  it('keeps first 9 images and reports the remainder', () => {
    const images = Array.from({ length: 12 }, (_, index) => `${index}.png`);
    const result = previewImages(images);
    expect(result.visible).toHaveLength(9);
    expect(result.more).toBe(3);
  });

  it('does not report remainder when under limit', () => {
    expect(previewImages(['a.png'])).toEqual({ visible: ['a.png'], more: 0 });
  });

  it('detects image urls', () => {
    expect(isImageUrl('/uploads/a.JPG')).toBe(true);
    expect(isImageUrl('/uploads/a.docx')).toBe(false);
    expect(isImageUrl('')).toBe(false);
  });
});
