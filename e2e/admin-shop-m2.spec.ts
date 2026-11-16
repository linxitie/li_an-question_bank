import { expect, test, type Page } from '@playwright/test';

/**
 * 2026-11-05 第四轮（管理员金币商城页）：
 * - 左侧导航常驻（路由挂在 AdminLayout 下）
 * - 在售/已下架分离：列表只显示在售，"已下架"单独入口
 * - 新增弹窗有分类下拉、权益类型下拉、上传照片、金币价输入
 */

const ADMIN = { user: 'cbrycc', pass: 'cbrycc' };

async function login(page: Page, account: { user: string; pass: string }) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(account.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(account.pass);
  await pwd.press('Enter');
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
}

test('管理员金币商城：导航常驻 + 在售/已下架分离', async ({ page }) => {
  await login(page, ADMIN);
  await page.goto('/#/admin/shop');
  await page.waitForLoadState('networkidle');

  // 左侧导航常驻
  await expect(page.getByText('金币商城', { exact: true }).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('系统总览', { exact: true }).first()).toBeVisible();

  // 先等列表渲染完成，再统计状态标签
  await expect(page.locator('.as-table tbody tr').first()).toBeVisible({ timeout: 20_000 });
  const tags = await page.locator('.as-table .status-tag').allInnerTexts();
  expect(tags.length).toBeGreaterThan(0);
  tags.forEach((t) => expect(t).toContain('在售'));

  // 已下架按钮带数量，点开能看到下架商品
  const offBtn = page.locator('.as-offshelf-btn');
  await expect(offBtn).toBeVisible();
  const offText = await offBtn.innerText();
  expect(offText).toContain('已下架');

  await offBtn.click();
  await expect(page.locator('.as-offshelf-modal')).toBeVisible({ timeout: 15_000 });
  const offRows = page.locator('.as-offshelf-modal .as-table tbody tr');
  await expect(offRows.first()).toBeVisible({ timeout: 15_000 });
  expect(await offRows.count()).toBeGreaterThan(0);
  await page.locator('.as-offshelf-modal .close-btn').click();
  await expect(page.locator('.as-offshelf-modal')).toHaveCount(0);
});

test('管理员金币商城：新增弹窗含分类/权益类型/图片上传', async ({ page }) => {
  await login(page, ADMIN);
  await page.goto('/#/admin/shop');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '+ 新增商品' }).click();
  const modal = page.locator('.modal').first();
  await expect(modal).toBeVisible({ timeout: 15_000 });

  // 分类下拉：含「警大文创」「文具」「习题册」
  const selects = modal.locator('select');
  const categoryOptions = await selects.nth(0).locator('option').allInnerTexts();
  expect(categoryOptions).toEqual(expect.arrayContaining(['专属头像框', '限定称号', '文具', '习题册', '警大文创']));

  // 权益类型下拉：含称号/头像框/卡密/人工处理
  const typeOptions = await selects.nth(1).locator('option').allInnerTexts();
  expect(typeOptions).toEqual(expect.arrayContaining(['称号', '头像框', '卡密', '人工处理']));

  // 新增类型按钮 ×2
  expect(await modal.getByRole('button', { name: '+ 新增类型' }).count()).toBe(2);

  // 上传照片按钮 + 金币价输入
  await expect(modal.getByRole('button', { name: /上传照片（自动抠像）/ })).toBeVisible();
  await expect(modal.locator('input[type="number"][placeholder="管理员自定义"]')).toBeVisible();

  // 权益参数说明文案
  const hint = await modal.innerText();
  expect(hint).toContain('权益参数');
  expect(hint).toContain('title_id');
});
