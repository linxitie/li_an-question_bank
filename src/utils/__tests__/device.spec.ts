import { describe, expect, it } from 'vitest';

import { detectDeviceFrom } from '../device';

const base = {
  userAgent: '',
  width: 1440,
  touchable: false,
  coarsePointer: false,
  hoverable: true
};

describe('detectDeviceFrom', () => {
  it('标准安卓平板 UA → tablet', () => {
    expect(
      detectDeviceFrom({
        ...base,
        userAgent: 'mozilla/5.0 (linux; android 13; sm-x700) applewebkit/537.36 chrome/120.0.0.0 safari/537.36',
        width: 1180,
        touchable: true,
        coarsePointer: true,
        hoverable: false
      })
    ).toBe('tablet');
  });

  it('桌面模式平板（桌面 UA + 粗指针不可悬停）→ tablet', () => {
    expect(
      detectDeviceFrom({
        ...base,
        userAgent: 'mozilla/5.0 (windows nt 10.0; win64; x64) applewebkit/537.36 chrome/120.0.0.0 safari/537.36',
        width: 1366,
        touchable: true,
        coarsePointer: true,
        hoverable: false
      })
    ).toBe('tablet');
  });

  it('触摸笔记本（可悬停）→ pc', () => {
    expect(
      detectDeviceFrom({
        ...base,
        userAgent: 'mozilla/5.0 (windows nt 10.0; win64; x64) applewebkit/537.36 chrome/120.0.0.0 safari/537.36',
        width: 1440,
        touchable: true,
        coarsePointer: false,
        hoverable: true
      })
    ).toBe('pc');
  });

  it('普通 PC → pc', () => {
    expect(
      detectDeviceFrom({
        ...base,
        userAgent: 'mozilla/5.0 (windows nt 10.0; win64; x64) applewebkit/537.36 chrome/120.0.0.0 safari/537.36'
      })
    ).toBe('pc');
  });

  it('手机竖屏 → mobile', () => {
    expect(
      detectDeviceFrom({
        ...base,
        userAgent: 'mozilla/5.0 (iphone; cpu iphone os 17_0 like mac os x) applewebkit/605.1.15 mobile/15e148',
        width: 390,
        touchable: true,
        coarsePointer: true,
        hoverable: false
      })
    ).toBe('mobile');
  });

  it('手机横屏（android mobi UA + 粗指针）→ mobile', () => {
    expect(
      detectDeviceFrom({
        ...base,
        userAgent: 'mozilla/5.0 (linux; android 13; pixel 7) applewebkit/537.36 chrome/120.0.0.0 mobile safari/537.36',
        width: 780,
        touchable: true,
        coarsePointer: true,
        hoverable: false
      })
    ).toBe('mobile');
  });
});
