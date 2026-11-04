import { describe, expect, it } from 'vitest';

import { canAccess } from '../access';

describe('canAccess', () => {
  it('allows matching role', () => {
    expect(canAccess({ roles: ['teacher'] }, 'teacher', [])).toBe(true);
  });

  it('rejects mismatched role', () => {
    expect(canAccess({ roles: ['admin'] }, 'student', [])).toBe(false);
  });

  it('lets admin bypass roles', () => {
    expect(canAccess({ roles: ['teacher'] }, 'admin', [])).toBe(true);
  });

  it('rejects missing permission', () => {
    expect(canAccess({ permissions: ['feedback:handle'] }, 'student', [])).toBe(false);
  });

  it('allows granted permission', () => {
    expect(
      canAccess({ permissions: ['feedback:handle'] }, 'student', ['feedback:handle'])
    ).toBe(true);
  });

  it('requires both roles and permissions when both exist', () => {
    const meta = { roles: ['teacher'], permissions: ['forum:moderate'] };
    expect(canAccess(meta, 'teacher', ['forum:moderate'])).toBe(true);
    expect(canAccess(meta, 'teacher', [])).toBe(false);
    expect(canAccess(meta, 'student', ['forum:moderate'])).toBe(false);
  });

  it('allows routes without restrictions', () => {
    expect(canAccess(undefined, null, [])).toBe(true);
  });
});
