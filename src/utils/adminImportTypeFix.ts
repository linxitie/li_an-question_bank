/**
 * 旧版资料管理页「导入向导」：把文档类入库类型从「作为文章」纠正为「作为讲义」
 * （DOM 注入，遵守 R3：不改 `.vtj` 页面模板）
 *
 * 背景（资料管理 v3.1 · B3，2026-11-07）
 *  P1 缺陷的**前端一半**：`/admin/materials/legacy` 的导入向导里，
 *  文档类（docx/pdf）唯一的类型选项是 `<option value="article">作为文章</option>`，
 *  `state.imp.type` 默认就是 `article`；后端又在入库时用分类器结果覆盖了它，
 *  于是「短文档」被判成 `card` → 讲义落进卡片区（实测 material 121/122）。
 *
 *  后端已修（显式 type 优先 + 文档默认 lecture + 重复拦截），本文件负责让管理员
 *  **在界面上就能选到「讲义」并默认选中它**，否则后端永远只能收到 `article`。
 *
 * 生命周期：B2 会用新页的批量导入重建这个向导，届时本文件与 `main.ts` 的安装行一起删除。
 *
 * 约束（与 `adminMaterialTypes.ts` 同一套路）
 *  · 只在 `#/admin/materials/legacy` + admin 角色下注入；离开页面自动还原、解除定时器；
 *  · 幂等：选项带 `data-b3-type-opt` 标记，重复调用不插第二份；
 *  · 只强制一次：每个 `.meta-form` 元素（= 一次解析结果）只把默认值从 article 改成 lecture，
 *    改完打 `data-b3-forced`，之后管理员手选「作为文章」不会被反复覆盖；
 *  · 触发方式必须是原生 `change` 事件，Vue 的 `v-model` 才会回写 `state.imp.type`。
 */

/** 导入向导所在路由（旧版页；新页是 `#/admin/materials`，B2 会接手） */
const LEGACY_HASH = '#/admin/materials/legacy';
/** 注入的选项：值必须与后端 type 白名单一致 */
export const LECTURE_OPTION = { value: 'lecture', label: '作为讲义' } as const;
const OPT_MARK = 'data-b3-type-opt';
const FORCED_MARK = 'data-b3-forced';
/** 向导里类型下拉的定位：包含「作为文章」选项的那个 select */
const TEXT_TYPE_SELECTOR = '.meta-form select';

export interface ImportTypeFixInput {
  hash: string;
  role: string;
}

/** 是否应注入（纯函数，便于单测） */
export function shouldInjectImportTypeFix({ hash, role }: ImportTypeFixInput): boolean {
  if (role !== 'admin') return false;
  const h = hash || '';
  return h === LEGACY_HASH || h.startsWith(LEGACY_HASH + '?') || h.startsWith(LEGACY_HASH + '/');
}

/** 找到向导里的「文档类型」下拉（它一定含有 value=article 的「作为文章」） */
export function findTypeSelect(doc: Document): HTMLSelectElement | null {
  const selects = Array.from(doc.querySelectorAll<HTMLSelectElement>(TEXT_TYPE_SELECTOR));
  // 只认带 article 选项的那个下拉：xlsx 卡片流这个 select 根本不会渲染（v-if），
  // 如果退化成"含 card 就算"，会把卡片导入的类型也改成讲义。
  return selects.find((s) => Array.from(s.options).some((o) => o.value === 'article')) || null;
}

/** 幂等补入「作为讲义」选项，返回是否新插入 */
export function injectLectureOption(doc: Document, select: HTMLSelectElement): boolean {
  if (Array.from(select.options).some((o) => o.value === LECTURE_OPTION.value)) return false;
  const opt = doc.createElement('option');
  opt.value = LECTURE_OPTION.value;
  opt.textContent = LECTURE_OPTION.label;
  opt.setAttribute(OPT_MARK, '1');
  select.appendChild(opt);
  return true;
}

/**
 * 把默认值从 `article` 改成 `lecture`（每次解析结果只做一次）。
 * 返回是否真的改了 —— 已强制过 / 管理员已经选了别的 / 该下拉是 xlsx 卡片流（无 article）都返回 false。
 */
