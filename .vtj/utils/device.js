/**
 * 设备检测工具
 * 用于根据用户设备自动跳转到对应的端
 */

export type DeviceType = 'pc' | 'tablet' | 'mobile';

/**
 * 检测当前设备类型
 */
export function detectDevice(): DeviceType {
  const userAgent = navigator.userAgent.toLowerCase();
  const screenWidth = window.innerWidth;
  
  // 平板设备检测
  if (
    /(ipad|tablet|(android(?!.*mobi))|(windows(?!.*phone)(.*touch)))/.test(userAgent) ||
    (screenWidth >= 768 && screenWidth <= 1024 && 'ontouchstart' in window)
  ) {
    return 'tablet';
  }
  
  // 手机设备检测
  if (
    /iphone|ipod|android.*mobi|windows phone|blackberry|opera mini|iemobile/.test(userAgent) ||
    screenWidth < 768
  ) {
    return 'mobile';
  }
  
  // PC设备
  return 'pc';
}

/**
 * 获取当前设备的路径前缀
 */
export function getDevicePrefix(): string {
  const device = detectDevice();
  switch (device) {
    case 'tablet':
      return '/tablet';
    case 'mobile':
      return '/mobile';
    default:
      return '';
  }
}

/**
 * 检查当前是否为指定设备
 */
export function isDevice(device: DeviceType): boolean {
  return detectDevice() === device;
}

/**
 * 检查当前是否为移动设备（手机或平板）
 */
export function isMobileDevice(): boolean {
  const device = detectDevice();
  return device === 'mobile' || device === 'tablet';
}

/**
 * 根据设备类型获取对应的首页路径
 */
export function getHomePagePath(): string {
  const device = detectDevice();
  switch (device) {
    case 'tablet':
      return '/tablet/home';
    case 'mobile':
      return '/mobile/home';
    default:
      return '/';
  }
}

/**
 * 根据设备类型获取对应的登录页路径
 */
export function getLoginPagePath(): string {
  const device = detectDevice();
  switch (device) {
    case 'tablet':
      return '/tablet/login';
    case 'mobile':
      return '/mobile/login';
    default:
      return '/login';
  }
}
