/**
 * 同步引擎模块 — Vue ↔ DSL 同步与一致性检查
 *
 * 职责：
 *   1. syncVueToDSL：将 Vue 文件中的 methods/state/lifeCycles 同步到 DSL JSON
 *   2. checkConsistency：检查 Vue 与 DSL 的一致性（版本号、方法签名等）
 */

import {
  readText, readJSON, writeJSON, existsFile,
  getVuePath, getDslPath, getDslFileMap, getProjectConfig, isRawPage
} from './file-system.js';
import { parseVueSFC } from './parser.js';
import { createSuccessResponse, createErrorResponse } from '../utils/logger.js';

// ── 提取函数 ──────────────────────────────────────────────

/**
 * 从 Vue SFC 的 script 中提取 methods 签名信息
 */
function extractMethodsFromScript(scriptContent) {
  const methods = {};
  const methodsBlock = scriptContent.match(/methods\s*:\s*\{([\s\S]*?)\n\s*\}/);
  if (methodsBlock) {
    const methodRegex = /(\w+)\s*\(([^)]*)\)\s*\{/g;
    let match;
    while ((match = methodRegex.exec(methodsBlock[1])) !== null) {
      const name = match[1];
      const params = match[2].split(',').map(p => p.trim()).filter(Boolean);
      const isAsync = methodsBlock[1].substring(
        Math.max(0, match.index - 20), match.index
      ).includes('async');
      methods[name] = {
        type: isAsync ? 'asyncMethod' : 'method',
        params: params
      };
    }
  }
  return methods;
}

/**
 * 从 Vue SFC 的 setup() 中提取 state 初始化信息
 */
function extractStateFromScript(scriptContent) {
  const state = {};
  const reactiveMatch = scriptContent.match(/reactive\s*\(\s*\{([\s\S]*?)\}\s*\)/);
  if (reactiveMatch) {
    const stateBlock = reactiveMatch[1];
    const propRegex = /(\w+)\s*:\s*(.+?)(?:,|\n|$)/g;
    let match;
    while ((match = propRegex.exec(stateBlock)) !== null) {
      const key = match[1];
      const value = match[2].trim().replace(/,$/, '');
      state[key] = value;
    }
  }
  return state;
}

/**
 * 从 Vue SFC 的 script 中提取 lifeCycles
 */
function extractLifeCyclesFromScript(scriptContent) {
  const lifeCycles = {};
  const hookNames = ['mounted', 'beforeMount', 'updated', 'beforeUnmount', 'unmounted', 'created', 'beforeCreate', 'activated', 'deactivated'];
  for (const hook of hookNames) {
    if (new RegExp(`${hook}\\s*\\(`).test(scriptContent)) {
      lifeCycles[hook] = { type: 'method' };
    }
  }
  return lifeCycles;
}

/**
 * 从 Vue SFC 中提取 useProvider 的 version
 */
