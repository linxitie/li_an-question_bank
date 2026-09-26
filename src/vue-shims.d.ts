/**
 * `.vue` 模块的环境声明。
 *
 * 必须独立于 `src/env.d.ts`：后者含 `export {}`，属于模块文件，
 * 其中的 `declare module '*.vue'` 会被 TypeScript 视为「模块增强」
 * 而非「环境声明」，从而对 `@/views/*.vue` 等路径不生效（TS7016）。
 * 本文件不含任何顶层 import/export，因此是全局脚本，声明可正确生效。
 */

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, any>;
  export default component;
}
