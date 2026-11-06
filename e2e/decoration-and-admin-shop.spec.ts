import { expect, test, type Page } from '@playwright/test';

/**
 * 2026-11-05 第三轮：
 * 1. 管理员左侧导航有「金币商城」
 * 2. 学生「编辑资料」里有「我的装扮」（称号 / 头像框），可佩戴
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

test('管理员导航：金币商城入口可进入', async ({ page }) => {
  await login(page, ADMIN);
  await page.goto('/#/admin/dashboard');
  await page.waitForLoadState('networkidle');

  const menu = page.getByText('金币商城', { exact: true }).first();
  await expect(menu).toBeVisible({ timeout: 20_000 });

  await menu.click();
  await expect.poll(() => page.url(), { timeout: 15_000 }).toContain('admin_shop');
  await expect(page.getByRole('button', { name: /上架|下架/ }).first()).toBeVisible({
    timeout: 20_000,
  });
});

test('学生编辑资料：我的装扮可佩戴称号与头像框', async ({ page }) => {
  await login(page, STUDENT);
  await page.goto('/#/profile');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '编辑资料' }).first().click();
  await expect(page.locator('.deco-block')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.deco-title')).toHaveText('我的装扮');

  // 称号 chip 存在（测试账号已发放「学习之星」）
  const titleChip = page.locator('.deco-chip').filter({ hasText: '学习之星' }).first();
  await expect(titleChip).toBeVisible({ timeout: 20_000 });
  await titleChip.click();
  await expect(titleChip).toHaveClass(/is-on/, { timeout: 15_000 });

  // 头像框 chip 存在
  const frameChip = page.locator('.deco-chip').filter({ hasText: '限定头像框' }).first();
  await expect(frameChip).toBeVisible({ timeout: 20_000 });
  await frameChip.click();
  await expect(frameChip).toHaveClass(/is-on/, { timeout: 15_000 });

  // 刷新后仍然保持佩戴状态（写入成功）
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: '编辑资料' }).first().click();
  await expect(page.locator('.deco-chip.is-on').first()).toBeVisible({ timeout: 20_000 });
});
