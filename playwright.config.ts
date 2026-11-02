import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 配置（管理员端 UI 回归）。
 *
 * 前提：9527（vite dev server）与 8000（uvicorn）已在运行，本配置不负责启停。
 * 测试放在 e2e/ 而非 src/：tsconfig include 只含 "src"，vitest include 只含 "src/**"，两边都不会被误收。
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  outputDir: './e2e/.artifacts',
  use: {
    baseURL: 'http://127.0.0.1:9527',
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'off',
    actionTimeout: 20_000
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }
  ]
});
