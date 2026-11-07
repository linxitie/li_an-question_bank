/**
 * 管理员端组件库（A0 · 2026-11-07）
 *
 * 6 个基础组件，配合 `src/styles/admin-tokens.css` 的令牌与 `.adm-btn/.adm-input`
 * 等工具类，构成管理端统一画风的地基。
 *
 * 引入方式：
 *   import { AdminStatCard, AdminTable } from '@/components/admin';
 *
 * 说明：这里顺带 import 一次令牌 CSS，保证任何用到组件的地方变量都在
 * （`main.ts` 也会全局引一次，重复 import 由打包器去重）。
 */
import '@/styles/admin-tokens.css';

export { default as AdminStatCard } from './AdminStatCard.vue';
export { default as AdminPageHeader } from './AdminPageHeader.vue';
export { default as AdminToolbar } from './AdminToolbar.vue';
export { default as AdminTable } from './AdminTable.vue';
export { default as AdminTag } from './AdminTag.vue';
export { default as AdminFormItem } from './AdminFormItem.vue';
