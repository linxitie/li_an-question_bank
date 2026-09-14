/**
 * 设备路由守卫
 * 根据用户设备自动跳转到对应的端
 */
import { detectDevice, getDevicePrefix, isMobileDevice } from './device.js';

// 需要排除的路径（不进行自动跳转）
const EXCLUDED_PATHS = [
  '/login',
  '/tablet/login',
  '/mobile/login',
  '/api',
  '/admin',
  '/teacher'
];

// 平板端和手机端的路径前缀
const TABLET_PREFIX = '/tablet';
const MOBILE_PREFIX = '/mobile';

/**
 * 检查路径是否在排除列表中
 */
function isExcludedPath(path: string): boolean {
  return EXCLUDED_PATHS.some(excluded => path.startsWith(excluded));
}

/**
 * 检查路径是否已经是设备特定路径
 */
function isDeviceSpecificPath(path: string): boolean {
  return path.startsWith(TABLET_PREFIX) || path.startsWith(MOBILE_PREFIX);
}

/**
 * 路由守卫 - 自动设备跳转
 */
export function setupDeviceRouterGuard(router: any) {
  router.beforeEach((to: any, from: any, next: any) => {
    const path = to.path;
    const device = detectDevice();
    
    // 排除的路径不进行跳转
    if (isExcludedPath(path)) {
      next();
      return;
    }
    
    // 如果已经是设备特定路径，直接放行
    if (isDeviceSpecificPath(path)) {
      next();
      return;
    }
    
    // 根据设备类型进行跳转
    switch (device) {
      case 'tablet':
        // 平板设备，检查是否已经在平板路径
        if (!path.startsWith(TABLET_PREFIX)) {
          // 自动跳转到平板端对应页面
          const tabletPath = `${TABLET_PREFIX}${path}`;
          next({ path: tabletPath, replace: true });
        } else {
          next();
        }
        break;
        
      case 'mobile':
        // 手机设备，检查是否已经在手机路径
        if (!path.startsWith(MOBILE_PREFIX)) {
          // 自动跳转到手机端对应页面
          const mobilePath = `${MOBILE_PREFIX}${path}`;
          next({ path: mobilePath, replace: true });
        } else {
          next();
        }
        break;
        
      default:
        // PC设备，如果已经在设备特定路径，跳转回PC端
        if (isDeviceSpecificPath(path)) {
          // 提取PC端路径
          let pcPath = path;
          if (path.startsWith(TABLET_PREFIX)) {
            pcPath = path.slice(TABLET_PREFIX.length) || '/';
          } else if (path.startsWith(MOBILE_PREFIX)) {
            pcPath = path.slice(MOBILE_PREFIX.length) || '/';
          }
          next({ path: pcPath, replace: true });
        } else {
          next();
        }
        break;
    }
  });
}

/**
 * 手动跳转到设备对应的页面
 */
export function navigateToDevicePage(router: any, pcPath: string) {
  const device = detectDevice();
  let targetPath = pcPath;
  
  switch (device) {
    case 'tablet':
      targetPath = `${TABLET_PREFIX}${pcPath}`;
      break;
    case 'mobile':
      targetPath = `${MOBILE_PREFIX}${pcPath}`;
      break;
  }
  
  router.push(targetPath);
}

/**
 * 跳转到PC端页面（强制）
 */
export function navigateToPCPage(router: any, path: string) {
  router.push(path);
}

/**
 * 跳转到平板端页面（强制）
 */
export function navigateToTabletPage(router: any, path: string) {
  router.push(`${TABLET_PREFIX}${path}`);
}

/**
 * 跳转到手机端页面（强制）
 */
export function navigateToMobilePage(router: any, path: string) {
  router.push(`${MOBILE_PREFIX}${path}`);
}
