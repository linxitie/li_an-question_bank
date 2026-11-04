import {
  createProvider,
  LocalService,
  createModules,
  NodeEnv,
  autoUpdate,
  ContextMode,
  notify,
  loading,
  createAdapter,
  createServiceRequest,
  IconsPlugin,
  Startup
} from '@vtj/web';
import { useTitle } from '@vueuse/core';
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import router from './router';
import App from './App.vue';
import { vtj, name } from '../package.json';
import './style/index.scss';
import './auth';   // 共享认证模块 → window.__VTJ_AUTH__
import { registerImageRetry } from './image-retry';  // 第9层防线：图片智能重试
// 2026-11-04：徽章展示模块下线 → 「我的」页内徽章入口注入一并移除
import { installMaterialsCreateEntry } from './utils/materialsCreateEntry';  // PC 资料页「创建卡片」入口（DOM 注入）
import { installTabletMaterialsEntry } from './utils/tabletMaterialsEntry';  // 平板首页「备考资料」入口（DOM 注入）

// 注册全局图片重试函数（第9层防线）
registerImageRetry();

const app = createApp(App);
const pinia = createPinia();
const adapter = createAdapter({ loading, notify, Startup, useTitle });
const service = new LocalService(createServiceRequest(notify));
const { provider, onReady } = createProvider({
  nodeEnv: process.env.NODE_ENV as NodeEnv,
  mode: ContextMode.Raw,
  modules: createModules(),
  adapter,
  service,
  router,
  dependencies: {
    Vue: () => import('vue'),
    VueRouter: () => import('vue-router'),
    Pinia: () => import('pinia'),
    VueI18n: () => import('vue-i18n')
  },
  project: {
    id: vtj?.id || name
  },
  enableStaticRoute: true
});

/**
 * 版本自检：前端产物由 vite 注入 __BUILD_SHA__，后端 /health 返回 revision。
 * 为什么需要它：浏览器标签页/后端进程缓存旧代码时，新功能会表现为「功能开发中」或 404，
 * 这属于版本不一致而非功能缺失。显式比对后直接在控制台与页面告警，避免再次误判。
 */
async function checkVersionConsistency(): Promise<void> {
  // 用 typeof 兜底：dev server 未重启或未注入 define 时不能抛 ReferenceError 打断页面
  const frontendSha = typeof __BUILD_SHA__ === 'string' ? __BUILD_SHA__ : 'dev';
  const frontendTime = typeof __BUILD_TIME__ === 'string' ? __BUILD_TIME__ : new Date().toISOString();
  window.__APP_BUILD__ = { sha: frontendSha, time: frontendTime };
  console.info(`[砺安题库] 前端构建 ${frontendSha} @ ${frontendTime}`);
  try {
    const res = await fetch('/health', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    const backend = typeof data?.revision === 'string' ? data.revision : '';
    window.__APP_BUILD__.backend = backend;
    if (!backend || backend === 'unknown' || frontendSha === 'unknown') return;
    if (backend === frontendSha) return;
    window.__VERSION_MISMATCH__ = { frontend: frontendSha, backend };
    console.warn(
      `[砺安题库] 前后端版本不一致：前端 ${frontendSha} / 后端 ${backend}，请刷新页面；仍不一致则重启后端`
    );
    const { ElMessage } = await import('element-plus');
    ElMessage.warning({
      message: '检测到前后端版本不一致，请刷新页面（后端需重启到最新版本）',
      duration: 8000,
    });
  } catch {
    // 后端未启动时静默：属环境问题，不应阻断页面加载
  }
}

onReady(async () => {
  app.use(pinia);
  app.use(router);
  app.use(provider);
  app.use(IconsPlugin);
  app.mount('#app');
  void checkVersionConsistency();
  // 三科资料页是 VTJ 页面 → 运行时在顶栏下方注入「创建卡片 / Excel 批量导入」入口
  installMaterialsCreateEntry();
  // 平板首页也是 VTJ 页面 → 运行时往「快捷功能」里注入「备考资料」入口
  installTabletMaterialsEntry();
});

if (process.env.NODE_ENV === 'production') {
  autoUpdate();
}
