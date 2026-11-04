import { expect, test, type Page } from '@playwright/test';

/**
 * 第 2 轮回归（2026-11-03）：
 *  - #4 「查看更多」弹窗里必须能看到正文摘要（不是只有标题）
 *  - #5 点赞计数必须是纯数字，爱心旁不能出现「👍」
 *  - #1 详情里的超长标题不能顶破卡片
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

test('#4 查看更多弹窗显示正文摘要，而不是只有标题', async ({ page }) => {
  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.forum-page')).toBeVisible();

  // 今日热门 → 查看更多
  const viewAll = page.locator('.my-posts-view-all').first();
  await expect(viewAll).toBeVisible({ timeout: 15_000 });
  await viewAll.click();

  await expect(page.locator('.modal-overlay.modal-l1')).toBeVisible({ timeout: 10_000 });
  const items = page.locator('.modal-overlay.modal-l1 .my-post-item');
  await expect(items.first()).toBeVisible({ timeout: 10_000 });

  const excerpt = items.first().locator('.list-excerpt');
  await expect(excerpt).toBeVisible();
  const text = (await excerpt.innerText()).trim();
  expect(text.length, '查看更多弹窗里的正文摘要不能为空').toBeGreaterThan(0);

  // 布局断言：摘要必须真的占一行，而不是被 flex 挤成 0 宽
  const box = await excerpt.boundingBox();
  expect(box?.width ?? 0, '摘要宽度过小说明被布局挤没了').toBeGreaterThan(80);

  await page.screenshot({ path: 'e2e/.artifacts/forum-list-excerpt.png' });
});

test('#5 点赞计数是纯数字，不含大拇指 emoji', async ({ page }) => {
  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');

  const likeBtn = page.locator('.meta-likes').first();
  await expect(likeBtn).toBeVisible({ timeout: 15_000 });
  await likeBtn.click();
  await page.waitForTimeout(800);

  const label = (await likeBtn.innerText()).trim();
  // 允许前缀爱心（♡/❤），计数据部分必须是纯数字；关键是不能再出现「👍」
  expect(label, `点赞计数不应包含 emoji：${label}`).not.toContain('👍');
  const digits = label.replace(/[^\d]/g, '');
  expect(digits.length, `点赞计数里没有数字：${label}`).toBeGreaterThan(0);
  expect(label.replace(/[\s\d♡❤️]/g, ''), `除爱心外不应有别的符号：${label}`).toBe('');
});

test('#1 详情里的超长标题不越过卡片边缘', async ({ page }) => {
  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');

  // 找到标题最长的一条帖子（库里有一条连写数字标题）
  const titles = page.locator('.post-item .post-title');
  await expect(titles.first()).toBeVisible({ timeout: 20_000 });
  const count = await titles.count();
  expect(count).toBeGreaterThan(0);

  let longest = 0;
  let idx = 0;
  for (let i = 0; i < count; i += 1) {
    const len = (await titles.nth(i).innerText()).trim().length;
    if (len > longest) {
      longest = len;
      idx = i;
    }
  }

  await titles.nth(idx).click();
  const detail = page.locator('.modal-overlay.modal-l2');
  await expect(detail).toBeVisible({ timeout: 15_000 });

  const title = detail.locator('.detail-title').first();
  if (await title.count()) {
    const overflow = await title.evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflow, '详情标题横向溢出（scrollWidth > clientWidth）').toBeLessThanOrEqual(1);
  }

  // 详情卡片本身也不能被撑出弹窗
  const cardOverflow = await detail
    .locator('.post-detail-card')
    .first()
    .evaluate((el) => el.scrollWidth - el.clientWidth);
  expect(cardOverflow, '详情卡片被内容撑宽').toBeLessThanOrEqual(1);
});
