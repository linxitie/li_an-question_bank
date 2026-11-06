import { expect, test, type Page } from '@playwright/test';

/**
 * M3.5：知识图谱（弹窗形态）
 *
 * 覆盖：金币购页点「知识图谱」→ 弹窗出现且不跳路由 → 图谱/习惯/候选渲染
 * → Esc / × 关闭；独立页仍可直接访问。
 */

const STUDENT = { user: '202516001', pass: 'test123456' };

async function login(page: Page) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(STUDENT.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(STUDENT.pass);
  await pwd.press('Enter');
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
}

async function openKgModal(page: Page) {
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');
  await page.locator('.gp-kg-entry').click();
  await expect(page.locator('.kgm-mask')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.kgm-modal')).toBeVisible();
  await expect(page.locator('.kgm-head h3')).toHaveText('我的知识图谱');
}

test('金币购页：知识图谱以弹窗打开，不跳路由', async ({ page }) => {
  await login(page);
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');
  const before = page.url();

  await page.locator('.gp-kg-entry').click();
  await expect(page.locator('.kgm-mask')).toBeVisible({ timeout: 20_000 });

  expect(page.url(), '弹窗不应改变路由').toBe(before);

  // 弹窗内必须渲染图谱区与习惯卡（有数据时是 SVG，无数据时是空态）
  await expect(page.locator('.kgm-body')).toBeVisible();
  const habitCard = page.locator('.kgm-body .kgp-card').filter({ hasText: '做题习惯' });
  await expect(habitCard).toBeVisible();
  await expect(habitCard).toContainText('采样温度');

  // Esc 关闭
  await page.keyboard.press('Escape');
  await expect(page.locator('.kgm-mask')).toHaveCount(0);
});

test('知识图谱弹窗：× 关闭与再次打开', async ({ page }) => {
  await login(page);
  await openKgModal(page);
  await page.locator('.kgm-close').click();
  await expect(page.locator('.kgm-mask')).toHaveCount(0);

  await page.locator('.gp-kg-entry').click();
  await expect(page.locator('.kgm-mask')).toBeVisible();
});

test('知识图谱弹窗：生成个性化任务', async ({ page }) => {
  await login(page);
  await openKgModal(page);

  const btn = page.getByRole('button', { name: '生成本周个性化任务' });
  await expect(btn).toBeEnabled();
  await btn.click();
  await expect(page.locator('.el-message')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('.el-message')).toContainText('已生成');
});

test('独立页仍可直接访问（保留链接能力）', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/knowledge/graph');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.kg-page')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.kgp-card').filter({ hasText: '做题习惯' })).toBeVisible();
});

test('手机端：知识图谱弹窗为底部抽屉', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/mobile/gold-purchase');
  await page.waitForLoadState('networkidle');
  await page.locator('.gp-kg-entry').click();
  await expect(page.locator('.kgm-mask')).toBeVisible({ timeout: 20_000 });

  const box = await page.locator('.kgm-modal').boundingBox();
  expect(box!.width).toBeGreaterThan(330);
});
