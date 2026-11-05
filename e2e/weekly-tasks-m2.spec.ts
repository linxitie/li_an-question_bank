import { expect, test, type Page } from '@playwright/test';

/**
 * M2 周任务：金币购「任务」页签展示
 * - 3 个置顶任务带「置顶」标记且排在最前
 * - 本周统计（周键 / 已领金币 / 上限）可见
 * - 置顶奖励 = 基础 × 难度 × 稀缺（416/365/270）
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

test('任务页签：置顶标记与本周统计', async ({ page }) => {
  await login(page);
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '任务' }).click();
  await expect(page.locator('.week-meta')).toBeVisible({ timeout: 20_000 });

  // 本周统计文案
  const meta = await page.locator('.week-meta').innerText();
  expect(meta).toMatch(/W\d{2}/);
  expect(meta).toContain('/900');

  // 3 个置顶标记
  const badges = page.locator('.pin-badge');
  await expect(badges.first()).toBeVisible();
  expect(await badges.count()).toBe(3);

  // 置顶任务排在最前：前 3 条任务标题里应含置顶任务名
  const titles = await page.locator('.task-title').allInnerTexts();
  const weeklyTitles = titles.slice(-11); // 周常区块
  expect(weeklyTitles[0]).toContain('本周完成 300 道题');
  expect(weeklyTitles[1]).toContain('本周完成 3 套真题');
  expect(weeklyTitles[2]).toContain('本周 5 天有刷题记录');

  // 置顶奖励体现稀缺系数：416 / 365 / 270
  const rewards = await page.locator('.task-reward').allInnerTexts();
  const weeklyRewards = rewards.slice(-11).map((t) => t.replace(/[^\d]/g, ''));
  expect(weeklyRewards[0]).toBe('416');
  expect(weeklyRewards[1]).toBe('365');
  expect(weeklyRewards[2]).toBe('270');
});