function extractVersionFromScript(scriptContent) {
  const match = scriptContent.match(/useProvider\s*\(\s*\{[^}]*version\s*:\s*['"](\d+)['"]/);
  return match ? match[1] : null;
}

/**
 * 构建 DSL methods 声明（精简版，仅签名）
 */
function buildDslMethods(scriptContent) {
  const methods = extractMethodsFromScript(scriptContent);
  const methodNames = Object.keys(methods);

  const setupFnRegex = /(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)/g;
  let match;
  while ((match = setupFnRegex.exec(scriptContent)) !== null) {
    const name = match[1];
    if (!methodNames.includes(name) && !name.startsWith('_')) {
      const params = match[2].split(',').map(p => p.trim()).filter(Boolean);
      const isAsync = scriptContent.substring(
        Math.max(0, match.index - 30), match.index
      ).includes('async');
      methods[name] = {
        type: isAsync ? 'asyncMethod' : 'method',
        params: params
      };
    }
  }

  return methods;
}

// ── 公共 API ──────────────────────────────────────────────

/**
 * 同步 Vue 文件到 DSL JSON
 *
 * @param {string} id 页面或区块 ID
 * @param {object} [options] 选项
 * @param {boolean} [options.dryRun=false] 仅预览不实际写入
 * @returns {Promise<object>} 同步结果
 */
export async function syncVueToDSL(id, options = {}) {
  const { dryRun = false } = options;

  // raw 手写页面受保护：DSL 同步有损，禁止执行
  if (isRawPage(id)) {
    return createErrorResponse(
      'RAW_PAGE_PROTECTED',
      `页面 ${id} 为 raw 手写页面，禁止同步 DSL。同步会丢失提取不到的手写方法，` +
      `且设计器回存时会将丢失部分覆盖到手写代码上。如需调整 UI 请在 VTJ 设计器中拖拽操作。`
    );
  }

  const vuePath = getVuePath(id);
  const dslPath = getDslPath(id);

  if (!existsFile(vuePath)) {
    return createErrorResponse('VUE_FILE_NOT_FOUND', `Vue 文件不存在: .vtj/vue/${id}.vue`);
  }

  if (!existsFile(dslPath)) {
    return createErrorResponse('DSL_FILE_NOT_FOUND', `DSL 文件不存在: .vtj/files/${id}.json`);
  }

  const vueContent = readText(vuePath);
  const dsl = readJSON(dslPath);

  if (!vueContent || !dsl) {
    return createErrorResponse('FILE_READ_ERROR', '无法读取文件');
  }

  const parsed = parseVueSFC(vueContent);
  const scriptContent = parsed.script || parsed.scriptSetup;

  // 提取信息
  const vueVersion = extractVersionFromScript(scriptContent);
  const dslVersion = dsl.__VERSION__;
  const syncedMethods = buildDslMethods(scriptContent);
  const syncedState = extractStateFromScript(scriptContent);
  const syncedLifeCycles = extractLifeCyclesFromScript(scriptContent);

  const changes = [];

  // 检查版本
  if (vueVersion && vueVersion !== dslVersion) {
    changes.push({
      field: '__VERSION__',
      from: dslVersion,
      to: vueVersion,
      type: 'version'
    });
  }

  // 检查 methods
  const existingMethodNames = dsl.methods ? Object.keys(dsl.methods) : [];
  const newMethodNames = Object.keys(syncedMethods);
  for (const name of newMethodNames) {
    if (!existingMethodNames.includes(name)) {
      changes.push({ field: `methods.${name}`, from: null, to: syncedMethods[name], type: 'method_add' });
    }
  }

  // 检查 state
  if (dsl.state) {
    const existingStateKeys = Object.keys(dsl.state);
    const newStateKeys = Object.keys(syncedState);
    for (const key of newStateKeys) {
      if (!existingStateKeys.includes(key)) {
        changes.push({ field: `state.${key}`, from: null, to: syncedState[key], type: 'state_add' });
      }
    }
  }

  // 检查 lifeCycles
  if (dsl.lifeCycles) {
    const existingHookNames = Object.keys(dsl.lifeCycles);
    const newHookNames = Object.keys(syncedLifeCycles);
    for (const name of newHookNames) {
      if (!existingHookNames.includes(name)) {
        changes.push({ field: `lifeCycles.${name}`, from: null, to: syncedLifeCycles[name], type: 'lifeCycle_add' });
      }
    }
  }

  if (dryRun) {
    return {
      dryRun: true,
      id,
      vueVersion,
      dslVersion,
      versionMatch: vueVersion === dslVersion,
      changes,
      changesCount: changes.length,
      wouldUpdate: changes.length > 0,
      methods: syncedMethods
    };
  }

  // 实际写入
  if (vueVersion) dsl.__VERSION__ = vueVersion;
  dsl.methods = { ...(dsl.methods || {}), ...syncedMethods };
  if (Object.keys(syncedState).length > 0) {
    dsl.state = { ...(dsl.state || {}), ...syncedState };
  }
  if (Object.keys(syncedLifeCycles).length > 0) {
    dsl.lifeCycles = { ...(dsl.lifeCycles || {}), ...syncedLifeCycles };
  }

  // 备份
  const bakPath = dslPath + '.bak';
  writeJSON(bakPath, readJSON(dslPath));

  const success = writeJSON(dslPath, dsl);
  if (!success) {
    return createErrorResponse('FILE_WRITE_ERROR', '写入 DSL 失败');
  }

  return createSuccessResponse({
    id,
    changes,
    changesCount: changes.length,
    message: changes.length > 0
      ? `已同步 ${changes.length} 项变更到 .vtj/files/${id}.json`
      : '无需同步，Vue 和 DSL 一致',
    methods: syncedMethods
  });
}

/**
 * 检查 Vue 与 DSL 的一致性
 *
 * @param {string} [id] 页面或区块 ID，不提供则检查所有文件
 * @returns {Promise<object>} 一致性检查结果（直接返回，不包装）
 */
export async function checkConsistency(id) {
  const results = [];

  if (id) {
    results.push(checkPageConsistency(id));
  } else {
    const dslMap = getDslFileMap();
    for (const pageId of Object.keys(dslMap)) {
      results.push(checkPageConsistency(pageId));
    }
  }

  const consistent = results.filter(r => r.status === 'consistent').length;
  const inconsistent = results.filter(r => r.status === 'inconsistent').length;
  const missing = results.filter(r => r.status === 'missing_file').length;

  return {
    checked: results.length,
    consistent,
    inconsistent,
    missingFiles: missing,
    results
  };
}

/**
 * 检查单个页面的一致性
 */
function checkPageConsistency(pageId) {
  const vuePath = getVuePath(pageId);
  const dslPath = getDslPath(pageId);

  const hasVue = existsFile(vuePath);
  const hasDsl = existsFile(dslPath);

  if (!hasVue || !hasDsl) {
    return { id: pageId, status: 'missing_file', hasVue, hasDsl };
  }

  const vueContent = readText(vuePath);
  const dsl = readJSON(dslPath);

  if (!vueContent || !dsl) {
    return { id: pageId, status: 'read_error' };
  }

  const parsed = parseVueSFC(vueContent);
  const scriptContent = parsed.script || parsed.scriptSetup;
  const vueVersion = extractVersionFromScript(scriptContent);
  const dslVersion = dsl.__VERSION__;
  const versionMatch = vueVersion === dslVersion;

  const vueMethods = Object.keys(buildDslMethods(scriptContent));
  const dslMethods = dsl.methods ? Object.keys(dsl.methods) : [];
  const missingInDsl = vueMethods.filter(m => !dslMethods.includes(m));
  const extraInDsl = dslMethods.filter(m => !vueMethods.includes(m));

  const issues = [];
  if (!versionMatch) issues.push('version_mismatch');
  if (missingInDsl.length > 0) issues.push('methods_missing_in_dsl');
  if (extraInDsl.length > 0) issues.push('methods_extra_in_dsl');

  return {
    id: pageId,
    name: dsl.name || pageId,
    status: issues.length === 0 ? 'consistent' : 'inconsistent',
    vueVersion,
    dslVersion,
    versionMatch,
    issues,
    missingInDsl,
    extraInDsl
  };
}
