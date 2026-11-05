import { expect, test, type Page } from '@playwright/test';

/**
 * M2 周任务：金币购「任务」页签展示
 * - 3 个置顶任务带「置顶」标记且排在最前
 * - 本周统计（周键 / 已领金币 / 上限）可见
 * - 置顶奖励 = 基础 × 难度 × 稀缺（416/365/270）
 *
 * 注意：M3 起「周常任务」卡片里还可能包含本人的个性化任务，
 * 所以这里只取该卡片内的前 3 条做断言，不再依赖总数切片。
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

  const meta = await page.locator('.week-meta').innerText();
  expect(meta).toMatch(/W\d{2}/);
  expect(meta).toContain('/900');

  // 周常任务卡片：用标题「周常任务」定位，避免混入每日/随机任务
  const weeklyCard = page.locator('.gp-card').filter({ hasText: '周常任务' }).last();

  const badges = weeklyCard.locator('.pin-badge');
  await expect(badges.first()).toBeVisible();
  expect(await badges.count()).toBe(3);

  const titles = await weeklyCard.locator('.task-title').allInnerTexts();
  expect(titles[0]).toContain('本周完成 300 道题');
  expect(titles[1]).toContain('本周完成 3 套真题');
  expect(titles[2]).toContain('本周 5 天有刷题记录');

  const rewards = (await weeklyCard.locator('.task-reward').allInnerTexts())
    .slice(0, 3)
    .map((t) => t.replace(/[^\d]/g, ''));
  expect(rewards[0]).toBe('416');
  expect(rewards[1]).toBe('365');
  expect(rewards[2]).toBe('270');
});
