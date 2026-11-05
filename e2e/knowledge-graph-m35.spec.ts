import { expect, test, type Page } from '@playwright/test';

/**
 * M3.5：我的知识图谱页面（/student/knowledge/graph）
 *
 * 覆盖：SVG 节点与边渲染、节点详情、习惯画像卡、采样候选、生成任务按钮。
 * 依赖开发库已有真实行为数据（M3 验收时造过）。
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

test('知识图谱页：节点、边、习惯与候选渲染', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/knowledge/graph');
  await page.waitForLoadState('networkidle');

  await expect(page.locator('.kg-page')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('.kg-head h1')).toHaveText('我的知识图谱');

  // SVG 节点与边
  const nodes = page.locator('.kg-node');
  await expect(nodes.first()).toBeVisible({ timeout: 20_000 });
  expect(await nodes.count()).toBeGreaterThan(0);

  const edges = page.locator('.kg-edges line');
  expect(await edges.count()).toBeGreaterThan(0);

  // 习惯画像卡（含温度与提示）
  const habitCard = page.locator('.kg-card').filter({ hasText: '做题习惯' });
  await expect(habitCard).toBeVisible();
  const habitText = await habitCard.innerText();
  expect(habitText).toContain('采样温度');
  expect(habitText).toMatch(/节奏/);

  // 采样候选
  const sampleCard = page.locator('.kg-card').filter({ hasText: '本周任务候选' });
  await expect(sampleCard).toBeVisible();

  // 点击节点 → 详情
  await nodes.first().click();
  await expect(page.locator('.kg-node-detail')).toBeVisible();
  const detail = await page.locator('.kg-node-detail').innerText();
  expect(detail).toContain('掌握度');
  expect(detail).toContain('贡献度');
});

test('知识图谱页：生成个性化任务可点击', async ({ page }) => {
  await login(page);
  await page.goto('/#/student/knowledge/graph');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.kg-node').first()).toBeVisible({ timeout: 20_000 });

  const btn = page.getByRole('button', { name: '生成本周个性化任务' });
  await expect(btn).toBeEnabled();
  await btn.click();

  // ElMessage 成功提示（element-plus）
  await expect(page.locator('.el-message')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('.el-message')).toContainText('已生成');
});

test('金币购页「知识图谱」入口可进入', async ({ page }) => {
  await login(page);
  await page.goto('/#/page/gold_purchase');
  await page.waitForLoadState('networkidle');

  const entry = page.locator('.gp-kg-entry');
  await expect(entry).toBeVisible({ timeout: 20_000 });
  await entry.click();

  await expect.poll(() => page.url(), { timeout: 15_000 }).toContain('/student/knowledge/graph');
  await expect(page.locator('.kg-page')).toBeVisible({ timeout: 20_000 });
});
