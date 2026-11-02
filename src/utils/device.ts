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
  // 触摸能力：navigator.maxTouchPoints 比 'ontouchstart' in window 更可靠
  // （iPadOS 桌面模式 UA 下 maxTouchPoints 仍 > 0）
  const touchable =
    'ontouchstart' in window ||
    (typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 0);

  // 平板设备检测（UA 优先，宽度+触摸为辅）
  if (
    /(ipad|tablet|(android(?!.*mobi))|(windows(?!.*phone)(.*touch)))/.test(userAgent) ||
    (screenWidth >= 768 && screenWidth <= 1024 && touchable)
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

/**
 * PC 路径 → 移动端路径 显式映射表
 *
 * 为什么用映射表而不是「前缀拼接」？
 * 前缀拼接会产生 `/mobile/` 这类不存在的路由，导致 `router.getRoutes()`
 * 匹配失败、跳转静默失效（这正是此前"手机端不生效"的根因之一）。
 * 显式映射明确声明「哪些 PC 路径存在对应的移动端页面」，
 * 未列出的路径（如 /admin、/teacher）在移动端不强跳，回落到兜底页，避免误伤。
 */
const DEVICE_ROUTE_MAP: Record<'mobile' | 'tablet', Record<string, string>> = {
  mobile: {
    '/': '/mobile/home',
    '/home': '/mobile/home',
    '/login': '/mobile/login',
    '/question-bank': '/mobile/question-bank',
    '/forum': '/mobile/forum',
    '/practice': '/mobile/practice',
    '/profile': '/mobile/profile',
  },
  tablet: {
    '/': '/tablet/home',
    '/home': '/tablet/home',
    '/login': '/tablet/login',
    '/question-bank': '/tablet/question-bank',
    '/forum': '/tablet/forum',
    '/practice': '/tablet/practice',
    '/profile': '/tablet/profile',
  },
};

/**
 * 将 PC 路径解析为指定设备的对应路径
 * @param rawPath 原始路径（如 '/'、'/login'）
 * @param device  目标设备类型
 * @returns 对应的设备路径；若该路径无移动端对应页，返回 null
 */
export function resolveDevicePath(rawPath: string, device: DeviceType): string | null {
  if (device !== 'mobile' && device !== 'tablet') return null;
  const map = DEVICE_ROUTE_MAP[device];
  return map[rawPath] ?? null;
}
