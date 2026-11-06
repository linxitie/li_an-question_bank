import { expect, test, type Page } from '@playwright/test';

/**
 * 2026-11-05 需求验收：
 * 1. 学生 PC 端导航栏有「商城」
 * 2. 手机端底部导航中间有「商城」
 * 3. 管理员端商城页能上架/下架商品
 */

const STUDENT = { user: '202516001', pass: 'test123456' };
const ADMIN = { user: 'cbrycc', pass: 'cbrycc' };

async function login(page: Page, account: { user: string; pass: string }) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(account.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(account.pass);
  await pwd.press('Enter');
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
}

test('PC 导航栏：商城入口可跳转', async ({ page }) => {
  await login(page, STUDENT);
  await page.goto('/#/page/home_page');
  await page.waitForLoadState('networkidle');

  const nav = page.locator('.navbar, nav').first();
  const shop = page.getByRole('button', { name: '商城' }).or(page.getByText('商城', { exact: true })).first();
  await expect(shop).toBeVisible({ timeout: 20_000 });

  await shop.click();
  await expect.poll(() => page.url(), { timeout: 15_000 }).toContain('gold_purchase');
  await expect(page.locator('.gold-purchase-page')).toBeVisible({ timeout: 20_000 });
  void nav;
});

test('手机端底部导航：商城在中间', async ({ page }) => {
  await login(page, STUDENT);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/mobile/home');
  await page.waitForLoadState('networkidle');

  const bar = page.locator('.mtb-bar');
  await expect(bar).toBeVisible({ timeout: 20_000 });

  const labels = await bar.locator('.mtb-label').allInnerTexts();
  expect(labels.length).toBe(5);
  expect(labels[2], '商城应位于底部栏正中间').toBe('商城');

  await bar.locator('.mtb-item').nth(2).click();
  await expect.poll(() => page.url(), { timeout: 15_000 }).toContain('/mobile/gold-purchase');
  await expect(page.locator('.mobile-gp-page')).toBeVisible({ timeout: 20_000 });
});

test('管理员端：商品上架/下架切换生效', async ({ page }) => {
  await login(page, ADMIN);
  await page.goto('/#/page/admin_shop');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('.product-row, tr, .goods-row');
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });

  const toggle = page.getByRole('button', { name: /上架|下架/ }).first();
  const before = await toggle.innerText();
  await toggle.click();

  // 成功后列表刷新，按钮文案应翻转
  await expect
    .poll(async () => (await page.getByRole('button', { name: /上架|下架/ }).first().innerText()), {
      timeout: 15_000,
    })
    .not.toBe(before);

  // 复原，避免留下上下架副作用
  await page.getByRole('button', { name: /上架|下架/ }).first().click();
  await expect(page.locator('.el-message, .status-tag').first()).toBeVisible({ timeout: 15_000 });
});
