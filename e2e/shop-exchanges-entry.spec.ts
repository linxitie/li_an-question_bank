import { expect, test, type Page } from '@playwright/test';

/**
 * M1.5：「我的兑换」入口（用户授权改模板，2026-11-05）
 *
 * 覆盖 PC / 平板 / 手机三端金币购页：入口可见 → 点击 → 跳到 /student/shop/exchanges 并渲染。
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

test('PC 金币购页 → 我的兑换', async ({ page }) => {
  await login(page);
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');

  const btn = page.locator('.gp-my-exchanges');
  await expect(btn).toBeVisible({ timeout: 20_000 });
  await expect(btn).toHaveText('我的兑换');

  await btn.click();
  await expect
    .poll(() => page.url(), { timeout: 15_000 })
    .toContain('/student/shop/exchanges');
  await expect(page.locator('.ex-page')).toBeVisible({ timeout: 20_000 });
});

test('手机端金币购页 → 我的兑换', async ({ page }) => {
  // 手机端登录页的输入框不同，先用 PC 视口登录，再切到手机视口访问移动页
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/mobile/gold-purchase');
  await page.waitForLoadState('networkidle');

  const btn = page.locator('.gp-my-exchanges');
  await expect(btn).toBeVisible({ timeout: 20_000 });

  await btn.click();
  await expect
    .poll(() => page.url(), { timeout: 15_000 })
    .toContain('/student/shop/exchanges');
  await expect(page.locator('.ex-page')).toBeVisible({ timeout: 20_000 });
});

test('平板端金币购页 → 我的兑换', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/#/tablet/gold-purchase');
  await page.waitForLoadState('networkidle');

  const btn = page.locator('.gp-my-exchanges');
  await expect(btn).toBeVisible({ timeout: 20_000 });

  await btn.click();
  await expect
    .poll(() => page.url(), { timeout: 15_000 })
    .toContain('/student/shop/exchanges');
  await expect(page.locator('.ex-page')).toBeVisible({ timeout: 20_000 });
});
