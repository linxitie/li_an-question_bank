import { expect, test, type Page } from '@playwright/test';

/**
 * 第 10 项回归：收藏 / 我的喜欢 / 今日热门 / 我的帖子 这些列表弹窗
 * 不能只显示标题，必须带 2–3 行正文摘要（.list-excerpt / .tf-fav-excerpt）。
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

test('学生端：列表弹窗显示正文摘要而不是只有标题', async ({ page }) => {
  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.forum-page')).toBeVisible();

  // 1) 今日热门「查看更多」弹窗
  const viewAll = page.locator('.my-posts-view-all').first();
  if (await viewAll.count()) {
    await viewAll.click();
    const hotItems = page.locator('.hot-item');
    await expect(hotItems.first()).toBeVisible({ timeout: 10_000 });
    const firstHot = hotItems.first();
    await expect(firstHot.locator('.list-excerpt')).toBeVisible();
    const text = (await firstHot.locator('.list-excerpt').innerText()).trim();
    expect(text.length, '热门列表正文摘要不能为空').toBeGreaterThan(0);
    await page.locator('.fav-modal .fav-close, .modal-overlay .cancel-btn, .modal-overlay button').first().click().catch(() => {});
    await page.keyboard.press('Escape');
  }

  // 2) 我的收藏 / 我的喜欢 弹窗
  const star = page.locator('.post-btn.star-only');
  await expect(star).toBeVisible();
  await star.click();
  await expect(page.locator('.fav-modal')).toBeVisible({ timeout: 10_000 });

  const favItems = page.locator('.fav-item');
  const favCount = await favItems.count();
  if (favCount > 0) {
    await expect(favItems.first().locator('.list-excerpt')).toBeVisible();
    const favText = (await favItems.first().locator('.list-excerpt').innerText()).trim();
    expect(favText.length, '收藏列表正文摘要不能为空').toBeGreaterThan(0);
  }

  await page.screenshot({ path: 'e2e/.artifacts/forum-list-excerpt.png' });
});
