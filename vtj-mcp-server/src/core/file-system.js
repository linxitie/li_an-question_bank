/**
 * 文件系统模块 — 从 vtj-mcp-server.js 提取的通用文件操作函数
 *
 * 职责：
 *   1. 安全读写 JSON / 文本文件
 *   2. 文件存在性检查与备份
 *   3. 读取 VTJ 项目配置、物料配置、DSL 文件映射
 *
 * 通过 configure(rootDir) 设置项目根目录，替代原硬编码的 PROJECT_ROOT。
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'fs';
import { basename, join } from 'path';

// ── 路径常量（由 configure() 初始化）──────────────────────
let VTJ_DIR = '';
let VTJ_FILES_DIR = '';
let VTJ_VUE_DIR = '';
let VTJ_PROJECTS_DIR = '';
let VTJ_MATERIALS_DIR = '';
let VTJ_ROUTER_FILE = '';
let SRC_ROUTER_FILE = '';

/**
 * 设置项目根目录，初始化所有路径常量。
 *
 * @param {string} rootDir 项目根目录
 */
export function configure(rootDir) {
  VTJ_DIR = join(rootDir, '.vtj');
  VTJ_FILES_DIR = join(VTJ_DIR, 'files');
  VTJ_VUE_DIR = join(VTJ_DIR, 'vue');
  VTJ_PROJECTS_DIR = join(VTJ_DIR, 'projects');
  VTJ_MATERIALS_DIR = join(VTJ_DIR, 'materials');
  VTJ_ROUTER_FILE = join(VTJ_DIR, 'router.js');
  SRC_ROUTER_FILE = join(rootDir, 'src', 'router', 'index.ts');
}

/** 安全读取 JSON 文件 */
export function readJSON(filePath) {
  try {
    const content = readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (e) {
    return null;
  }
}

/** 安全写入 JSON 文件 */
export function writeJSON(filePath, data) {
  try {
    writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    return true;
  } catch (e) {
    return false;
  }
}

/** 读取文本文件 */
export function readText(filePath) {
  try {
    return readFileSync(filePath, 'utf-8');
  } catch (e) {
    return null;
  }
}

/** 写入文本文件 */
export function writeText(filePath, content) {
  try {
    writeFileSync(filePath, content, 'utf-8');
    return true;
  } catch (e) {
    return false;
  }
}

/** 检查文件是否存在 */
export function existsFile(filePath) {
  return existsSync(filePath);
}

/** 创建 .bak 备份副本，返回备份路径 */
export function createBackup(filePath) {
  const backupPath = `${filePath}.bak`;
  try {
    const content = readFileSync(filePath);
    writeFileSync(backupPath, content);
    return backupPath;
  } catch (e) {
    return null;
  }
}

/** 获取项目配置 */
export function getProjectConfig() {
  const files = readdirSync(VTJ_PROJECTS_DIR).filter(f => f.endsWith('.json'));
  if (files.length === 0) return null;
  return readJSON(join(VTJ_PROJECTS_DIR, files[0]));
}

/**
 * 判断页面/区块是否为 VTJ 的 raw 手写页面。
 *
 * raw 页面由 ContextMode.Raw 直接加载 .vtj/vue/*.vue，不经过 JSON DSL 运行时渲染。
 * 设计器保存时会从 JSON DSL 重新生成 .vue，因此对 raw 页面做 DSL 同步是有损的：
 * 提取器读不到全部手写方法（例如 question_import.vue 的 _pollImportStatus），
 * 同步会丢失这些方法，随后设计器回存又把丢失部分覆盖到手写代码上。
 * 见 CLAUDE.md/vtj.md「修改 .vue 后的同步步骤（勘误 2026-10-03）」。
 *
 * @param {string} id 页面或区块 ID
 * @returns {boolean} true 表示该页面受保护，禁止同步 DSL
 */
export function isRawPage(id) {
  // 未配置项目根目录、或项目配置不可读时，一律按「非 raw」处理：
  // 同步本身还会校验文件是否存在，这里不应成为第一个抛错的地方。
  try {
    const project = getProjectConfig();
    if (!project?.pages) return false;
    const page = project.pages.find(p => p.id === id);
    return page?.raw === true;
  } catch {
    return false;
  }
}

/** 获取材料配置 */
export function getMaterialConfig() {
  const files = readdirSync(VTJ_MATERIALS_DIR).filter(f => f.endsWith('.json'));
  if (files.length === 0) return null;
  return readJSON(join(VTJ_MATERIALS_DIR, files[0]));
}

/** 列出所有 DSL 文件 ID → 文件名映射 */
export function getDslFileMap() {
  const map = {};
  if (!existsSync(VTJ_FILES_DIR)) return map;
  const files = readdirSync(VTJ_FILES_DIR).filter(f => f.endsWith('.json'));
  for (const f of files) {
    const id = basename(f, '.json');
    map[id] = f;
  }
  return map;
}

// ── 路径构建辅助函数 ────────────────────────────────────

/** 获取 Vue 文件路径 */
export function getVuePath(id) {
  return join(VTJ_VUE_DIR, `${id}.vue`);
}

/** 获取 DSL 文件路径 */
export function getDslPath(id) {
  return join(VTJ_FILES_DIR, `${id}.json`);
}

/** 获取 VTJ 目录 */
export function getVtjDir() {
  return VTJ_DIR;
}

/** 获取 VTJ files 目录 */
export function getVtjFilesDir() {
  return VTJ_FILES_DIR;
}

/** 获取 VTJ projects 目录 */
export function getVtjProjectsDir() {
  return VTJ_PROJECTS_DIR;
}

/** 获取 VTJ materials 目录 */
export function getVtjMaterialsDir() {
  return VTJ_MATERIALS_DIR;
}

/** 获取 VTJ router 文件路径 */
export function getVtjRouterFile() {
  return VTJ_ROUTER_FILE;
}

/** 获取 src/router/index.ts 路径 */
export function getSrcRouterFile() {
  return SRC_ROUTER_FILE;
}