import { expect, test, type Page } from '@playwright/test';

/**
 * 管理员端布局回归：滚动时左侧导航必须固定。
 *
 * 依据：`.admin-layout` 高度锁死 100vh + overflow hidden，`.admin-main` 是唯一滚动容器；
 * 侧栏不再跟随 document 滚动。断言全部取自真实浏览器计算样式，不靠肉眼。
 */

const ADMIN = { user: 'cbrycc', pass: 'cbrycc' };

async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(ADMIN.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(ADMIN.pass);
  await pwd.press('Enter');
  await page.waitForURL(/#\/admin/, { timeout: 40_000 });
}

test.describe('管理员端：左侧导航固定', () => {
  test('滚动内容时侧栏不移动，document 不产生滚动', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/#/admin/forum');

    const sidebar = page.locator('.admin-sidebar');
    await expect(sidebar).toBeVisible();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    const before = await page.evaluate(() => {
      const layout = document.querySelector('.admin-layout') as HTMLElement;
      const main = document.querySelector('.admin-main') as HTMLElement;
      return {
        viewportHeight: window.innerHeight,
        layoutHeight: getComputedStyle(layout).height,
        layoutOverflowY: getComputedStyle(layout).overflowY,
        docScrollable: document.documentElement.scrollHeight - document.documentElement.clientHeight,
        mainClientHeight: main.clientHeight,
        mainScrollHeight: main.scrollHeight
      };
    });

    // 1) 布局高度被锁成视口高，且关掉外层溢出
    expect(Math.round(parseFloat(before.layoutHeight))).toBe(before.viewportHeight);
    expect(before.layoutOverflowY).toBe('hidden');

    // 2) document 本身不再可滚动（这正是侧栏会跟着走的根因）
    expect(before.docScrollable).toBeLessThanOrEqual(0);

    // 3) 滚动唯一容器：.admin-main
    const scrollable = before.mainScrollHeight > before.mainClientHeight;
    expect(scrollable, '.admin-main 内容不足以滚动，断言无意义').toBe(true);

    await page.evaluate(() => {
      (document.querySelector('.admin-main') as HTMLElement).scrollTop = 600;
    });
    await page.waitForTimeout(300);

    const after = await page.evaluate(() => {
      const main = document.querySelector('.admin-main') as HTMLElement;
      return { mainScrollTop: main.scrollTop, windowScrollY: window.scrollY };
    });

    // 4) 内部真的滚动了，而窗口没滚
    expect(after.mainScrollTop).toBeGreaterThan(0);
    expect(after.windowScrollY).toBe(0);

    // 5) 侧栏几何位置仍贴在视口顶部，且高度铺满视口
    const box = await sidebar.boundingBox();
    expect(box).not.toBeNull();
    expect(Math.round(box!.y)).toBe(0);
    expect(Math.round(box!.height)).toBe(before.viewportHeight);

    await page.screenshot({ path: 'e2e/.artifacts/admin-forum-sidebar-after-scroll.png' });
  });
});
