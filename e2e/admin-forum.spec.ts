import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

/**
 * 管理员端论坛（P3a 列表/批量/抽屉 + P3b 数据看板 + 图片/表情/评论）的浏览器断言。
 *
 * 只做只读断言，唯一例外是「图片与评论」这条：它会自建一条带图片的帖子、
 * 发一条管理员评论，跑完用 purge 彻底删除，保证不残留测试数据。
 */

const ADMIN = { user: 'cbrycc', pass: 'cbrycc' };
const STUDENT = { user: '202516001', pass: 'test123456' };

/** 8×8 红色 PNG（由 Pillow 生成，后端会真实解码校验） */
const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGO8ZGPEgA0wYRUdtBIA/ygBUM+oTXcAAAAASUVORK5CYII=';

async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/#/login');
  await page.getByPlaceholder('请输入学号 / 教师编号').fill(ADMIN.user);
  const pwd = page.getByPlaceholder('请输入密码');
  await pwd.fill(ADMIN.pass);
  await pwd.press('Enter');
  await page.waitForURL(/#\/admin/, { timeout: 40_000 });
}

async function apiLogin(request: APIRequestContext, account: { user: string; pass: string }) {
  const res = await request.post('/api/auth/login', {
    form: { username: account.user, password: account.pass, client_type: 'web' }
  });
  expect(res.ok(), `登录失败：${res.status()}`).toBeTruthy();
  const body = await res.json();
  return body.access_token as string;
}

