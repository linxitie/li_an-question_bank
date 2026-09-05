/**
 * 图片智能重试（第9层防线）
 *
 * 设计理念：后端 1-8 层已确保 98% 图片路径有效，前端再加一道智能重试防线——
 * 对每张图片维护多个候选 URL，onerror 时自动切换，不显示 broken image 图标。
 *
 * 剩余 <2% 极端情况（源文件已删且无备份）：优雅降级（visibility:hidden 保留占位空间）
 * + sendBeacon 上报待修复，不显示错误占位符。
 *
 * 触发方式：img 标签的 onerror="window.__retryImg(this)"
 *   - 由 exercise.vue 的 renderContent 注入
 *   - 也兼容后端返回的 <img src="..."> 标签（通过 mutation observer 增强）
 */

interface BrokenImageReport {
  src: string;
  marker: string | null;
  url: string;
  timestamp: number;
}

const REPORT_ENDPOINT = '/api/images/report-broken';
const MAX_RETRIES = 3;

/**
 * 根据 marker 构建候选 URL 列表
 * marker 格式可能是：
 *   - uuid_qn_seq（如 abc12345_1_0）
 *   - qn_seq（如 1_0）
 */
function buildFallbacks(marker: string, originalSrc: string): string[] {
  const fallbacks: string[] = [];

  if (marker) {
    // 候选1：扁平路径（uuid_qn_seq 格式）
    fallbacks.push('/static/questions/' + marker + '.png');

    // 候选2：简化 marker（uuid_x_y → x_y）
    const parts = marker.split('_');
    if (parts.length === 3) {
      const simpleMarker = parts[1] + '_' + parts[2];
      fallbacks.push('/static/questions/' + simpleMarker + '.png');
    }
  }

  // 候选3：原始 src（带缓存破坏参数）
  if (originalSrc && fallbacks.indexOf(originalSrc) < 0) {
    const sep = originalSrc.indexOf('?') >= 0 ? '&' : '?';
    fallbacks.push(originalSrc + sep + '_retry=' + Date.now());
  }

  return fallbacks;
}

/**
 * 上报断裂图片到后端健康检查队列
 */
function reportBrokenImage(src: string, marker: string | null): void {
  try {
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const report: BrokenImageReport = {
        src: src,
        marker: marker,
        url: location.href,
        timestamp: Date.now()
      };
      navigator.sendBeacon(
        REPORT_ENDPOINT,
        new Blob([JSON.stringify(report)], { type: 'application/json' })
      );
    }
  } catch (e) {
    // 静默失败，不影响用户体验
  }
}

/**
 * 图片加载失败时的重试函数
 * 注册到 window.__retryImg，供 img onerror 内联调用
 */
function retryImg(img: HTMLImageElement): void {
  const marker = img.getAttribute('data-marker');
  const retryCount = parseInt(img.getAttribute('data-retry') || '0', 10);
  const originalSrc = img.getAttribute('src') || '';

  // 构建/读取 fallback 列表
  let fallbacks: string[] = [];
  const fallbacksAttr = img.getAttribute('data-fallbacks');
  if (fallbacksAttr) {
    try {
      fallbacks = JSON.parse(fallbacksAttr);
    } catch (e) {
      fallbacks = buildFallbacks(marker || '', originalSrc);
    }
  } else {
    fallbacks = buildFallbacks(marker || '', originalSrc);
    try {
      img.setAttribute('data-fallbacks', JSON.stringify(fallbacks));
    } catch (e) {
      // ignore
    }
  }

  // 尝试下一个候选 URL
  if (retryCount < fallbacks.length - 1 && retryCount < MAX_RETRIES) {
    const nextRetry = retryCount + 1;
    const nextSrc = fallbacks[nextRetry];
    img.setAttribute('data-retry', String(nextRetry));
    img.src = nextSrc;
    return;
  }

  // 所有候选都失败 → 优雅降级（保留占位空间，不显示 broken 图标）
  img.style.visibility = 'hidden';
  img.style.minHeight = '60px';
  img.style.minWidth = '100%';
  img.setAttribute('data-broken', '1');
  img.removeAttribute('onerror'); // 避免无限循环

  // 上报待修复
  reportBrokenImage(originalSrc, marker);
}

/**
 * 为后端返回的 <img src="..."> 标签注入 onerror 重试能力
 * 通过 MutationObserver 监听 DOM 变化，自动增强未带 onerror 的图片
 */
function enhanceExistingImages(root: Node): void {
  try {
    const imgs = (root as Element).querySelectorAll
      ? (root as Element).querySelectorAll('img.q-img:not([data-enhanced])')
      : [];
    imgs.forEach((img: Element) => {
      const htmlImg = img as HTMLImageElement;
      htmlImg.setAttribute('data-enhanced', '1');
      if (!htmlImg.getAttribute('onerror')) {
        htmlImg.setAttribute(
          'onerror',
          'window.__retryImg && window.__retryImg(this)'
        );
      }
      // 从 src 中提取 marker（如果是 /static/questions/{marker}.png 格式）
      if (!htmlImg.getAttribute('data-marker')) {
        const src = htmlImg.getAttribute('src') || '';
        const m = src.match(/\/static\/questions\/([^/]+)\.png/);
        if (m) {
          htmlImg.setAttribute('data-marker', m[1]);
        }
      }
    });
  } catch (e) {
    // 静默失败
  }
}

/**
 * 注册全局图片重试函数
 * 在 main.ts 中调用一次即可
 */
export function registerImageRetry(): void {
  if (typeof window === 'undefined') return;

  // 避免重复注册
  if ((window as any).__retryImg) return;

  (window as any).__retryImg = retryImg;

  // 通过 MutationObserver 自动增强动态插入的图片
  if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              enhanceExistingImages(node);
            }
          });
        }
      }
    });

    // 等待 DOM 就绪后开始监听
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        enhanceExistingImages(document.body);
        observer.observe(document.body, { childList: true, subtree: true });
      });
    } else {
      enhanceExistingImages(document.body);
      observer.observe(document.body, { childList: true, subtree: true });
    }
  }
}
