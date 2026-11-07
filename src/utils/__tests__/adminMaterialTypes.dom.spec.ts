// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * A1 注入的 DOM 级验证（jsdom）：直接对着「管理页真实结构的最小复刻」跑。
 *
 * 2026-11-07 改版：统计行从「追加 2 格」变成「整行换成 5 格」——
 *   总资料 ｜ 试卷 ｜ 文章/讲义 ｜ 卡片 ｜ 已上架/未上架
 * 因此这里断言：① 原来 4 格被隐藏；② 新 5 格齐全且双值形态正确；③ 离开页面能还原。
 */
vi.mock('@/modules/library/api', () => ({
  fetchAdminMaterialStats: vi.fn(async () => ({
    total: 119,
    by_type: { video_intro: 0, video_advanced: 0, article: 3, card: 116, lecture: 0, paper: 2 },
    by_subject: { xingce: 43, shenlun: 27, gongzhuan: 49 },
    by_status: { published: 103, draft: 11 }
  }))
}));

import { buildStatValues, installAdminMaterialTypes, STAT_SPECS } from '../adminMaterialTypes';

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
const injectedCards = () => Array.from(document.querySelectorAll('.stats-overview .a1-stat-card'));
/** 取某张卡的数值区（双值会连成 "103/11"） */
const statValue = (id: string) =>
  document
    .getElementById(`a1-stat-${id}`)
    ?.querySelector('.a1-stat-value')
    ?.textContent?.replace(/\s+/g, '');
const statLabel = (id: string) =>
  document.getElementById(`a1-stat-${id}`)?.querySelector('.a1-stat-label')?.textContent?.trim();

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
    expect(optionValues(typeSelect())).toEqual([
      '',
      'video_intro',
      'video_advanced',
      'article',
      'card',
      'lecture',
      'paper'
    ]);
  });

  it('统计行整行换成 5 格，顺序与规格一致', () => {
    uninstall = installAdminMaterialTypes(window);
    const cards = injectedCards();
    expect(cards.length).toBe(5);
    expect(cards.map((c) => c.id)).toEqual(STAT_SPECS.map((s) => `a1-stat-${s.id}`));
    expect(cards.map((c) => c.querySelector('.a1-stat-label')?.textContent)).toEqual([
      '总资料',
      '试卷',
      '文章/讲义',
      '卡片',
      '已上架/未上架'
    ]);
  });

  it('原来的 4 格被隐藏（容器加接管标记）', () => {
    uninstall = installAdminMaterialTypes(window);
    const box = document.querySelector('.stats-overview') as HTMLElement;
    expect(box.classList.contains('a1-stats-overridden')).toBe(true);
  });

  it('数值来自 /admin/stats：单值 + 双值 a/b 形态', async () => {
    uninstall = installAdminMaterialTypes(window);
    await flush();
    expect(statValue('total')).toBe('119');
    expect(statValue('paper')).toBe('2');
    expect(statValue('doc')).toBe('3/0'); // 文章 3 / 讲义 0
    expect(statValue('card')).toBe('116');
    expect(statValue('status')).toBe('103/11'); // 已上架 103 / 未上架 11
    expect(statLabel('doc')).toBe('文章/讲义');
    expect(statLabel('status')).toBe('已上架/未上架');
  });

  it('双值卡片右半有独立颜色类（未上架用 warn）', async () => {
    uninstall = installAdminMaterialTypes(window);
    await flush();
    const statusCard = document.getElementById('a1-stat-status') as HTMLElement;
    expect(statusCard.querySelector('.a1-stat-value2')?.classList.contains('is-tone-warn')).toBe(true);
    expect(statusCard.classList.contains('is-tone-ok')).toBe(true); // 左半=已上架，绿
    // 文章/讲义 右半不加语义色
    const docCard = document.getElementById('a1-stat-doc') as HTMLElement;
    expect(docCard.querySelector('.a1-stat-value2')?.className).toBe('a1-stat-value2');
  });

  it('重复安装是单例：节点不翻倍，返回同一个 teardown', () => {
    uninstall = installAdminMaterialTypes(window);
    const again = installAdminMaterialTypes(window);
    expect(again).toBe(uninstall);
    expect(typeSelect().querySelectorAll('option[value="lecture"]').length).toBe(1);
    expect(injectedCards().length).toBe(5);
  });

  it('离开管理页后选项、5 格与接管标记都还原', () => {
    uninstall = installAdminMaterialTypes(window);
    expect(optionValues(typeSelect())).toContain('lecture');

    window.location.hash = '#/materials/xingce';
    window.dispatchEvent(new Event('hashchange'));

    expect(optionValues(typeSelect())).not.toContain('lecture');
    expect(injectedCards().length).toBe(0);
    const box = document.querySelector('.stats-overview') as HTMLElement;
    expect(box.classList.contains('a1-stats-overridden')).toBe(false);
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

describe('buildStatValues（纯函数）', () => {
  it('把 /admin/stats 映射成 5 格，双值拆分正确', () => {
    const v = buildStatValues({
      total: 119,
      by_type: { article: 3, card: 116, lecture: 1, paper: 2 },
      by_status: { published: 103, draft: 11 }
    });
    expect(v.map((x) => x.id)).toEqual(['total', 'paper', 'doc', 'card', 'status']);
    expect(v.find((x) => x.id === 'doc')).toEqual({ id: 'doc', label: '文章/讲义', value: 3, value2: 1 });
    expect(v.find((x) => x.id === 'status')).toEqual({
      id: 'status',
      label: '已上架/未上架',
      value: 103,
      value2: 11
    });
  });

  it('缺字段一律给 0，不给 undefined（避免显示 — 让人以为接口挂了）', () => {
    const v = buildStatValues(null);
    expect(v.every((x) => typeof x.value === 'number')).toBe(true);
    expect(v.find((x) => x.id === 'status')?.value2).toBe(0);
  });
});
