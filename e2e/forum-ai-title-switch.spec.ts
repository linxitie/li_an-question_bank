import { expect, test, type Page } from '@playwright/test';

/**
 * v4 回归（2026-11-04）：发帖弹窗的「AI 自动总结标题」开关。
 *
 * 用网络拦截验证行为，不依赖后端实现细节：
 *  - 开关默认打开
 *  - 关闭后提交带 ai_title_enabled=false（multipart 表单）
 *  - 「AI 生成标题」把建议填进标题框（mock 接口）
 *  - 手改标题后不再声称是 AI 原样产出
 *
 * 注意：弹窗可能自动回填上次草稿（v3 的草稿恢复功能），
 * 所以每条用例都先清空标题，避免「已有标题 → 触发覆盖确认」干扰断言。
 */

const STUDENT = { user: '202516001', pass: 'test123456' };

async function openComposer(page: Page) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(STUDENT.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(STUDENT.pass);
  await pwd.press('Enter');
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
  await page.goto('/#/forum');
  await page.waitForLoadState('networkidle');
  await page.locator('.post-btn', { hasText: '发布新帖' }).click();
  const mask = page.locator('.pc-mask');
  await expect(mask).toBeVisible({ timeout: 15_000 });
  // 清掉可能的草稿回填，保证用例从空表单开始。
  // 草稿是异步拉取的（v3 的回填功能），可能在本行之后才写入，所以等一拍再清一次。
  const titleInput = mask.getByPlaceholder(/给帖子起一个清晰的标题/);
  await titleInput.fill('');
  await page.waitForTimeout(1200);
  await titleInput.fill('');
  await expect(titleInput).toHaveValue('');
  return mask;
}

test('开关默认打开，关闭后发布请求带 ai_title_enabled=false', async ({ page }) => {
  const mask = await openComposer(page);

  const toggle = mask.locator('.ai-switch input[type="checkbox"]');
  await expect(toggle).toBeChecked();

  let postedForm = '';
  await page.route('**/api/forum/posts', async (route) => {
    if (route.request().method() === 'POST') {
      // multipart/form-data 的原文里字段名是 name="xxx"，不是 xxx=
      postedForm = route.request().postData() || '';
    }
    await route.continue();
  });

  await mask.getByPlaceholder(/给帖子起一个清晰的标题/).fill('开关关闭测试');
  const richBody = mask.locator('.editor-rich .w-e-text-container [contenteditable="true"]');
  await richBody.click();
  await page.keyboard.type('这是一段用于验证开关的正文内容');

  await toggle.uncheck();
  await expect(mask.locator('.ai-switch-tip')).toContainText('已关闭');

  await mask.getByRole('button', { name: '发布' }).click();
  await expect.poll(() => postedForm, { timeout: 20_000 }).toContain('ai_title_enabled');
  expect(postedForm).toContain('false');
});

test('点「AI 生成标题」把建议填入标题框，手改后不再标记 AI', async ({ page }) => {
  await page.route('**/api/forum/ai-title/suggest', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ title: '公安联考行测资料选择', reason: null, remaining: 29 })
    });
  });

  const mask = await openComposer(page);
  const richBody = mask.locator('.editor-rich .w-e-text-container [contenteditable="true"]');
  await richBody.click();
  await page.keyboard.type('推荐几本公安联考行测的备考资料，粉笔的题更新一些');

  // 标题为空时点生成，不会触发「覆盖确认」
  await mask.locator('.ai-suggest-btn').click();

  const titleInput = mask.getByPlaceholder(/给帖子起一个清晰的标题/);
  await expect(titleInput).toHaveValue('公安联考行测资料选择', { timeout: 15_000 });
  await expect(mask.locator('.ai-suggest-btn')).toHaveText('重新生成');
  await expect(mask.locator('.ai-ok-tip')).toBeVisible();

  // 手改标题后，不再声称是 AI 原样产出
  await titleInput.fill('我自己改过的标题');
  await expect(mask.locator('.ai-ok-tip')).toBeHidden();
});
