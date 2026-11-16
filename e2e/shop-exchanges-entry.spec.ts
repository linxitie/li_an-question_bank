import { expect, test, type Page } from '@playwright/test';

/**
 * M1.5：「我的兑换」入口 —— 用户要求改为弹窗（2026-11-05）
 *
 * 覆盖 PC / 平板 / 手机三端：点「我的兑换」→ 弹窗出现（不跳路由）→ 卡密可见
 * → 关闭（Esc / 右上角 / 点遮罩）→ 弹窗消失。
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

async function expectModal(page: Page) {
  await expect(page.locator('.mex-mask')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.mex-modal')).toBeVisible();
  await expect(page.locator('.mex-modal-head h3')).toHaveText('我的兑换');
  // 弹窗里必须看到卡密与订单
  await expect(page.locator('.mex-item').first()).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.mex-code-value').first()).toBeVisible();
}

test('PC：点「我的兑换」弹出弹窗，不跳路由', async ({ page }) => {
  await login(page);
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');
  const urlBefore = page.url();

  await page.getByRole('button', { name: '我的兑换' }).click();
  await expectModal(page);

  expect(page.url(), '弹窗不应改变路由').toBe(urlBefore);

  // Esc 关闭
  await page.keyboard.press('Escape');
  await expect(page.locator('.mex-mask')).toHaveCount(0);
});

test('PC：点遮罩关闭弹窗', async ({ page }) => {
  await login(page);
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: '我的兑换' }).click();
  await expectModal(page);

  await page.locator('.mex-mask').click({ position: { x: 5, y: 5 } });
  await expect(page.locator('.mex-mask')).toHaveCount(0);

  // 再次打开后点右上角关闭
  await page.getByRole('button', { name: '我的兑换' }).click();
  await expectModal(page);
  await page.locator('.mex-close').click();
  await expect(page.locator('.mex-mask')).toHaveCount(0);
});

test('手机端：我的兑换弹窗', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/mobile/gold-purchase');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '我的兑换' }).click();
  await expectModal(page);

  // 手机端弹窗是底部抽屉形态：宽度接近整屏
  const box = await page.locator('.mex-modal').boundingBox();
  expect(box!.width).toBeGreaterThan(330);
});

test('平板端：我的兑换弹窗', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/#/tablet/gold-purchase');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '我的兑换' }).click();
  await expectModal(page);
});

test('独立页仍可直接访问（保留链接能力）', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/shop/exchanges');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.ex-page')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.mex-item').first()).toBeVisible({ timeout: 20_000 });
});