test.describe('管理员端论坛', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/#/admin/forum');
    await expect(page.locator('.af')).toBeVisible();
    await page.waitForLoadState('networkidle');
  });

  test('页面骨架与四个页签按设计稿渲染', async ({ page }) => {
    await expect(page.locator('.page-head h2')).toHaveText('论坛管理');

    const tabs = page.locator('.tabs .tab');
    await expect(tabs).toHaveCount(4);
    await expect(tabs.nth(0)).toHaveText(/数据看板/);
    await expect(tabs.nth(1)).toHaveText(/内容管理/);
    await expect(tabs.nth(2)).toHaveText(/待复核/);
    await expect(tabs.nth(3)).toHaveText(/回收站/);
    await expect(tabs.nth(0)).toHaveClass(/on/);
  });

  test('数据看板：6 个 KPI + 图表 + 关键词 + 风险提示', async ({ page, request }) => {
    // 看板的词云依赖「窗口内有帖」，而本套用例会清理自己造的测试数据，
    // 库里可能一条当天的帖子都没有 → 词云为空导致断言假失败。
    // 这里先自建几条带不同关键词的帖子，跑完 purge，保证断言不依赖外部数据。
    const studentToken = await apiLogin(request, STUDENT);
    const adminToken = await apiLogin(request, ADMIN);
    const seeded: number[] = [];
    const keywords = ['行测资料', '申论写作', '面试技巧', '公安联考', '备考计划', '真题变化'];
    try {
      for (const kw of keywords) {
        const res = await request.post('/api/forum/posts', {
          headers: { Authorization: `Bearer ${studentToken}` },
          form: {
            title: `${kw} 讨论`,
            content: `关于${kw}的经验分享，希望和大家交流一下具体的复习方法。`,
            content_format: 'TEXT',
            visibility: 'ALL',
            ai_title_enabled: 'false'
          }
        });
        if (res.ok()) seeded.push((await res.json()).id);
      }

      await page.reload();
      await expect(page.locator('.af')).toBeVisible();
      await page.waitForLoadState('networkidle');

      const kpis = page.locator('.kpi-row .kpi');
      await expect(kpis).toHaveCount(6);
      await expect(kpis.nth(0).locator('.k-label')).toHaveText('发帖量');

      const segs = page.locator('.seg-time button');
      await expect(segs).toHaveCount(3);
      await expect(segs.nth(0)).toHaveClass(/on/);
      expect(await page.locator('.dash-grid canvas').count()).toBeGreaterThanOrEqual(3);

      const words = page.locator('.wordcloud .w');
      await expect(words.first()).toBeVisible({ timeout: 20_000 });
      expect(await words.count()).toBeGreaterThan(0);
      await expect(page.locator('.sub').filter({ hasText: /词频 TOP/ })).toBeVisible();
      await expect(words.first()).toHaveAttribute('title', /次$/);

      const boxes = await words.evaluateAll((els) =>
        els.map((el) => {
          const r = el.getBoundingClientRect();
          return { y: Math.round(r.y), size: parseFloat(getComputedStyle(el).fontSize) };
        })
      );
      expect(new Set(boxes.map((b) => b.y)).size, '词云必须是散点分布').toBeGreaterThan(5);
      expect(new Set(boxes.map((b) => b.size)).size, '字号至少 3 档').toBeGreaterThanOrEqual(3);

      const overflow = await page.evaluate(() => {
        const box = document.querySelector('.wordcloud') as HTMLElement | null;
        if (!box) return ['容器不存在'];
        const outer = box.getBoundingClientRect();
        return Array.from(box.querySelectorAll('.w'))
          .filter((el) => {
            const r = el.getBoundingClientRect();
            return (
              r.left < outer.left - 1 ||
              r.right > outer.right + 1 ||
              r.top < outer.top - 1 ||
              r.bottom > outer.bottom + 1
            );
          })
          .map((el) => el.textContent || '');
      });
      expect(overflow, `这些词溢出了词云容器：${overflow.join('、')}`).toHaveLength(0);

      const radius = await page.evaluate(() => {
        const box = document.querySelector('.wordcloud') as HTMLElement;
        const outer = box.getBoundingClientRect();
        const cx = outer.left + outer.width / 2;
        const cy = outer.top + outer.height / 2;
        return Array.from(box.querySelectorAll('.w')).map((el) => {
          const r = el.getBoundingClientRect();
          const dx = r.left + r.width / 2 - cx;
          const dy = r.top + r.height / 2 - cy;
          return { text: el.textContent || '', d: Math.sqrt(dx * dx + dy * dy) };
        });
      });
      expect(radius[0].d, `「${radius[0].text}」应最靠中心`).toBe(Math.min(...radius.map((r) => r.d)));
      const half = Math.floor(radius.length / 2);
      const inner = radius.slice(0, half).reduce((s, r) => s + r.d, 0) / Math.max(1, half);
      const outerAvg =
        radius.slice(half).reduce((s, r) => s + r.d, 0) / Math.max(1, radius.length - half);
      expect(outerAvg, '低热度词应比高热度词离中心更远').toBeGreaterThan(inner);

      await page.locator('.wordcloud').scrollIntoViewIfNeeded();
      await page.locator('.wordcloud').screenshot({ path: 'e2e/.artifacts/wordcloud.png' });
      await expect(page.locator('.hbars .hbar')).toHaveCount(4);
      expect(await page.locator('.risk .item').count()).toBeGreaterThan(0);

      await page.screenshot({ path: 'e2e/.artifacts/admin-forum-dashboard.png' });
      await segs.nth(1).click();
      await expect(segs.nth(1)).toHaveClass(/on/);
      await expect(page.locator('.kpi-row .kpi')).toHaveCount(6);
    } finally {
      for (const id of seeded) {
        await request.delete(`/api/admin/forum/posts/${id}/purge`, {
          headers: { Authorization: `Bearer ${adminToken}` }
        });
      }
    }
  });

  test('内容管理：筛选条 / 真实数据 / 分页', async ({ page }) => {
    await page.locator('.tabs .tab').nth(1).click();
    await expect(page.locator('.tabs .tab').nth(1)).toHaveClass(/on/);

    await expect(page.locator('.filterbar .field.search')).toBeVisible();
    await expect(page.locator('.filterbar select.plain')).toHaveCount(2);
    await expect(page.locator('.filterbar .field.date')).toBeVisible();

    const rows = page.locator('.table-wrap tbody tr');
    await expect(rows.first()).toBeVisible();
    expect(await rows.count(), '至少应有一行真实帖子').toBeGreaterThan(0);
    await expect(page.locator('.pager span').first()).toHaveText(/共 \d+ 条/);
  });

  test('点标题打开右侧抽屉并加载评论', async ({ page }) => {
    await page.locator('.tabs .tab').nth(1).click();
    await page.locator('.cell-post .ttl').first().click();
    const drawer = page.locator('.drawer');
    await expect(drawer).toHaveClass(/on/, { timeout: 10_000 });
    await expect(page.locator('.drawer .drawer-hd h3')).toHaveText('帖子详情');
    await expect(page.locator('.drawer .post-main')).toBeVisible();
    await expect(page.locator('.drawer .cmt-sec h4')).toContainText('评论区');
    // 管理员代发评论的输入框必须在
    await expect(page.locator('.drawer .cmt-input input')).toBeVisible();
  });

  test('待复核与回收站页签可切换', async ({ page }) => {
    await page.locator('.tabs .tab').nth(2).click();
    await expect(page.locator('.table-wrap thead th').first()).toBeVisible();

    await page.locator('.tabs .tab').nth(3).click();
    await expect(page.locator('.noticebar')).toBeVisible();
    await expect(page.locator('.table-wrap thead th').first()).toBeVisible();

    await page.locator('.tabs .tab').nth(1).click();
    await expect(page.locator('.filterbar')).toBeVisible();
    await page.screenshot({ path: 'e2e/.artifacts/admin-forum-list.png' });
  });

  test('能看见帖子图片，并能以管理员身份发表评论', async ({ page, request }) => {
    const studentToken = await apiLogin(request, STUDENT);
    const marker = `DSH图片验证${Date.now()}`;

    // 1) 学生上传一张图片（这条链路此前 405）
    const upload = await request.post('/api/media/image', {
      headers: { Authorization: `Bearer ${studentToken}` },
      multipart: {
        file: {
          name: 'probe.png',
          mimeType: 'image/png',
          buffer: Buffer.from(TINY_PNG_BASE64, 'base64')
        }
      }
    });
    expect(upload.status(), `图片上传应成功：${await upload.text()}`).toBe(200);
    const attachment = await upload.json();

    // 2) 用这张图片发一条帖子
    const created = await request.post('/api/forum/posts', {
      headers: { Authorization: `Bearer ${studentToken}` },
      form: {
        title: marker,
        content: `这条帖子的正文包含一张图片 [[sticker:${attachment.url}]]`,
        attachments: JSON.stringify([
          {
            name: attachment.name,
            url: attachment.url,
            size: attachment.size,
            type: attachment.type
          }
        ])
      }
    });
    expect(created.ok(), `发帖应成功：${created.status()} ${await created.text()}`).toBeTruthy();
    const postId = (await created.json()).id as number;

    try {
      // 3) 管理端列表能看到图片
      await page.locator('.tabs .tab').nth(1).click();
      await page.locator('.filterbar .field.search input').fill(marker);
      await page.getByRole('button', { name: '查询' }).click();
      const row = page.locator('.table-wrap tbody tr').first();
      await expect(row).toContainText(marker);
      await expect(row.locator('.image-grid img').first()).toBeVisible({ timeout: 10_000 });
      await expect(row.locator('.attachment-list img, .ig-cell img').first()).toBeVisible();

      // 4) 抽屉里也能看到图片，并能发评论
      await row.locator('.cell-post .ttl').click();
      await expect(page.locator('.drawer')).toHaveClass(/on/);
      await expect(page.locator('.drawer .post-main img').first()).toBeVisible({ timeout: 10_000 });

      const text = `管理员评论 ${Date.now()}`;
      await page.locator('.drawer .cmt-input input').fill(text);
      await page.locator('.drawer .cmt-input button').click();
      await expect(page.locator('.drawer .cmt .tx').filter({ hasText: text })).toBeVisible({
        timeout: 15_000
      });

      await page.screenshot({ path: 'e2e/.artifacts/admin-forum-media-comment.png' });
    } finally {
      // 5) 无论断言成败都彻底删除这条测试帖，不给库里留垃圾
      const adminToken = await apiLogin(request, ADMIN);
      const purged = await request.delete(`/api/admin/forum/posts/${postId}/purge`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      expect(purged.ok(), '测试帖清理失败').toBeTruthy();
    }
  });
});
