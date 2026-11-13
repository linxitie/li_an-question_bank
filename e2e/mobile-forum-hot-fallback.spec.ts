import { expect, test, type Page } from '@playwright/test';

/**
 * #3 回归（2026-11-03 第 2 轮）：手机端「今日热门」当日无帖时，必须自动回退近 7 天并标注。
 *
 * 库里今天有帖，走不到回退分支，所以用网络拦截造「当天 0 条、近 7 天 1 条」的场景：
 *  - 第 1 次请求（当天区间）→ 返回空
 *  - 第 2 次请求（近 7 天区间）→ 返回 1 条
 * 断言：页签文案变成「今日热门 · 近 7 天」，且列表渲染出那条帖子。
 */

const STUDENT = { user: '202516001', pass: 'test123456' };

const SAMPLE_POST = {
  id: 990001,
  title: '近七日热门样例帖',
  content: '这条帖子用于验证近 7 天回退',
  contentFormat: 'TEXT',
  createTime: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
  viewCount: 0,
  commentCount: 0,
  likeCount: 5,
  liked: false,
  favorited: false,
  favoriteCount: 0,
  shareType: 'DISCUSSION',
  attachments: [],
  user: { nickname: '样例用户', avatar: '' }
};

async function login(page: Page) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(STUDENT.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(STUDENT.pass);
  await pwd.press('Enter');
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
}

test('手机端：今日热门当日无帖 → 回退近 7 天并标注', async ({ page }) => {
  // 先在桌面视口登录（移动视口下登录页是另一套表单），登录后再切手机视口
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });

  let postCalls = 0;
  let dayCalls = 0;
  let weekCalls = 0;
  await page.route('**/api/forum/posts**', async (route) => {
    postCalls += 1;
    const url = route.request().url();
    const from = /date_from=([\d-]+)/.exec(url)?.[1] ?? '';
    const to = /date_to=([\d-]+)/.exec(url)?.[1] ?? '';
    // 按「日期区间」而不是请求序号判断：首屏「全部」也会打同一接口，序号会错位。
    const isSingleDay = Boolean(from) && from === to;
    if (isSingleDay) {
      dayCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total: 0, limit: 50, offset: 0, posts: [] })
      });
      return;
    }
    if (from && to) {
      weekCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total: 1, limit: 50, offset: 0, posts: [SAMPLE_POST] })
      });
      return;
    }
    // 其它（首屏全部）原样放行
    await route.continue();
  });

  await page.goto('/#/mobile/forum');
  await page.waitForLoadState('domcontentloaded');

  // 切到「今日热门」页签
  const hotTab = page.locator('.cat-tab').filter({ hasText: '今日热门' }).first();
  await expect(hotTab).toBeVisible({ timeout: 20_000 });
  await hotTab.click();

  // 回退后页签应注明「近 7 天」
  await expect(page.locator('.cat-tab.active')).toContainText('近 7 天', { timeout: 15_000 });
  // 「当天」与「近 7 天」两个区间都应被请求过
  expect(dayCalls, '应请求过当日区间').toBeGreaterThanOrEqual(1);
  expect(weekCalls, '当日为空后应请求近 7 天区间').toBeGreaterThanOrEqual(1);
  expect(postCalls).toBeGreaterThanOrEqual(2);
  // 列表渲染出样例帖
  await expect(page.locator('.post-card').first()).toContainText('近七日热门样例帖', {
    timeout: 15_000
  });

  await page.screenshot({ path: 'e2e/.artifacts/mobile-forum-hot-week.png' });
});
