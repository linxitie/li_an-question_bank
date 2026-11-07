// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * A1 注入的 DOM 级验证（jsdom）：直接对着「管理页真实结构的最小复刻」跑，
 * 证明三件事——选项补进去了、统计卡补进去了、离开页面能干净移除。
 *
 * 页面真实结构来自 `.vtj/vue/admin_materials.vue`（L5/L35-41 统计与类型下拉）。
 */
vi.mock('@/modules/library/api', () => ({
  fetchAdminMaterialStats: vi.fn(async () => ({
    total: 119,
    by_type: { video_intro: 0, video_advanced: 0, article: 3, card: 116, lecture: 85, paper: 3 },
    by_subject: { xingce: 0, shenlun: 0, gongzhuan: 0 },
    by_status: { published: 102, draft: 17 }
  }))
}));

import { installAdminMaterialTypes } from '../adminMaterialTypes';

/** 管理页最小复刻：4 格统计 + 筛选条（科目/类型/状态） */
function mountPage(): void {
  document.body.innerHTML = `
    <div class="adm-page">
      <div class="stats-overview">
        <div class="stat-card"><div class="stat-value">119</div><div class="stat-label">总资料数</div></div>
        <div class="stat-card"><div class="stat-value">0</div><div class="stat-label">视频</div></div>
        <div class="stat-card"><div class="stat-value">3</div><div class="stat-label">文档</div></div>
        <div class="stat-card"><div class="stat-value">116</div><div class="stat-label">卡片</div></div>
      </div>
      <header class="bar">
        <div class="ops">
          <select id="fSubject"><option value="">全部科目</option><option value="xingce">行测</option></select>
          <select id="fType">
            <option value="">全部类型</option>
            <option value="video_intro">入门视频</option>
            <option value="video_advanced">进阶视频</option>
            <option value="article">文章</option>
            <option value="card">知识卡片</option>
          </select>
          <select id="fStatus"><option value="">全部状态</option><option value="1">已发布</option></select>
        </div>
      </header>
    </div>`;
}

const typeSelect = () => document.getElementById('fType') as HTMLSelectElement;
const optionValues = (sel: HTMLSelectElement) => Array.from(sel.options).map((o) => o.value);
const injectedCards = () =>
  Array.from(document.querySelectorAll('.stats-overview .a1-stat-card'));

/** 等统计请求的回调落地（fetch mock 是 async，两轮微任务足够） */
async function flush(): Promise<void> {
  for (let i = 0; i < 3; i += 1) await Promise.resolve();
}

describe('installAdminMaterialTypes', () => {
  let uninstall: (() => void) | null = null;

  beforeEach(() => {
    mountPage();
    window.location.hash = '#/admin/materials';
    (window as any).__VTJ_AUTH__ = { getUserRole: () => 'admin' };
  });

  afterEach(() => {
    uninstall?.();
    uninstall = null;
    document.head.innerHTML = '';
    document.body.innerHTML = '';
    delete (window as any).__VTJ_AUTH__;
  });

  it('类型下拉补出「讲义」「试卷」，且保留原有 4 项', () => {
    uninstall = installAdminMaterialTypes(window);
    const sel = typeSelect();
    expect(optionValues(sel)).toEqual([
      '',
      'video_intro',
      'video_advanced',
      'article',
      'card',
      'lecture',
      'paper'
    ]);
    const label = (v: string) =>
      Array.from(sel.options).find((o) => o.value === v)?.textContent?.trim();
    expect(label('lecture')).toBe('讲义');
    expect(label('paper')).toBe('试卷');
  });

  it('统计概览补出两格，数字来自 /admin/stats 的 by_type', async () => {
    uninstall = installAdminMaterialTypes(window);
    await flush();
    const cards = injectedCards();
    expect(cards.length).toBe(2);
    const byId = (id: string) => document.getElementById(id);
    expect(byId('a1-stat-lecture')?.querySelector('.a1-stat-label')?.textContent).toBe('讲义');
    expect(byId('a1-stat-paper')?.querySelector('.a1-stat-label')?.textContent).toBe('试卷');
    expect(byId('a1-stat-lecture')?.querySelector('.a1-stat-value')?.textContent).toBe('85');
    expect(byId('a1-stat-paper')?.querySelector('.a1-stat-value')?.textContent).toBe('3');
  });

  it('重复安装是单例：节点不翻倍，返回同一个 teardown', () => {
    uninstall = installAdminMaterialTypes(window);
    const again = installAdminMaterialTypes(window);
    expect(again).toBe(uninstall);
    expect(typeSelect().querySelectorAll('option[value="lecture"]').length).toBe(1);
    expect(typeSelect().querySelectorAll('option[value="paper"]').length).toBe(1);
    expect(injectedCards().length).toBe(2);
  });

  it('离开管理页后选项与统计卡被移除', () => {
    uninstall = installAdminMaterialTypes(window);
    expect(optionValues(typeSelect())).toContain('lecture');

    window.location.hash = '#/materials/xingce';
    window.dispatchEvent(new Event('hashchange'));

    expect(optionValues(typeSelect())).not.toContain('lecture');
    expect(optionValues(typeSelect())).not.toContain('paper');
    expect(injectedCards().length).toBe(0);
  });

  it('非管理员角色不注入', () => {
    (window as any).__VTJ_AUTH__ = { getUserRole: () => 'teacher' };
    uninstall = installAdminMaterialTypes(window);
    expect(optionValues(typeSelect())).not.toContain('lecture');
    expect(injectedCards().length).toBe(0);
  });

  it('卸载后恢复原样（样式 / 选项 / 统计卡都不留痕）', () => {
    uninstall = installAdminMaterialTypes(window);
    uninstall();
    uninstall = null;
    expect(document.getElementById('admin-material-types-style')).toBeNull();
    expect(optionValues(typeSelect())).toEqual([
      '',
      'video_intro',
      'video_advanced',
      'article',
      'card'
    ]);
    expect(injectedCards().length).toBe(0);
  });
});
