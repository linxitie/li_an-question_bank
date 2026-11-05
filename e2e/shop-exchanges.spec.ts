import { expect, test, type Page } from '@playwright/test';

/**
 * 金币购 M1.5：「我的兑换」独立页面（/student/shop/exchanges）。
 *
 * 覆盖：页面可打开、展示真实兑换记录、卡密可见可复制、待处理状态正确、
 * 页签筛选生效、余额展示。
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

  // 有真实兑换记录（开发库至少 2 条）
  const items = page.locator('.ex-item');
  await expect(items.first()).toBeVisible({ timeout: 20_000 });
  expect(await items.count()).toBeGreaterThanOrEqual(2);

  // 卡密可见（视频会员日卡那笔）
  const code = page.locator('.ex-code-value').first();
  await expect(code).toBeVisible();
  const codeText = (await code.innerText()).trim();
  expect(codeText.length).toBeGreaterThan(3);

  // 状态标签至少有两种：已交付 / 待发货
  const tags = await page.locator('.ex-tag').allInnerTexts();
  expect(tags.length).toBeGreaterThanOrEqual(2);

  // 余额展示
  await expect(page.locator('.ex-balance-num')).toBeVisible();
});

test('我的兑换页：页签筛选可用', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/shop/exchanges');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.ex-item').first()).toBeVisible({ timeout: 20_000 });

  const totalCount = await page.locator('.ex-item').count();

  await page.getByRole('tab', { name: '待处理' }).click();
  const pendingCount = await page.locator('.ex-item').count();
  expect(pendingCount).toBeLessThanOrEqual(totalCount);

  // 待处理里的每条都必须是待处理状态
  const pendingTags = await page.locator('.ex-tag').allInnerTexts();
  pendingTags.forEach((t) => expect(t).toContain('待'));

  await page.getByRole('tab', { name: '已交付' }).click();
  const doneTags = await page.locator('.ex-tag').allInnerTexts();
  doneTags.forEach((t) => expect(t).toContain('已交付'));
});

test('我的兑换页：复制卡密可用', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await login(page);
  await page.goto('/#/student/shop/exchanges');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.ex-code-value').first()).toBeVisible({ timeout: 20_000 });

  const codeText = (await page.locator('.ex-code-value').first().innerText()).trim();
  await page.locator('.ex-code .ex-btn').first().click();

  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toBe(codeText);
  await expect(page.locator('.ex-code .ex-btn').first()).toHaveText('已复制');
});
