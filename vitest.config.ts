import { fileURLToPath, URL } from 'node:url';
import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vitest/config';

/**
 * 前端单测基座（P1-05）。
 *
 * 默认 `environment: 'node'`：本项目当前单测对象是 Pinia store / 纯逻辑模块，
 * 无需 DOM，跑得更轻。需要挂载组件的用例可在文件头加
 * `// @vitest-environment jsdom` 单独切到 jsdom（jsdom 已安装）。
 *
 * `vue()` 插件：让单测能 import `.vue` 单文件组件（组件挂载用例需要）。
 * 它随 @vtj/cli 已经装在 node_modules 里，这里只做注册，未新增依赖。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      $vtj: fileURLToPath(new URL('./.vtj', import.meta.url))
    }
  },
  test: {
    environment: 'node',
    include: ['src/**/*.{test,spec}.{ts,js}'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/.worktrees/**']
  }
});
