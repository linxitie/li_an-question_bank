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
import './styles/design-system.css';  // 内容型页面统一设计令牌（远端 main，2026-11）
import './styles/admin-tokens.css';   // 管理端设计令牌（A0）：CSS 变量 + .adm-btn/.adm-input 工具类
import './auth';   // 共享认证模块 → window.__VTJ_AUTH__
import { registerImageRetry } from './image-retry';  // 第9层防线：图片智能重试
import { installChunkRecovery } from './utils/chunkRecovery';  // 第10层防线：页面模块加载失败自动恢复
// 2026-11-04：徽章展示模块下线 → 「我的」页内徽章入口注入一并移除
import { installMaterialsCreateEntry } from './utils/materialsCreateEntry';  // PC 资料页「创建卡片」入口（DOM 注入）
import { installTabletMaterialsEntry } from './utils/tabletMaterialsEntry';  // 平板首页「备考资料」入口（DOM 注入）
import { installAdminMaterialTypes } from './utils/adminMaterialTypes';  // 管理页「讲义/试卷」类型与统计卡（DOM 注入，A4 后删除）
import { installAdminImportTypeFix } from './utils/adminImportTypeFix';  // 旧版导入向导：文档默认「作为讲义」（B3，B2 后删除）
import { installA11yFormFields } from './utils/a11yFormFields';  // 表单元素补 id/name（.vtj 模板不能改，走 DOM 注入）

// 注册全局图片重试函数（第9层防线）
registerImageRetry();
// 页面模块加载失败自动重载（第10层防线）
installChunkRecovery();

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
 *
 * 2026-11-03 修正：dev 环境下前端 SHA 是 **vite 启动那一刻**烘焙进去的（vite.config.ts），
 * 后端 SHA 是 **后端启动那一刻**取的（main.py）。两者只要不同时启动就必然不同，
 * 重启后端也追不上前端那份旧值 —— 强告警在 dev 下永远消不掉，属噪音。
 * 因此：dev 只打印 info；只有生产构建才做「同提交可比」的强校验。
 */
async function checkVersionConsistency(): Promise<void> {
  // 用 typeof 兜底：dev server 未重启或未注入 define 时不能抛 ReferenceError 打断页面
  const frontendVersion = typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : '0.0.0';
  const frontendSha = typeof __BUILD_SHA__ === 'string' ? __BUILD_SHA__ : 'dev';
  const frontendTime = typeof __BUILD_TIME__ === 'string' ? __BUILD_TIME__ : new Date().toISOString();
  window.__APP_BUILD__ = { version: frontendVersion, sha: frontendSha, time: frontendTime };
  console.info(`[砺安题库] 前端 v${frontendVersion} 构建 ${frontendSha} @ ${frontendTime}`);

  const isDev = import.meta.env.DEV;
  try {
    const res = await fetch('/health', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    const backend = typeof data?.revision === 'string' ? data.revision : '';
    const backendVersion = typeof data?.version === 'string' ? data.version : '';
    window.__APP_BUILD__.backend = backend;
    window.__APP_BUILD__.backendVersion = backendVersion;

    // 判定依据是版本号（两端读同一个 VERSION 文件），不是 SHA：
    // dev 下前端 SHA 是 vite 启动那一刻、后端 SHA 是后端启动那一刻，天然不同，
    // 拿 SHA 作判据会让「同版本」永远显示为「不一致」——正是用户看到的角标噪声。
    const versionComparable = Boolean(backendVersion) && backendVersion !== '0.0.0';
    if (versionComparable && backendVersion === frontendVersion) {
      console.info(
        `[砺安题库] 前后端版本一致 v${frontendVersion}（前端 ${frontendSha} / 后端 ${backend}）`
      );
      return;
    }

    if (isDev) {
      console.info(
        `[砺安题库] dev 模式：前端 v${frontendVersion}(${frontendSha}) / 后端 v${backendVersion}(${backend})，不一致时请重启后端`
      );
      return;
    }

    window.__VERSION_MISMATCH__ = { frontend: frontendVersion, backend: backendVersion || 'unknown' };
    console.warn(
      `[砺安题库] 前后端版本不一致：前端 v${frontendVersion} / 后端 v${backendVersion || 'unknown'}（${backend}）`
    );
    // dev 环境不弹 toast，只打日志（2026-11-07）：
    // `__BUILD_SHA__` 是 **vite 启动那一刻** 的 `git rev-parse --short HEAD`（见 vite.config 的 define），
    // 而后端每次重启都会更新 `/health.revision` → 只要「先起前端、后提交、再重启后端」，
    // 就必然出现一次"版本不一致"。这是构建时间差，不是代码问题（刷新页面也没用，得重启 vite）。
    // 生产环境仍保留 toast：那里的不一致是真实事故信号（旧 bundle + 新后端）。
    if (process.env.NODE_ENV !== 'production') return;
    const { ElMessage } = await import('element-plus');
    ElMessage.warning({
      message: `检测到前后端版本不一致（前端 v${frontendVersion} / 后端 v${backendVersion || '未知'}），请刷新页面；若仍不一致则重启后端`,
      duration: 8000,
    });
  } catch {
    // 后端未启动时静默：属环境问题，不应阻断页面加载
  }
}

onReady(async () => {
  // 2026-11-08（验收缺陷修复）：Element Plus 的浮层默认从 z-index 2000 起算，
  // 而管理端自绘浮层是 3000（预览抽屉）/3100（对话框）→ 弹窗里的「确认框」会被压在对话框下面。
  // 把 EP 的初始 z-index 提到 5000，让**所有** EP 浮层（确认框/消息/下拉/气泡）都压在自绘浮层之上。
  // 数值关系见 `src/utils/overlay.ts`（OVERLAY_Z / DIALOG_Z / EP_Z），改动要同步。
  const { provideGlobalConfig } = await import('element-plus');
  provideGlobalConfig({ zIndex: 5000 }, app);

  app.use(pinia);
  app.use(router);
  app.use(provider);
  app.use(IconsPlugin);
  app.mount('#app');
  // 自动恢复重载后清掉 URL 上的临时参数，避免脏链接被复制/收藏
  if (window.location.search.includes('__reload=')) {
    const clean = new URL(window.location.href);
    clean.searchParams.delete('__reload');
    window.history.replaceState(window.history.state, '', clean.toString());
  }
  void checkVersionConsistency();
  // 三科资料页是 VTJ 页面 → 运行时在顶栏下方注入「创建卡片 / Excel 批量导入」入口
  installMaterialsCreateEntry();
  // 平板首页也是 VTJ 页面 → 运行时往「快捷功能」里注入「备考资料」入口
  installTabletMaterialsEntry();
  // 管理端资料页：类型下拉补「讲义/试卷」、统计卡补两格（A4 换成手写页后连同本行删除）
  installAdminMaterialTypes();
  // 旧版资料页的导入向导：文档类默认「作为讲义」（B3 修复 P1；B2 重建向导后删除）
  installAdminImportTypeFix();
  // Chrome Issues「表单字段缺 id/name」兜底：VTJ 页模板不能改，运行时补（只补缺失的）
  installA11yFormFields();
});

if (process.env.NODE_ENV === 'production') {
  autoUpdate();
}
