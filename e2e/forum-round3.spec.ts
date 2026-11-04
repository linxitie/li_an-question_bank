import { expect, test, type Page } from '@playwright/test';

/**
 * 第 3 轮回归（2026-11-03）：
 *  - #1 AI 标题前缀（用网络拦截注入 aiTitle，不依赖真实 LLM）
 *  - #2 点赞/收藏动画必须真的挂到「容器」上
 *  - #3 草稿保存后重开能回填
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

test('#1 有 aiTitle 的帖子标题前显示「AI生成」标记', async ({ page }) => {
  await page.route('**/api/forum/posts?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total: 1,
        limit: 20,
        offset: 0,
        posts: [
          {
            id: 880001,
            title: 'AI 总结出的标题',
            aiTitle: true,
            content: '正文内容',
            contentFormat: 'TEXT',
            createTime: new Date().toISOString(),
            viewCount: 1,
            commentCount: 0,
            likeCount: 0,
            liked: false,
            favorited: false,
            favoriteCount: 0,
            shareType: 'DISCUSSION',
            attachments: [],
            user: { nickname: '样例', avatar: '' }
          }
        ]
      })
    });
  });

  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');

  const tag = page.locator('.post-item .ai-title-tag').first();
  await expect(tag).toBeVisible({ timeout: 15_000 });
  await expect(tag).toHaveText('AI生成');
  await expect(page.locator('.post-item .post-title').first()).toContainText('AI 总结出的标题');
});

test('#2 点赞与收藏动画挂到容器上并真实触发', async ({ page }) => {
  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');

  // 分两段断言，避免与页面 15s 静默刷新抢节点：
  // (1) CSS 接线：给容器加上 active 类后，必须真的挂上动画（这正是上一轮打空的地方）
  const likeAnim = await page.locator('.meta-likes').first().evaluate((el) => {
    el.classList.add('active');
    return (el.getAnimations?.() ?? []).map((a) => (a as any).animationName);
  });
  expect(likeAnim.join(','), '点赞容器应挂载 dsh-ring 光圈').toContain('dsh-ring');

  const favAnim = await page.locator('.meta-favs').first().evaluate((el) => {
    el.classList.add('active');
    return (el.getAnimations?.() ?? []).map((a) => (a as any).animationName);
  });
  expect(favAnim.join(','), '收藏容器应挂载金色光圈/摇摆').toMatch(/dsh-ring-gold|dsh-star-wiggle/);

  // (2) 交互接线：真实点击必须打到 reactions 接口（点赞/取消都算通过）
  const reacted = page.waitForRequest(
    (req) => req.url().includes('/reactions') && req.method() !== 'GET',
    { timeout: 15_000 }
  );
  await page.locator('.meta-likes').first().click();
  const req = await reacted;
  expect(req.url()).toContain('/api/forum/posts/');
});

test('#3 存为草稿后关闭再打开能回填', async ({ page }) => {
  await login(page);
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');

  await page.locator('.post-btn', { hasText: '发布新帖' }).click();
  const mask = page.locator('.pc-mask');
  await expect(mask).toBeVisible({ timeout: 15_000 });

  const titleInput = mask.getByPlaceholder(/给帖子起一个清晰的标题/);
  const savedTitle = `草稿回填验证_${Date.now()}`;
  await titleInput.fill(savedTitle);

  const richBody = mask.locator('.editor-rich .w-e-text-container [contenteditable="true"]');
  await richBody.click();
  await page.keyboard.type('草稿正文验证');

  await mask.getByRole('button', { name: '存为草稿' }).click();
  await expect(page.locator('.el-message').filter({ hasText: '已保存到草稿箱' })).toBeVisible({
    timeout: 15_000
  });

  // 关闭弹窗：点右上角 × 或按 Esc
  const closeBtn = mask.locator('.pc-hd button').last();
  if (await closeBtn.count()) await closeBtn.click();
  else await page.keyboard.press('Escape');
  await expect(mask).toBeHidden({ timeout: 10_000 });

  // 重新打开：标题与正文都应回填
  await page.locator('.post-btn', { hasText: '发布新帖' }).click();
  await expect(mask).toBeVisible({ timeout: 15_000 });
  await expect(titleInput).toHaveValue(savedTitle, { timeout: 15_000 });
  await expect(richBody).toContainText('草稿正文验证', { timeout: 15_000 });

  await page.screenshot({ path: 'e2e/.artifacts/forum-draft-restored.png' });
});
