import { expect, test, type Page } from '@playwright/test';

/**
 * 金币购 M1.5：「我的兑换」页面与弹窗共用的列表组件（MyExchangesPanel）。
 *
 * 页面与弹窗都渲染 `.mex-*` 结构，这里直接验证独立页；
 * 弹窗行为在 shop-exchanges-entry.spec.ts 覆盖。
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

test('我的兑换页：展示订单、卡密与状态', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/shop/exchanges');
  await page.waitForLoadState('networkidle');

  await expect(page.locator('.ex-page')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.ex-head h1')).toHaveText('我的兑换');

  const items = page.locator('.mex-item');
  await expect(items.first()).toBeVisible({ timeout: 20_000 });
  expect(await items.count()).toBeGreaterThanOrEqual(2);

  const code = page.locator('.mex-code-value').first();
  await expect(code).toBeVisible();
  expect((await code.innerText()).trim().length).toBeGreaterThan(3);

  const tags = await page.locator('.mex-tag').allInnerTexts();
  expect(tags.length).toBeGreaterThanOrEqual(2);

  await expect(page.locator('.mex-balance')).toBeVisible();
});

test('我的兑换页：页签筛选可用', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/shop/exchanges');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.mex-item').first()).toBeVisible({ timeout: 20_000 });

  const totalCount = await page.locator('.mex-item').count();

  await page.getByRole('tab', { name: '待处理' }).click();
  expect(await page.locator('.mex-item').count()).toBeLessThanOrEqual(totalCount);
  const pendingTags = await page.locator('.mex-tag').allInnerTexts();
  pendingTags.forEach((t) => expect(t).toContain('待'));

  await page.getByRole('tab', { name: '已交付' }).click();
  const doneTags = await page.locator('.mex-tag').allInnerTexts();
  doneTags.forEach((t) => expect(t).toContain('已交付'));
});

test('我的兑换页：复制卡密可用', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await login(page);
  await page.goto('/#/student/shop/exchanges');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.mex-code-value').first()).toBeVisible({ timeout: 20_000 });

  const codeText = (await page.locator('.mex-code-value').first().innerText()).trim();
  await page.locator('.mex-code .mex-btn').first().click();

  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toBe(codeText);
  await expect(page.locator('.mex-code .mex-btn').first()).toHaveText('已复制');
});
