import { expect, test, type Page } from '@playwright/test';

/**
 * 2026-11-05：头像框到期
 * - 有效期内显示「剩 N 天」，可佩戴
 * - 已过期显示「已过期」且不可点击
 */

const STUDENT = { user: '202516001', pass: 'test123456' };

async function login(page: Page) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(STUDENT.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(STUDENT.pass);
  await pwd.press('Enter');
  await page.waitForURL((u) => !u.hash.includes('/login'), { timeout: 40_000 });
}

test('编辑资料：头像框显示剩余天数 / 已过期不可佩戴', async ({ page }) => {
  await login(page);
  await page.goto('/#/profile');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '编辑资料' }).first().click();
  const block = page.locator('.deco-block');
  await expect(block).toBeVisible({ timeout: 20_000 });

  // 头像框 chip：至少一个，且带「剩 N 天」或「已过期」标记
  const frameChips = block.locator('.deco-chip').filter({ hasText: '头像框' });
  await expect(frameChips.first()).toBeVisible({ timeout: 20_000 });

  const texts = await frameChips.allInnerTexts();
  const withExpiry = texts.filter((t) => t.includes('剩') || t.includes('已过期'));
  console.log('头像框 chips:', JSON.stringify(texts));
  expect(withExpiry.length).toBeGreaterThan(0);

  // 若存在已过期 chip，它必须是 disabled
  const expiredCount = await block.locator('.deco-chip.is-expired').count();
  if (expiredCount > 0) {
    await expect(block.locator('.deco-chip.is-expired').first()).toBeDisabled();
  }
});
