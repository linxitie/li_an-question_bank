/**
 * 表单可访问性兜底（2026-11-16）。
 *
 * 背景：Chrome DevTools → Issues 会报
 *   "A form field element should have an id or name attribute"
 * 而不少页面是 VTJ 低代码页（.vtj/vue/*.vue），按 R3 不能由 AI 改 <template>。
 * 因此沿用项目已有的「DOM 注入器」模式（materialsCreateEntry / tabletMaterialsEntry）：
 * 运行时给没有 id/name 的 input/select/textarea 补上稳定唯一标识，既满足 DevTools 告警，
 * 也让浏览器的自动填充、读屏与自动化测试能稳定定位字段。
 *
 * 只在「缺属性」时补，已写死的 id/name 一律不动；用 MutationObserver 覆盖路由切换与弹窗动态渲染。
 */

const FIELD_SELECTOR = 'input:not([type="hidden"]), select, textarea';
let seq = 0;

function slugOf(el: HTMLElement): string {
  const hint =
    el.getAttribute('placeholder') ||
    el.getAttribute('aria-label') ||
    el.className ||
    el.getAttribute('type') ||
    el.tagName.toLowerCase();
  const base = String(hint)
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24);
  return base || el.tagName.toLowerCase();
}

/** 给 root 下所有缺 id / name 的表单元素补齐；返回补了几项 */
export function labelUnnamedFields(root: ParentNode = document): number {
  if (!root || typeof (root as ParentNode).querySelectorAll !== 'function') return 0;
  let changed = 0;
  const fields = Array.from(root.querySelectorAll<HTMLElement>(FIELD_SELECTOR));
  for (const el of fields) {
    const input = el as HTMLInputElement;
    const hasId = Boolean(input.id);
    const hasName = Boolean(el.getAttribute('name'));
    if (hasId && hasName) continue;
    if (!hasId) {
      let id = '';
      do {
        id = 'f-' + slugOf(el) + '-' + ++seq;
      } while (document.getElementById(id));
      input.id = id;
      changed += 1;
    }
    if (!hasName) el.setAttribute('name', input.id || 'f-field-' + ++seq);
  }
  return changed;
}

/** 安装：立即补一次 + 监听后续路由/弹窗插入的字段（防抖 120ms） */
export function installA11yFormFields(): void {
  if (typeof document === 'undefined' || typeof MutationObserver === 'undefined') return;
  labelUnnamedFields();
  let timer: ReturnType<typeof setTimeout> | null = null;
  const observer = new MutationObserver(() => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      labelUnnamedFields();
    }, 120);
  });
  observer.observe(document.body, { childList: true, subtree: true });
}
