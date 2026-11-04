import { expect, test, type Page } from '@playwright/test';

/**
 * 统一发帖弹窗（PostComposer）三端回归。
 *
 * 断言「图一」要求的结构：标题 / 正文工具条 / 字数计数 / 附件拖拽区 /
 * 可见范围 / 存为草稿 / 发布。只断言渲染，不真正提交，避免污染论坛数据。
 */

const STUDENT = { user: '202516001', pass: 'test123456' };
const TEACHER = { user: 'ycc5678', pass: 'ycc5678' };
const ADMIN = { user: 'cbrycc', pass: 'cbrycc' };

/** 8×8 红色 PNG（由 Pillow 生成，后端会真实解码校验） */
const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGO8ZGPEgA0wYRUdtBIA/ygBUM+oTXcAAAAASUVORK5CYII=';

async function login(page: Page, account: { user: string; pass: string }) {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(account.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(account.pass);
  await pwd.press('Enter');
  // 登录后落点按角色不同（学生 /#/home、教师 /#/teacher、管理员 /#/admin），只要求离开登录页
  await page.waitForURL((url) => !url.hash.includes('/login'), { timeout: 40_000 });
}

async function assertComposer(page: Page, shot?: string) {
  const mask = page.locator('.pc-mask');
  await expect(mask).toBeVisible({ timeout: 15_000 });
  await expect(mask.locator('.pc-hd h3')).toHaveText('发布新帖');

  // 标题 / 正文
  await expect(mask.getByPlaceholder(/给帖子起一个清晰的标题/)).toBeVisible();
  // 2026-11-03：正文改为 wangEditor 富文本（RichTextEditor），不再有 .editor textarea。
  // 断言内容区可编辑，并真实写入一段内容验证 v-model 通路。
  const richBody = mask.locator('.editor-rich .w-e-text-container [contenteditable="true"]');
  await expect(richBody).toBeVisible({ timeout: 15_000 });
  await richBody.click();
  await page.keyboard.type('测试正文');
  await expect(richBody).toContainText('测试正文');

  // 富文本工具栏由 wangEditor 渲染（段落/字体/字号/颜色/对齐/列表/表格…）
  const richToolbar = mask.locator('.editor-rich .w-e-toolbar');
  await expect(richToolbar).toBeVisible();
  expect(await richToolbar.locator('.w-e-menu').count()).toBeGreaterThanOrEqual(10);

  // 附件拖拽区
  await expect(mask.locator('.dropzone')).toBeVisible();

  // 可见范围 pills
  const pills = mask.locator('.radio-pills .rp');
  await expect(pills).toHaveCount(2);
  await expect(pills.nth(0)).toHaveText('全站可见');
  await expect(pills.nth(1)).toHaveText('仅指定班级');

  // 底部按钮
  await expect(mask.getByRole('button', { name: '存为草稿' })).toBeVisible();
  await expect(mask.getByRole('button', { name: '发布' })).toBeVisible();

  // 真正走一次图片上传：只有上传成功（HTTP 200）才会出现附件 chip。
  // 这条曾经 405 —— /api/media/image 路由没注册，落到 /api/media/{asset_id} 的 GET 上。
  const chooserPromise = page.waitForEvent('filechooser');
  await mask.locator('.dropzone').click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: 'probe.png',
    mimeType: 'image/png',
    buffer: Buffer.from(TINY_PNG_BASE64, 'base64')
  });
  await expect(mask.locator('.pc-file')).toHaveCount(1, { timeout: 20_000 });
  await expect(mask.locator('.pc-file')).toContainText('probe.png');

  if (shot) await page.screenshot({ path: shot });
  await mask.locator('.pc-x').click();
  await expect(mask).toBeHidden();
}

test.describe('统一发帖弹窗', () => {
  test('学生端（PC 论坛页）发帖弹窗为新样式', async ({ page }) => {
    await login(page, STUDENT);
    await page.goto('/#/forum');
    await page.waitForLoadState('networkidle');
    // .post-btn 同时被「我的收藏」星标复用，必须按文案点
    await page.getByRole('button', { name: '发布新帖' }).first().click();
    await assertComposer(page, 'e2e/.artifacts/composer-student.png');
  });

  test('教师端发帖弹窗为新样式', async ({ page }) => {
    await login(page, TEACHER);
    await page.goto('/#/teacher/forum');
    await page.waitForLoadState('networkidle');
    await page.locator('.tf-post-btn').first().click();
    await assertComposer(page);
  });

  test('管理员端发布新帖也是同一个弹窗', async ({ page }) => {
    await login(page, ADMIN);
    await page.goto('/#/admin/forum');
    await page.waitForLoadState('networkidle');
    // 看板页签按设计不显示「发布新帖」，先切到内容管理
    await page.locator('.tabs .tab', { hasText: '内容管理' }).click();
    await page.getByRole('button', { name: /发布新帖/ }).click();
    await assertComposer(page);
  });
});
