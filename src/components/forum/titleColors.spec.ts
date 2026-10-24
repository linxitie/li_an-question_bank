import { describe, expect, it } from 'vitest';

import { normalizeTitleColor, titleColorValue } from './titleColors';

describe('title colors', () => {
  it('accepts whitelist tokens', () => {
    expect(normalizeTitleColor('gold')).toBe('gold');
    expect(titleColorValue('red')).toBe('#C41E3A');
  });

  it('falls back to default for css or unknown values', () => {
    expect(normalizeTitleColor('#fff')).toBe('default');
    expect(normalizeTitleColor('rgb(1,2,3)')).toBe('default');
    expect(normalizeTitleColor(undefined)).toBe('default');
  });
});
