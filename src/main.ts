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

onReady(async () => {
  app.use(pinia);
  app.use(router);
  app.use(provider);
  app.use(IconsPlugin);
  app.mount('#app');
});

if (process.env.NODE_ENV === 'production') {
  autoUpdate();
}
