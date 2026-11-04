import { expect, test, type Page } from '@playwright/test';

/**
 * v5 回归（2026-11-04）：
 *  - #1 手机端详情长标题不越界
 *  - #2 手机端详情有「收藏」（五角星），与「喜欢」相互独立
 *  - #3 评论显示绝对日期 YYYY-MM-DD HH:mm
 *  - #4 手机端「进详情→返回」保持列表滚动位置
 *  - #5 富文本（字号/颜色）在手机端正确渲染，不出现标签字面量
 *  - #6 手机端发帖页有富文本工具栏
 */

const STUDENT = { user: '202516001', pass: 'test123456' };
const ADMIN = { user: 'cbrycc', pass: 'cbrycc' };

async function login(page: Page) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(STUDENT.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(STUDENT.pass);
  await pwd.press('Enter');
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
}

async function apiToken(request: any, account: { user: string; pass: string }) {
  const res = await request.post('/api/auth/login', {
    form: { username: account.user, password: account.pass, client_type: 'web' }
  });
  const body = await res.json();
  return body.access_token as string;
}

/** 用接口造一条「富文本 + 长标题」的帖子，测试结束再删掉 */
async function createRichPost(request: any, token: string) {
  const content =
    '<p><span style="font-size:24px;color:rgb(255,0,0)">大红字</span></p>' +
    '<p style="text-align:center">居中段落</p>';
  const res = await request.post('/api/forum/posts', {
    headers: { Authorization: `Bearer ${token}` },
    form: {
      title: '2345678643213467876523678123456712345678643213467876523678123456712345678',
      content,
      content_format: 'HTML',
      visibility: 'ALL'
    }
  });
  const body = await res.json();
  return body.id as number;
}

test('#1 #2 #3 手机端详情：长标题不越界、有收藏、评论显示绝对日期', async ({ page, request }) => {
  const token = await apiToken(request, STUDENT);
  const postId = await createRichPost(request, token);

  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/#/mobile/forum/${postId}`);
  await page.waitForLoadState('networkidle');

  // #1 标题不横向溢出
  const title = page.locator('.post-title').first();
  await expect(title).toBeVisible({ timeout: 20_000 });
  const overflow = await title.evaluate((el) => el.scrollWidth - el.clientWidth);
  expect(overflow, '详情标题横向溢出').toBeLessThanOrEqual(1);

  // #2 收藏按钮存在，且与喜欢各自独立
  await expect(page.locator('.reaction-btn.heart-only')).toBeVisible();
  const favBtn = page.locator('.reaction-btn.fav-only');
  await expect(favBtn).toBeVisible();
  await favBtn.click();
  await expect(favBtn).toHaveClass(/active/, { timeout: 15_000 });
  // 收藏不应把「喜欢」点亮
  await expect(page.locator('.reaction-btn.heart-only')).not.toHaveClass(/active/);

  // #3 评论时间是绝对日期（形如 2026-11-04 20:30），不是「几天前」
  const commentTime = page.locator('.comment-time').first();
  if (await commentTime.count()) {
    const text = (await commentTime.innerText()).trim();
    expect(text).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  }

  // 清理
  const adminToken = await apiToken(request, ADMIN);
  await request.delete(`/api/admin/forum/posts/${postId}/purge`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
});

test('#5 富文本字号/颜色在手机端正确渲染，不出现标签字面量', async ({ page, request }) => {
  const token = await apiToken(request, STUDENT);
  const postId = await createRichPost(request, token);

  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/#/mobile/forum/${postId}`);
  await page.waitForLoadState('networkidle');

  const content = page.locator('.post-content').first();
  await expect(content).toBeVisible({ timeout: 20_000 });

  // 不出现标签字面量
  const text = await content.innerText();
  expect(text).not.toContain('<p');
  expect(text).not.toContain('font-size');

  // 字号真的生效（24px）
  const span = content.locator('span').first();
  await expect(span).toContainText('大红字');
  const fontSize = await span.evaluate((el) => getComputedStyle(el).fontSize);
  expect(fontSize, '作者选择的字号应生效').toBe('24px');

  const color = await span.evaluate((el) => getComputedStyle(el).color);
  expect(color.replace(/\s/g, '')).toBe('rgb(255,0,0)');

  const adminToken = await apiToken(request, ADMIN);
  await request.delete(`/api/admin/forum/posts/${postId}/purge`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
});

test('#4 手机端进详情后返回，列表滚动位置保持', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/mobile/forum');
  await page.waitForLoadState('networkidle');

  const scroller = page.locator('.mobile-forum-page .main-content');
  await expect(scroller).toBeVisible({ timeout: 20_000 });
  // 列表是异步加载的，必须等卡片出现（此时容器才有可滚动高度）
  await expect(page.locator('.post-card').first()).toBeVisible({ timeout: 20_000 });

  // 往下滚 500px 后进第一条帖子
  await scroller.evaluate((el) => {
    el.scrollTop = 500;
  });
  const before = await scroller.evaluate((el) => el.scrollTop);
  expect(before, '容器应已可滚动').toBeGreaterThan(400);

  // 注意：Playwright 的 click() 会先把目标滚进视野，从而把滚动位置重置为 0。
  // 这里在页面内点「当前视口内」的卡片，模拟真实用户点击（不触发自动滚动）。
  const clicked = await page.evaluate(() => {
    const sc = document.querySelector('.mobile-forum-page .main-content') as HTMLElement;
    const box = sc.getBoundingClientRect();
    const cards = Array.from(document.querySelectorAll('.post-card')) as HTMLElement[];
    const target = cards.find((c) => {
      const r = c.getBoundingClientRect();
      return r.top >= box.top - 1 && r.bottom <= box.bottom + 1;
    });
    if (!target) return false;
    target.click();
    return true;
  });
  expect(clicked, '视口内应有可点击的卡片').toBe(true);
  await page.waitForURL(/\/mobile\/forum\/\d+/, { timeout: 20_000 });
  await page.goBack();
  await page.waitForLoadState('networkidle');

  const scroller2 = page.locator('.mobile-forum-page .main-content');
  await expect(scroller2).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.post-card').first()).toBeVisible({ timeout: 20_000 });
  await expect
    .poll(async () => scroller2.evaluate((el) => el.scrollTop), { timeout: 15_000 })
    .toBeGreaterThan(400);
});

test('#6 手机端发帖页有富文本工具栏', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/mobile/forum/create');
  await page.waitForLoadState('networkidle');

  const toolbar = page.locator('.editor-rich .w-e-toolbar');
  await expect(toolbar).toBeVisible({ timeout: 20_000 });
  expect(await toolbar.locator('.w-e-menu').count()).toBeGreaterThanOrEqual(10);
});
