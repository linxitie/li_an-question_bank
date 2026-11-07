/**
 * 管理端「备考资料管理」页：类型下拉补「讲义 / 试卷」+ 统计卡补两格
 * （DOM 注入，遵守 R3：不修改 `.vtj` 页面模板）
 *
 * 背景（资料管理 v3.1 · A1 / 裁定 D29）
 *  `/admin/materials` 现在仍渲染 `.vtj/vue/admin_materials.vue`（VTJ 低代码页）。
 *  R3 规定不得直接改其 `<template>`，而本轮 A1 就要让两个新类型可见可用：
 *   ① 类型下拉只有 入门视频/进阶视频/文章/知识卡片 4 项 → 追加「讲义」「试卷」；
 *   ② 统计概览只有 总/视频/文档/卡片 4 格 → 追加「讲义」「试卷」两格，数字走
 *      `GET /api/materials/admin/stats`（后端已返回 6 个类型键）。
 *
 * 生命周期：A4 会用新建的手写页 `src/views/admin/materials.vue` 替换路由，
 *  届时本文件连同 `main.ts` 里的一行安装调用**一起删除**即可（6 类由手写页直接渲染）。
 *
 * 约束（与 materialsCreateEntry / tabletMaterialsEntry 同一套路）
 *  · 只在 `#/admin/materials` + admin 角色下注入；离开页面自动移除；
 *  · 幂等：元素带 id / data 标记，重复调用不插第二份；
 *  · 页面被 Vue 重新 patch 掉注入节点时，由 1s 定时 + hashchange 兜底补回；
 *  · 页面样式是 `scoped`，注入节点拿不到 `.stat-card` 规则 → 自带样式，不依赖页面 CSS。
 */
import { fetchAdminMaterialStats } from '@/modules/library/api';
import { MATERIAL_TYPES, type MaterialTypeMeta } from '@/modules/library/materialTypes';

/** A1 追加的两种类型（保持与后端 TYPES 一致） */
const NEW_TYPE_KEYS = ['lecture', 'paper'] as const;

const STYLE_ID = 'admin-material-types-style';
const OPTION_MARK = 'data-a1-type';
const statCardId = (key: string) => `a1-stat-${key}`;

/** 管理页路由（hash 路由，允许带查询参数） */
const PAGE_HASH = '#/admin/materials';

export interface AdminMaterialTypesInput {
  hash: string;
  role: string;
}

/** 是否应注入（纯函数，便于单测） */
export function shouldInjectAdminMaterialTypes({ hash, role }: AdminMaterialTypesInput): boolean {
  if (role !== 'admin') return false;
  const h = hash || '';
  return h === PAGE_HASH || h.startsWith(PAGE_HASH + '?') || h.startsWith(PAGE_HASH + '/');
}

/** 需要补进下拉的类型元数据（按 MATERIAL_TYPES 顺序，保证与手写页一致） */
export function injectedMaterialTypes(): MaterialTypeMeta[] {
  return MATERIAL_TYPES.filter((t) => (NEW_TYPE_KEYS as readonly string[]).includes(t.key));
}

const STYLE = `
.a1-stat-card {
  flex: 1;
  min-width: 0;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(10, 22, 40, 0.08);
}
.a1-stat-card .a1-stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}
.a1-stat-card .a1-stat-label {
  font-size: 13px;
  color: #8899aa;
}
.a1-stat-card.is-lecture .a1-stat-value { color: #0f7a86; }
.a1-stat-card.is-paper .a1-stat-value { color: #b35309; }
`;

/** 单例句柄：同一 window 只保留一套注入（HMR / 重复 onReady 不会叠加定时器与节点） */
let installed: { win: Window; teardown: () => void } | null = null;