export function forceLectureOnce(select: HTMLSelectElement): boolean {
  if (select.getAttribute(FORCED_MARK) === '1') return false;
  if (select.value !== 'article') return false;   // 管理员已改过，尊重他的选择
  select.value = LECTURE_OPTION.value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  select.setAttribute(FORCED_MARK, '1');
  return true;
}

/** 一次注入扫描：补选项 + 纠默认值。返回本次是否改动了 DOM/状态 */
export function applyImportTypeFix(doc: Document): { injected: boolean; forced: boolean } {
  const select = findTypeSelect(doc);
  if (!select) return { injected: false, forced: false };
  const injected = injectLectureOption(doc, select);
  const forced = forceLectureOnce(select);
  return { injected, forced };
}

/**
 * 旧页的类型徽标把新类型直接打出了英文 key（`{{ TYPE_LABEL[row.type] || row.type }}`，
 * 而 `TYPE_LABEL` 里只有 4 种旧类型）→ 讲义行会显示 `lecture`。
 * 这里把 `.type-tag` 里恰好等于 key 的文本换成中文；Vue 重新渲染后由 1s 轮询补回。
 * 只动文本完全等于 key 的节点，不会误伤标题里的同名单词。
 */
const TYPE_LABEL_CN: Record<string, string> = {
  lecture: '讲义',
  paper: '试卷',
  video_intro: '入门视频',
  video_advanced: '进阶视频',
  article: '文章',
  card: '知识卡片'
};

export function localizeTypeTags(doc: Document): number {
  let changed = 0;
  doc.querySelectorAll<HTMLElement>('.type-tag, .badge-type, .type-badge').forEach((el) => {
    const key = (el.textContent || '').trim();
    const cn = TYPE_LABEL_CN[key];
    if (cn && cn !== key) {
      el.textContent = cn;
      changed += 1;
    }
  });
  return changed;
}

/**
 * 读当前登录角色。
 * 首选 `window.__VTJ_AUTH__.getUserRole()`（与 `adminMaterialTypes.ts` 同一来源，
 * 会解 JWT；localStorage 里的 state 常常只有 token/username，**没有 role**——
 * 一开始只读 localStorage 导致注入判定永远是"非管理员"，注入从未生效）。
 * localStorage 只作为兜底。
 */
export function resolveRole(win: Window): string {
  const auth = (win as unknown as { __VTJ_AUTH__?: { getUserRole?: () => unknown } }).__VTJ_AUTH__;
  try {
    if (auth && typeof auth.getUserRole === 'function') {
      const r = String(auth.getUserRole() || '');
      if (r) return r;
    }
  } catch {
    /* 认证模块异常不应影响注入判定 */
  }
  try {
    const raw = win.localStorage.getItem('__VTJ_AUTH_STATE__');
    if (!raw) return '';
    const st = JSON.parse(raw) as { role?: string; userInfo?: { role?: string } };
    return st.role || st.userInfo?.role || '';
  } catch {
    return '';
  }
}

/**
 * 安装注入器：1s 轮询 + hashchange 兜底（页面被 Vue 重新 patch 掉注入节点时能补回）。
 * 返回卸载函数（离开页面 / 单测清理时调用）。
 */
export function installAdminImportTypeFix(win: Window = window): () => void {
  let timer: ReturnType<typeof setInterval> | null = null;

  const tick = (): void => {
    if (!shouldInjectImportTypeFix({ hash: win.location.hash, role: resolveRole(win) })) return;
    try {
      // 旧页徽标把 lecture/paper 打成英文 key，顺手换成中文（页面重渲染后由轮询补回）。
      // 两件事互不依赖，必须都跑：不能因为改了徽标就跳过下拉修正。
      localizeTypeTags(win.document);
      applyImportTypeFix(win.document);
    } catch {
      /* 旧页 DOM 结构变动不应影响页面本身 */
    }
  };

  timer = setInterval(tick, 1000);
  win.addEventListener('hashchange', tick);
  tick();

  return () => {
    if (timer) clearInterval(timer);
    timer = null;
    win.removeEventListener('hashchange', tick);
    // 还原：移除注入的选项与标记，避免离开页面后仍残留
    try {
      win.document.querySelectorAll(`option[${OPT_MARK}]`).forEach((o) => o.remove());
      win.document.querySelectorAll(`[${FORCED_MARK}]`).forEach((el) => el.removeAttribute(FORCED_MARK));
    } catch {
      /* 忽略 */
    }
  };
}
