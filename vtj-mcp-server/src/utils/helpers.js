/**
 * 通用辅助函数模块：dryRun 预览、下一步建议、路由推断
 */

import { isRawPage } from '../core/file-system.js';

/**
 * 创建 dryRun 预览对象
 * @param {object} options 预览选项
 * @param {string} options.operation 操作名称
 * @param {string} options.target 目标文件或页面
 * @param {object} [options.changes] 变更内容
 * @param {string} [options.backup] 备份文件路径
 * @param {string[]} [options.warnings] 警告列表
 * @param {string[]} [options.nextSteps] 后续步骤建议
 * @returns {object} 结构化 dryRun 预览对象
 */
export function createDryRunPreview({ operation, target, changes, backup, warnings, nextSteps }) {
  const preview = {
    dryRun: true,
    operation,
    target
  };
  if (changes !== undefined) preview.changes = changes;
  if (backup !== undefined) preview.backup = backup;
  if (warnings !== undefined) preview.warnings = warnings;
  if (nextSteps !== undefined) preview.nextSteps = nextSteps;
  return preview;
}

/**
 * 改完 .vue 的 <script> 之后，给出正确的后续同步建议。
 *
 * raw 手写页面禁止同步 DSL —— 同步有损，会丢失提取不到的手写方法，
 * 且设计器回存会把丢失的部分覆盖到手写代码上。详见 file-system.js 的 isRawPage()。
 *
 * @param {string} id 页面或区块 ID
 * @returns {string} 面向调用方的建议文本
 */
export function syncAdvice(id) {
  if (isRawPage(id)) {
    return (
      `页面 ${id} 为 raw 手写页面，禁止运行 vtj_sync_vue_to_dsl：` +
      `同步会丢失提取不到的手写方法，且设计器回存时会覆盖手写代码。` +
      `<template> 的 UI 调整请在 VTJ 设计器中拖拽完成。`
    );
  }
  return (
    `页面 ${id} 可同步：运行 vtj_sync_vue_to_dsl 同步到 DSL，` +
    `再用 vtj_check_consistency 验证一致性（建议先加 dryRun 预览）。`
  );
}

/**
 * 根据操作类型返回后续步骤建议
 * @param {string} operation 操作名称
 * @param {string} target 目标文件或页面
 * @returns {string[]} 后续步骤建议列表
 */
export function getNextSteps(operation, target) {
  switch (operation) {
    case 'write_vue_script':
      return [syncAdvice(target), '检查同步结果并验证一致性'];
    case 'sync_vue_to_dsl':
      return [`运行 vtj_check_consistency 检查 ${target} 的 Vue 与 DSL 一致性`, '清理 Vite 缓存并刷新页面'];
    case 'create_page_scaffold':
      return [`运行 vtj_add_route 为 ${target} 添加路由`, '在 VTJ 设计器中拖拽 UI'];
    case 'add_route':
      return [`运行 vtj_get_routing_info 验证路由 ${target} 已生效`];
    default:
      return [`检查 ${target} 的变更结果`, '运行 vtj_check_consistency 验证一致性'];
  }
}

/**
 * 从 Vue 文件内容中推断路由路径
 * @param {string} vueContent Vue 文件内容
 * @returns {string[]} 路由路径列表，未找到路由信息时返回空数组
 */
export function inferRoutes(vueContent) {
  if (!vueContent || typeof vueContent !== 'string') {
    return [];
  }
  const routes = [];
  // 匹配路由定义，如 path: '/xxx' 或 path: "/xxx"
  const pathPattern = /path\s*:\s*['"]([^'"]+)['"]/g;
  let match;
  while ((match = pathPattern.exec(vueContent)) !== null) {
    routes.push(match[1]);
  }
  return routes;
}