export function installAdminMaterialTypes(win: Window = window): () => void {
  if (installed && installed.win === win) return installed.teardown;

  const doc = win.document;
  const auth = () => (win as any).__VTJ_AUTH__;
  // 统计请求节流：1s 兜底 sync 会反复走到这里，必须限频，否则后端挂掉时会变成每秒一次请求
  let statsInFlight = false;
  let lastStatsAttempt = 0;
  const STATS_RETRY_MS = 15000;

  const ensureStyle = () => {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = STYLE;
    doc.head.appendChild(style);
  };

  /** 类型下拉：找「全部类型」那个 select（限定在筛选条 `.ops` 内，避免误伤弹层里的下拉） */
  const findTypeSelect = (): HTMLSelectElement | null => {
    const scopes = ['.ops', '.bar', '.adm-page'];
    for (const scope of scopes) {
      const root = doc.querySelector(scope);
      if (!root) continue;
      const select = Array.from(root.querySelectorAll('select')).find((s) =>
        Array.from(s.options).some((o) => (o.textContent || '').trim() === '全部类型')
      );
      if (select) return select as HTMLSelectElement;
    }
    return null;
  };

  const syncOptions = () => {
    const select = findTypeSelect();
    if (!select) return;
    for (const meta of injectedMaterialTypes()) {
      if (select.querySelector(`option[value="${meta.key}"]`)) continue;
      const option = doc.createElement('option');
      option.value = meta.key;
      option.textContent = meta.label;
      option.setAttribute(OPTION_MARK, '1');
      select.appendChild(option);
    }
  };

  const clearOptions = () => {
    doc.querySelectorAll(`option[${OPTION_MARK}]`).forEach((o) => o.remove());
  };

  const writeStat = (key: string, value: number | string) => {
    const card = doc.getElementById(statCardId(key));
    const box = card?.querySelector('.a1-stat-value');
    if (box) box.textContent = String(value);
  };

  const loadStats = async (): Promise<void> => {
    if (statsInFlight) return;
    const now = Date.now();
    if (now - lastStatsAttempt < STATS_RETRY_MS) return;
    lastStatsAttempt = now;
    statsInFlight = true;
    try {
      const stats = await fetchAdminMaterialStats();
      for (const meta of injectedMaterialTypes()) {
        writeStat(meta.key, stats?.by_type?.[meta.key] ?? 0);
      }
    } catch {
      // 后端未启动 / token 过期：保留 "—"，15s 后或下次进页面再试，不打断页面
    } finally {
      statsInFlight = false;
    }
  };

  const syncStats = () => {
    const box = doc.querySelector('.stats-overview');
    if (!box) return;
    for (const meta of injectedMaterialTypes()) {
      if (doc.getElementById(statCardId(meta.key))) continue;
      const card = doc.createElement('div');
      card.id = statCardId(meta.key);
      card.className = `a1-stat-card is-${meta.key}`;
      card.innerHTML =
        '<div class="a1-stat-value">—</div><div class="a1-stat-label"></div>';
      const label = card.querySelector('.a1-stat-label');
      if (label) label.textContent = meta.label;
      box.appendChild(card);
    }
    void loadStats();   // 自带 15s 节流：1s 兜底 sync 不会变成请求风暴
  };

  const clearStats = () => {
    for (const meta of injectedMaterialTypes()) doc.getElementById(statCardId(meta.key))?.remove();
  };

  const visible = (): boolean => {
    const a = auth();
    const role = typeof a?.getUserRole === 'function' ? String(a.getUserRole() || '') : '';
    return shouldInjectAdminMaterialTypes({ hash: win.location.hash, role });
  };

  const sync = () => {
    if (!visible()) {
      clearOptions();
      clearStats();
      return;
    }
    ensureStyle();
    syncOptions();
    syncStats();
  };

  sync();
  win.addEventListener('hashchange', sync);
  win.addEventListener('storage', sync);
  // 页面 patch 会移除注入节点 → 1s 兜底补回（与既有两处入口同一取舍）
  const repaint = win.setInterval(sync, 1000);
  // 统计数字：仅当停留在本页且标签可见时每 20s 刷一次
  const refresh = win.setInterval(() => {
    if (doc.visibilityState === 'hidden') return;
    if (!visible()) return;
    void loadStats();
  }, 20000);

  const teardown = () => {
    win.removeEventListener('hashchange', sync);
    win.removeEventListener('storage', sync);
    win.clearInterval(repaint);
    win.clearInterval(refresh);
    clearOptions();
    clearStats();
    doc.getElementById(STYLE_ID)?.remove();
    if (installed?.win === win) installed = null;
  };
  installed = { win, teardown };
  return teardown;
}
