#!/usr/bin/env node

/**
 * VTJ MCP Server — 桥接 Claude Code 与 VTJ.PRO 低代码平台
 *
 * 核心职责：
 *   1. 读取 VTJ 项目配置（页面、区块、API、物料）
 *   2. 读写 .vtj/vue/*.vue 文件的 <script> 业务逻辑
 *   3. 同步 .vue → .vtj/files/*.json DSL（保持版本一致性）
 *   4. 提供 VTJ 物料/组件查询
 *   5. 管理路由配置
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema
} from '@modelcontextprotocol/sdk/types.js';
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'fs';
import { resolve, dirname, basename, extname, join } from 'path';
import { fileURLToPath } from 'url';

// ── 路径常量 ──────────────────────────────────────────────
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = resolve(__dirname, '..');
const VTJ_DIR = join(PROJECT_ROOT, '.vtj');
const VTJ_FILES_DIR = join(VTJ_DIR, 'files');
const VTJ_VUE_DIR = join(VTJ_DIR, 'vue');
const VTJ_PROJECTS_DIR = join(VTJ_DIR, 'projects');
const VTJ_MATERIALS_DIR = join(VTJ_DIR, 'materials');
const VTJ_ROUTER_FILE = join(VTJ_DIR, 'router.js');
const SRC_ROUTER_FILE = join(PROJECT_ROOT, 'src', 'router', 'index.ts');

// ── 工具函数 ──────────────────────────────────────────────

/** 安全读取 JSON 文件 */
function readJSON(filePath) {
  try {
    const content = readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (e) {
    return null;
  }
}

/** 安全写入 JSON 文件 */
function writeJSON(filePath, data) {
  try {
    writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    return true;
  } catch (e) {
    return false;
  }
}

/** 读取文本文件 */
function readText(filePath) {
  try {
    return readFileSync(filePath, 'utf-8');
  } catch (e) {
    return null;
  }
}

/** 写入文本文件 */
function writeText(filePath, content) {
  try {
    writeFileSync(filePath, content, 'utf-8');
    return true;
  } catch (e) {
    return false;
  }
}

/** 获取项目配置 */
function getProjectConfig() {
  const files = readdirSync(VTJ_PROJECTS_DIR).filter(f => f.endsWith('.json'));
  if (files.length === 0) return null;
  return readJSON(join(VTJ_PROJECTS_DIR, files[0]));
}

/** 获取材料配置 */
function getMaterialConfig() {
  const files = readdirSync(VTJ_MATERIALS_DIR).filter(f => f.endsWith('.json'));
  if (files.length === 0) return null;
  return readJSON(join(VTJ_MATERIALS_DIR, files[0]));
}

/** 列出所有 DSL 文件 ID → 文件名映射 */
function getDslFileMap() {
  const map = {};
  if (!existsSync(VTJ_FILES_DIR)) return map;
  const files = readdirSync(VTJ_FILES_DIR).filter(f => f.endsWith('.json'));
  for (const f of files) {
    const id = basename(f, '.json');
    map[id] = f;
  }
  return map;
}

/** 通过 ID 查找页面信息 */
function findPageById(project, id) {
  if (!project?.pages) return null;
  return project.pages.find(p => p.id === id) || null;
}

/** 通过 ID 查找区块信息 */
function findBlockById(project, id) {
  if (!project?.blocks) return null;
  return project.blocks.find(b => b.id === id) || null;
}

/**
 * 解析 Vue SFC 文件，提取各区块
 * 返回 { template, script, style, scriptSetup, full }
 */
function parseVueSFC(source) {
  const result = { template: '', script: '', style: '', scriptSetup: '', styles: [] };

  // 提取 <template>
  const templateMatch = source.match(/<template>([\s\S]*?)<\/template>/i);
  if (templateMatch) result.template = templateMatch[1];

  // 提取 <script setup> 或 <script>
  const scriptSetupMatch = source.match(/<script\s+setup[^>]*>([\s\S]*?)<\/script>/i);
  if (scriptSetupMatch) {
    result.scriptSetup = scriptSetupMatch[1];
  } else {
    const scriptMatch = source.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
    if (scriptMatch) result.script = scriptMatch[1];
  }

  // 提取所有 <style> 块
  const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let styleMatch;
  while ((styleMatch = styleRegex.exec(source)) !== null) {
    result.styles.push(styleMatch[1]);
  }
  if (result.styles.length > 0) {
    result.style = result.styles.join('\n');
  }

  return result;
}

/**
 * 从 Vue SFC 的 script 中提取 methods 签名信息
 * 用于同步到 JSON DSL
 */
function extractMethodsFromScript(scriptContent) {
  const methods = {};
  // 匹配 methods: { ... }
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
  // 匹配 reactive({ ... })
  const reactiveMatch = scriptContent.match(/reactive\s*\(\s*\{([\s\S]*?)\}\s*\)/);
  if (reactiveMatch) {
    const stateBlock = reactiveMatch[1];
    // 简单匹配 key: value 对
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
  // 也检查 setup 中返回的函数（非 methods 块中的）
  const methodNames = Object.keys(methods);

  // 查找 setup 中定义但不在 methods 块中的函数
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

// ── MCP 工具定义 ──────────────────────────────────────────

const TOOLS = [
  // ════════════════════════════════════════════════════════
  // 1. 项目信息类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_get_project_info',
    description: '获取 VTJ 项目完整配置信息，包括所有页面、区块、API 定义、依赖项、项目配置。这是了解整个 VTJ 项目的入口工具。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: []
    }
  },
  {
    name: 'vtj_list_pages',
    description: '列出项目中所有页面，包含页面 ID、名称、标题、路由路径、raw 标记状态。raw=true 的页面由开发人员手动维护，VTJ 设计器不会覆盖。',
    inputSchema: {
      type: 'object',
      properties: {
        filter: {
          type: 'string',
          description: '可选筛选：raw（仅手写页面）、generated（仅 VTJ 生成页面）、all（全部，默认）',
          enum: ['raw', 'generated', 'all']
        }
      },
      required: []
    }
  },
  {
    name: 'vtj_list_blocks',
    description: '列出项目中所有区块组件（可复用组件），包含区块 ID、名称、标题、分类、来源类型。',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: '按分类筛选，如"首页模块"、"公共组件"、"首页区块"、"公共区块"'
        }
      },
      required: []
    }
  },
  {
    name: 'vtj_list_apis',
    description: '列出项目中所有 API 定义，包含 ID、URL、方法、名称和描述。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: []
    }
  },

  // ════════════════════════════════════════════════════════
  // 2. 文件读写类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_read_vue_file',
    description: '读取 VTJ 生成的 .vue 文件内容。可以读取完整文件或仅读取特定部分（template/script/style）。',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '页面或区块的 ID，例如 "mjvdqdu1"（题库页）或 "login"（登录页）'
        },
        section: {
          type: 'string',
          description: '要读取的部分：full（完整文件）、template、script、style',
          enum: ['full', 'template', 'script', 'style']
        }
      },
      required: ['id']
    }
  },
  {
    name: 'vtj_write_vue_script',
    description: `修改 VTJ 生成的 .vue 文件的 <script> 部分。
严格遵守 VTJ 开发规范：
- 只能修改 methods、state（reactive 数据）、lifeCycles（生命周期钩子）、computed（计算属性）
- 绝对不能修改 <template> 结构——UI 结构变更应通过 VTJ 设计器完成
- 保持 useProvider({ id, version }) 调用不变
- 保持 defineComponent + setup() 的 Options API 风格`,
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '页面或区块的 ID'
        },
        scriptContent: {
          type: 'string',
          description: '新的 <script> 部分完整内容（包含 <script lang="ts"> 标签）。如果只修改 methods 方法体，请提供完整 methods 块的替换内容。'
        },
        mode: {
          type: 'string',
          description: '修改模式：replace（完全替换 script 块）、methods（仅替换 methods 对象）、state（仅替换 reactive 数据）、lifeCycles（仅替换生命周期钩子）、addMethod（添加新方法）',
          enum: ['replace', 'methods', 'state', 'lifeCycles', 'addMethod']
        },
        methodName: {
          type: 'string',
          description: '当 mode=addMethod 时，新方法的名称'
        },
        methodBody: {
          type: 'string',
          description: '当 mode=addMethod 时，新方法的函数体（不含 async/function 关键字，直接写 () { ... } 或 async () { ... }）'
        }
      },
      required: ['id', 'scriptContent']
    }
  },
  {
    name: 'vtj_read_dsl_file',
    description: '读取 .vtj/files/ 下的 DSL JSON 文件。DSL（Domain Specific Language）是 VTJ 的中间表示层，用 JSON 完整描述一个 Vue 组件的所有信息（模板节点树、状态、方法、样式等）。',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '页面或区块的 ID'
        },
        section: {
          type: 'string',
          description: '读取指定部分：full（完整 DSL）、nodes（仅模板节点树）、state（仅状态定义）、methods（仅方法定义）、lifeCycles（仅生命周期）',
          enum: ['full', 'nodes', 'state', 'methods', 'lifeCycles', 'dataSources', 'css']
        }
      },
      required: ['id']
    }
  },

  // ════════════════════════════════════════════════════════
  // 3. 同步操作类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_sync_vue_to_dsl',
    description: `将 .vue 文件中修改的业务逻辑同步回 .vtj/files/*.json DSL 文件。
这是 VTJ 开发工作流的关键步骤——每次修改 .vue 的 <script> 后必须执行此同步，否则 VTJ 设计器保存时会覆盖你的修改。

同步内容：
- methods 方法签名（type + params）
- state 字段列表和初始值
- lifeCycles 生命周期声明
- __VERSION__ 版本号（保持一致）`,
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '页面或区块的 ID'
        },
        dryRun: {
          type: 'boolean',
          description: '如果为 true，仅显示将要同步的内容而不实际写入',
          default: false
        }
      },
      required: ['id']
    }
  },
  {
    name: 'vtj_check_consistency',
    description: '检查 .vue 文件和 .vtj/files/*.json DSL 之间的一致性，包括版本号、方法签名、状态字段等。返回不一致项的详细列表。',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '页面或区块的 ID，不提供则检查所有文件'
        }
      },
      required: []
    }
  },

  // ════════════════════════════════════════════════════════
  // 4. 页面结构分析类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_get_page_structure',
    description: '获取页面的节点树结构概览。解析 DSL JSON 的 nodes[] 数组，展示模板中的元素层次结构、组件引用、指令（v-for/v-if）和事件绑定。',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '页面 ID'
        },
        depth: {
          type: 'number',
          description: '展示深度（默认 3 层）',
          default: 3
        }
      },
      required: ['id']
    }
  },

  // ════════════════════════════════════════════════════════
  // 5. 路由管理类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_get_routing_info',
    description: '获取完整的路由配置信息，包括静态路由（src/router/index.ts）和 VTJ 自动生成的路由（.vtj/router.js），以及 Provider 自动注册的 /page/:id 路由。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: []
    }
  },
  {
    name: 'vtj_add_route',
    description: '向静态路由文件（src/router/index.ts）添加新的路由条目。',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: '路由路径，如 "/new-page"'
        },
        name: {
          type: 'string',
          description: '路由名称，如 "NewPage"'
        },
        componentPath: {
          type: 'string',
          description: '组件导入路径。VTJ 页面使用 "$vtj/vue/<id>.vue"，手写页面使用 "@/views/<name>.vue"'
        },
        title: {
          type: 'string',
          description: '页面标题（用于文档）'
        }
      },
      required: ['path', 'name', 'componentPath']
    }
  },

  // ════════════════════════════════════════════════════════
  // 6. 物料/组件查询类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_get_material_catalog',
    description: `获取 VTJ 可用的全部组件物料目录。
包含：
- HTML 原生元素（div, span, button, input 等）
- Element Plus 组件（ElButton, ElInput, ElTable 等）
- VTJ UI 组件（XIcon 等）
- VTJ Charts 图表组件
- Ant Design Vue 组件（可选）
返回每个组件的名称、标签、分类、可用属性列表。`,
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: '按分类筛选：html、element-plus、vtj-ui、vtj-charts、antdv'
        },
        search: {
          type: 'string',
          description: '按名称或标签搜索特定组件'
        }
      },
      required: []
    }
  },
  {
    name: 'vtj_get_component_detail',
    description: '获取特定组件的完整信息，包括所有属性配置（props）、设置器类型、子组件规则、代码片段等。这是设计新页面时了解可用组件的关键工具。',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: '组件名称，如 "ElButton"、"ElInput"、"ElTable"、"XIcon"、"div"'
        }
      },
      required: ['name']
    }
  },

  // ════════════════════════════════════════════════════════
  // 7. 项目操作类
  // ════════════════════════════════════════════════════════
  {
    name: 'vtj_create_page_scaffold',
    description: `为新页面创建基础脚手架文件。会同时创建：
1. .vtj/files/<id>.json — DSL 定义文件
2. .vtj/vue/<id>.vue — Vue SFC 文件
3. 可选的静态路由条目`,
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '新页面的唯一 ID'
        },
        name: {
          type: 'string',
          description: '组件名称（PascalCase），如 "MyNewPage"'
        },
        title: {
          type: 'string',
          description: '页面标题（中文），如 "我的新页面"'
        },
        icon: {
          type: 'string',
          description: 'Element Plus 图标名，如 "Collection"、"HomeFilled"',
          default: 'Collection'
        },
        addRoute: {
          type: 'boolean',
          description: '是否同时添加静态路由条目',
          default: false
        },
        routePath: {
          type: 'string',
          description: '当 addRoute=true 时的路由路径，如 "/my-page"'
        }
      },
      required: ['id', 'name', 'title']
    }
  }
];

// ── 资源定义（项目元数据）────────────────────────────────

const RESOURCES = [
  {
    uri: 'vtj://project/config',
    name: 'VTJ 项目配置',
    description: '项目完整配置 JSON（pages, blocks, apis, dependencies, config）',
    mimeType: 'application/json'
  },
  {
    uri: 'vtj://project/routing',
    name: '路由配置',
    description: '当前路由配置信息（静态路由 + VTJ 路由）',
    mimeType: 'application/json'
  },
  {
    uri: 'vtj://materials/catalog',
    name: '物料目录',
    description: '所有可用组件的目录',
    mimeType: 'application/json'
  }
];

// ── 工具处理器映射 ────────────────────────────────────────

const toolHandlers = {
  // ── 1. 项目信息 ──────────────────────────────────────
  'vtj_get_project_info': () => {
    const project = getProjectConfig();
    if (!project) return { error: '无法读取项目配置' };

    return {
      projectId: project.id,
      name: project.name,
      description: project.description,
      platform: project.platform,
      homepage: project.homepage,
      pagesCount: project.pages?.length || 0,
      blocksCount: project.blocks?.length || 0,
      apisCount: project.apis?.length || 0,
      dependenciesCount: project.dependencies?.length || 0,
      pages: project.pages?.map(p => ({
        id: p.id,
        name: p.name,
        title: p.title,
        raw: p.raw,
        icon: p.icon,
        hidden: p.hidden,
        needLogin: p.needLogin
      })),
      blocks: project.blocks?.map(b => ({
        id: b.id,
        name: b.name,
        title: b.title,
        category: b.category,
        fromType: b.fromType
      })),
      apis: project.apis,
      config: project.config,
      locked: project.locked
    };
  },

  'vtj_list_pages': ({ filter = 'all' }) => {
    const project = getProjectConfig();
    if (!project?.pages) return { error: '无法读取项目页面配置' };

    let pages = project.pages;
    if (filter === 'raw') pages = pages.filter(p => p.raw === true);
    if (filter === 'generated') pages = pages.filter(p => p.raw !== true);

    const dslMap = getDslFileMap();

    return {
      total: pages.length,
      filter,
      pages: pages.map(p => ({
        id: p.id,
        name: p.name,
        title: p.title,
        icon: p.icon,
        raw: !!p.raw,
        hidden: !!p.hidden,
        needLogin: !!p.needLogin,
        hasDsl: !!dslMap[p.id],
        hasVue: existsSync(join(VTJ_VUE_DIR, `${p.id}.vue`)),
        // 推测路由路径
        routes: inferRoutes(p)
      }))
    };
  },

  'vtj_list_blocks': ({ category }) => {
    const project = getProjectConfig();
    if (!project?.blocks) return { error: '无法读取项目区块配置' };

    let blocks = project.blocks;
    if (category) {
      blocks = blocks.filter(b => b.category === category);
    }

    // 统计分类
    const categories = {};
    for (const b of blocks) {
      categories[b.category] = (categories[b.category] || 0) + 1;
    }

    return {
      total: blocks.length,
      categories,
      blocks: blocks.map(b => ({
        id: b.id,
        name: b.name,
        title: b.title,
        category: b.category,
        fromType: b.fromType || 'Schema'
      }))
    };
  },

  'vtj_list_apis': () => {
    const project = getProjectConfig();
    if (!project?.apis) return { error: '无法读取 API 配置' };

    return {
      total: project.apis.length,
      apis: project.apis.map(a => ({
        id: a.id,
        name: a.name,
        label: a.label,
        method: a.method?.toUpperCase(),
        url: a.url
      }))
    };
  },

  // ── 2. 文件读写 ──────────────────────────────────────
  'vtj_read_vue_file': ({ id, section = 'full' }) => {
    const vuePath = join(VTJ_VUE_DIR, `${id}.vue`);
    if (!existsSync(vuePath)) {
      return { error: `文件不存在: .vtj/vue/${id}.vue` };
    }

    const content = readText(vuePath);
    if (content === null) return { error: `无法读取文件: ${vuePath}` };

    if (section === 'full') {
      return {
        id,
        path: `.vtj/vue/${id}.vue`,
        content,
        lines: content.split('\n').length
      };
    }

    const parsed = parseVueSFC(content);
    if (section === 'template') {
      return { id, section: 'template', content: parsed.template };
    }
    if (section === 'script') {
      return { id, section: 'script', content: parsed.script || parsed.scriptSetup };
    }
    if (section === 'style') {
      return { id, section: 'style', content: parsed.style };
    }
  },

  'vtj_write_vue_script': ({ id, scriptContent, mode = 'replace', methodName, methodBody }) => {
    const vuePath = join(VTJ_VUE_DIR, `${id}.vue`);
    if (!existsSync(vuePath)) {
      return { error: `文件不存在: .vtj/vue/${id}.vue` };
    }

    const original = readText(vuePath);
    if (original === null) return { error: '无法读取文件' };

    let newContent;

    if (mode === 'replace') {
      // 完全替换 script 块
      const templateMatch = original.match(/([\s\S]*?)<script/);
      const styleMatch = original.match(/<\/script>([\s\S]*)/);

      if (!templateMatch || !styleMatch) {
        // 尝试替换整个文件
        newContent = scriptContent;
      } else {
        const before = templateMatch[1];
        const after = styleMatch[1];
        newContent = before + scriptContent + after;
      }
    } else if (mode === 'methods') {
      // 仅替换 methods 块
      const scriptTagRegex = /(<script[^>]*>)([\s\S]*?)(<\/script>)/i;
      const scriptMatch = original.match(scriptTagRegex);
      if (!scriptMatch) return { error: '无法解析 script 标签' };

      const scriptOpen = scriptMatch[1];
      const scriptBody = scriptMatch[2];
      const scriptClose = scriptMatch[3];

      const newScriptBody = scriptBody.replace(
        /methods\s*:\s*\{[\s\S]*?\n\s*\}/,
        `methods: ${scriptContent}`
      );

      newContent = original.replace(scriptTagRegex, `${scriptOpen}${newScriptBody}${scriptClose}`);
    } else if (mode === 'state') {
      // 替换 reactive state
      const newScriptBody = original.replace(
        /(reactive\s*\(\s*)\{[\s\S]*?(\}\s*\))/,
        `$1${scriptContent}$2`
      );
      newContent = newScriptBody;
    } else if (mode === 'addMethod') {
      if (!methodName || !methodBody) {
        return { error: 'addMethod 模式需要 methodName 和 methodBody' };
      }
      // 在 methods 块末尾添加
      const methodsEnd = original.match(/(methods\s*:\s*\{[\s\S]*?)(\n\s*\})/);
      if (!methodsEnd) return { error: '找不到 methods 块' };

      const insert = `,\n    ${methodName}: ${methodBody}\n  `;
      newContent = original.replace(methodsEnd[0], methodsEnd[1] + insert + methodsEnd[2].trim());
    } else if (mode === 'lifeCycles') {
      // 替换/添加生命周期钩子
      newContent = original.replace(
        /(lifeCycles\s*:\s*\{[\s\S]*?\n\s*\})/,
        scriptContent
      );
    }

    if (!newContent) {
      return { error: '无法生成新内容，请检查参数' };
    }

    // 备份原文件
    const bakPath = vuePath + '.bak';
    writeText(bakPath, original);

    const success = writeText(vuePath, newContent);
    if (!success) return { error: '写入失败' };

    return {
      success: true,
      id,
      mode,
      path: `.vtj/vue/${id}.vue`,
      backupPath: `.vtj/vue/${id}.vue.bak`,
      message: '文件已更新。建议立即运行 vtj_sync_vue_to_dsl 同步 DSL JSON。',
      reminder: '⚠️ 请清理 Vite 缓存（rm -rf node_modules/.vite/）后刷新浏览器。'
    };
  },

  'vtj_read_dsl_file': ({ id, section = 'full' }) => {
    const dslPath = join(VTJ_FILES_DIR, `${id}.json`);
    if (!existsSync(dslPath)) {
      return { error: `文件不存在: .vtj/files/${id}.json` };
    }

    const dsl = readJSON(dslPath);
    if (!dsl) return { error: `无法解析 DSL JSON: ${dslPath}` };

    if (section === 'full') {
      return {
        id,
        path: `.vtj/files/${id}.json`,
        name: dsl.name,
        version: dsl.__VERSION__,
        hasState: !!dsl.state && Object.keys(dsl.state).length > 0,
        hasMethods: !!dsl.methods && Object.keys(dsl.methods).length > 0,
        hasComputed: !!dsl.computed && Object.keys(dsl.computed).length > 0,
        hasLifeCycles: !!dsl.lifeCycles && Object.keys(dsl.lifeCycles).length > 0,
        nodesCount: dsl.nodes?.length || 0,
        dsl
      };
    }

    const sections = {
      nodes: dsl.nodes,
      state: dsl.state,
      methods: dsl.methods,
      lifeCycles: dsl.lifeCycles,
      dataSources: dsl.dataSources,
      css: dsl.css
    };

    return {
      id,
      section,
      content: sections[section] || null
    };
  },

  // ── 3. 同步操作 ──────────────────────────────────────
  'vtj_sync_vue_to_dsl': ({ id, dryRun = false }) => {
    const vuePath = join(VTJ_VUE_DIR, `${id}.vue`);
    const dslPath = join(VTJ_FILES_DIR, `${id}.json`);

    if (!existsSync(vuePath)) return { error: `Vue 文件不存在: .vtj/vue/${id}.vue` };
    if (!existsSync(dslPath)) return { error: `DSL 文件不存在: .vtj/files/${id}.json` };

    const vueContent = readText(vuePath);
    const dsl = readJSON(dslPath);
    if (!vueContent || !dsl) return { error: '无法读取文件' };

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
        mode: 'dryRun',
        id,
        vueVersion,
        dslVersion,
        versionMatch: vueVersion === dslVersion,
        changes,
        changesCount: changes.length,
        wouldUpdate: changes.length > 0
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
    if (!success) return { error: '写入 DSL 失败' };

    return {
      success: true,
      id,
      changes,
      changesCount: changes.length,
      message: changes.length > 0
        ? `已同步 ${changes.length} 项变更到 .vtj/files/${id}.json`
        : '无需同步，Vue 和 DSL 一致',
      reminder: '⚠️ 请清理 Vite 缓存后刷新验证。'
    };
  },

  'vtj_check_consistency': ({ id }) => {
    const results = [];
    const idsToCheck = id ? [id] : Object.keys(getDslFileMap());

    for (const checkId of idsToCheck) {
      const vuePath = join(VTJ_VUE_DIR, `${checkId}.vue`);
      const dslPath = join(VTJ_FILES_DIR, `${checkId}.json`);

      if (!existsSync(vuePath) || !existsSync(dslPath)) {
        results.push({
          id: checkId,
          status: 'missing_file',
          hasVue: existsSync(vuePath),
          hasDsl: existsSync(dslPath)
        });
        continue;
      }

      const vueContent = readText(vuePath);
      const dsl = readJSON(dslPath);

      if (!vueContent || !dsl) {
        results.push({ id: checkId, status: 'read_error' });
        continue;
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

      results.push({
        id: checkId,
        name: dsl.name || checkId,
        status: issues.length === 0 ? 'consistent' : 'inconsistent',
        vueVersion,
        dslVersion,
        versionMatch,
        issues,
        missingInDsl,
        extraInDsl
      });
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
  },

  // ── 4. 页面结构分析 ──────────────────────────────────
  'vtj_get_page_structure': ({ id, depth = 3 }) => {
    const dslPath = join(VTJ_FILES_DIR, `${id}.json`);
    if (!existsSync(dslPath)) {
      return { error: `DSL 文件不存在: .vtj/files/${id}.json` };
    }

    const dsl = readJSON(dslPath);
    if (!dsl?.nodes) return { error: 'DSL 中无 nodes 定义' };

    /**
     * 递归解析节点树
     */
    function parseNode(node, currentDepth = 0) {
      if (currentDepth > depth) return { __truncated__: true };

      const info = {
        id: node.id,
        name: node.name,
        from: node.from || '(原生 HTML)',
        hasProps: !!node.props && Object.keys(node.props).length > 0,
        hasEvents: !!node.events && Object.keys(node.events).length > 0,
        directives: node.directives?.map(d => d.name) || [],
        childrenType: typeof node.children
      };

      // 提取关键属性
      if (node.props) {
        info.props = Object.keys(node.props).map(k => {
          const v = node.props[k];
          return {
            name: k,
            type: v?.type || 'literal',
            isDynamic: v?.type === 'JSExpression'
          };
        });
      }

      // 提取事件
      if (node.events) {
        info.events = Object.keys(node.events).map(k => {
          const v = node.events[k];
          return {
            event: k,
            handler: v?.handler?.value?.substring(0, 80) || '(native)'
          };
        });
      }

      // 递归子节点
      if (Array.isArray(node.children)) {
        info.children = node.children.map(c => parseNode(c, currentDepth + 1));
        info.childrenCount = node.children.length;
      } else if (typeof node.children === 'object' && node.children?.type === 'JSExpression') {
        info.dynamicChildren = node.children.value?.substring(0, 60);
      } else if (typeof node.children === 'string') {
        info.textContent = node.children.substring(0, 100);
      }

      return info;
    }

    const structure = dsl.nodes.map(n => parseNode(n));

    return {
      id,
      name: dsl.name,
      rootNodesCount: dsl.nodes.length,
      maxDepth: depth,
      structure
    };
  },

  // ── 5. 路由管理 ──────────────────────────────────────
  'vtj_get_routing_info': () => {
    const project = getProjectConfig();
    const staticRouter = readText(SRC_ROUTER_FILE);
    const vtjRouter = readText(VTJ_ROUTER_FILE);

    // 解析静态路由
    const staticRoutes = [];
    if (staticRouter) {
      const routeRegex = /\{\s*path\s*:\s*['"]([^'"]+)['"]\s*,\s*name\s*:\s*['"]([^'"]+)['"]\s*,\s*\n?\s*component\s*:\s*\(\)\s*=>\s*import\(['"]([^'"]+)['"]\)/g;
      let match;
      while ((match = routeRegex.exec(staticRouter)) !== null) {
        staticRoutes.push({
          path: match[1],
          name: match[2],
          component: match[3]
        });
      }
    }

    // VTJ 自动路由
    const autoRoutes = (project?.pages || []).map(p => ({
      path: `/page/${p.id}`,
      name: p.name,
      title: p.title,
      autoGenerated: true
    }));

    return {
      staticRoutesCount: staticRoutes.length,
      autoRoutesCount: autoRoutes.length,
      staticRoutes,
      autoRoutes,
      vtjRouterContent: vtjRouter,
      projectHomepage: project?.homepage || '',
      enableStaticRoute: true
    };
  },

  'vtj_add_route': ({ path, name, componentPath }) => {
    const content = readText(SRC_ROUTER_FILE);
    if (!content) return { error: '无法读取路由文件' };

    // 检查路由是否已存在
    if (content.includes(`path: '${path}'`) || content.includes(`path: "${path}"`)) {
      return { error: `路由路径 "${path}" 已存在` };
    }

    // 在最后一个路由条目后插入
    const lastRouteIndex = content.lastIndexOf('},\n');
    if (lastRouteIndex === -1) return { error: '无法找到插入位置' };

    const newRoute = `  {\n    path: '${path}',\n    name: '${name}',\n    component: () => import('${componentPath}')\n  }`;

    const before = content.substring(0, lastRouteIndex + 2);
    const after = content.substring(lastRouteIndex + 2);
    const newContent = before + ',\n' + newRoute + after;

    // 备份
    writeText(SRC_ROUTER_FILE + '.bak', content);

    const success = writeText(SRC_ROUTER_FILE, newContent);
    if (!success) return { error: '写入路由文件失败' };

    return {
      success: true,
      path,
      name,
      componentPath,
      message: '路由已添加。重启开发服务器生效。'
    };
  },

  // ── 6. 物料查询 ──────────────────────────────────────
  'vtj_get_material_catalog': ({ category, search }) => {
    const material = getMaterialConfig();
    if (!material) return { error: '无法读取物料配置' };

    // 构建分类信息
    const catalog = {};
    const categoryNames = {
      'html': 'HTML 原生元素',
      'element-plus': 'Element Plus 组件',
      'vtj-ui': 'VTJ UI 组件',
      'vtj-charts': 'VTJ Charts 图表',
      'antdv': 'Ant Design Vue 组件'
    };

    for (const [key, comp] of Object.entries(material)) {
      const cat = comp.categoryId || 'unknown';
      if (category && cat !== category) continue;
      if (search && !key.includes(search) && !comp.label?.includes(search)) continue;

      if (!catalog[cat]) catalog[cat] = { name: categoryNames[cat] || cat, components: [] };

      catalog[cat].components.push({
        name: key,
        label: comp.label || key,
        hasProps: !!comp.props,
        propCount: comp.props?.length || 0,
        allowsChildren: comp.childIncludes !== false,
        snippet: comp.snippet?.children || comp.label
      });
    }

    const totalCount = Object.values(catalog).reduce((sum, c) => sum + c.components.length, 0);

    return {
      totalComponents: totalCount,
      categories: catalog,
      categoryFilter: category || 'all',
      searchFilter: search || null
    };
  },

  'vtj_get_component_detail': ({ name }) => {
    const material = getMaterialConfig();
    if (!material) return { error: '无法读取物料配置' };

    const comp = material[name];
    if (!comp) {
      // 尝试模糊搜索
      const suggestions = Object.keys(material).filter(k =>
        k.toLowerCase().includes(name.toLowerCase()) ||
        material[k].label?.toLowerCase().includes(name.toLowerCase())
      );
      return {
        error: `未找到组件 "${name}"`,
        suggestions: suggestions.slice(0, 10)
      };
    }

    return {
      name: comp.name,
      label: comp.label,
      categoryId: comp.categoryId,
      allowsChildren: comp.childIncludes !== false,
      props: comp.props?.map(p => ({
        name: p.name,
        label: p.label,
        setters: Array.isArray(p.setters)
          ? p.setters.map(s => typeof s === 'string' ? s : s.name)
          : (typeof p.setters === 'string' ? [p.setters] : []),
        defaultValue: p.defaultValue,
        required: p.required
      })),
      snippet: comp.snippet,
      events: comp.events
    };
  },

  // ── 7. 项目操作 ──────────────────────────────────────
  'vtj_create_page_scaffold': ({ id, name: pageName, title, icon = 'Collection', addRoute = false, routePath }) => {
    const vuePath = join(VTJ_VUE_DIR, `${id}.vue`);
    const dslPath = join(VTJ_FILES_DIR, `${id}.json`);

    if (existsSync(vuePath)) return { error: `Vue 文件已存在: .vtj/vue/${id}.vue` };
    if (existsSync(dslPath)) return { error: `DSL 文件已存在: .vtj/files/${id}.json` };

    const project = getProjectConfig();
    const projectVersion = project?.dependencies?.[0]?.version || 'latest';
    const now = Date.now();
    const version = String(now);

    // 创建 Vue SFC
    const vueContent = `<!-- ${title} -->
<template>
  <div class="${name.toLowerCase()}">
    <h1>${title}</h1>
    <!-- VTJ 设计器生成的模板内容将在此处 -->
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: '${pageName}',
  setup(props) {
    const provider = useProvider({ id: '${id}', version: '${version}' });
    const state = reactive({
      loading: false
    });
    return { state, provider };
  },
  methods: {
    async handleInit() {
      // TODO: 初始化逻辑
    }
  },
  mounted() {
    this.handleInit();
  }
});
</script>

<style lang="css" scoped>
.${name.toLowerCase()} {
  padding: 20px;
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
}
</style>`;

    // 创建 DSL JSON
    const dslContent = {
      id,
      name: pageName,
      __VTJ_BLOCK__: true,
      __VERSION__: version,
      state: {
        loading: { type: 'JSExpression', value: 'false' }
      },
      methods: {
        handleInit: { type: 'asyncMethod' }
      },
      lifeCycles: {
        mounted: { type: 'method' }
      },
      nodes: [
        {
          id: `${id}_root`,
          name: 'div',
          from: '',
          props: {
            class: {
              type: 'JSExpression',
              value: `'${name.toLowerCase()}'`
            }
          },
          children: [
            {
              id: `${id}_title`,
              name: 'h1',
              from: '',
              children: title
            }
          ],
          locked: false,
          invisible: false
        }
      ],
      css: `.${name.toLowerCase()} { padding: 20px; font-family: 'Noto Sans SC', 'PingFang SC', sans-serif; }`,
      locked: false
    };

    // 写入文件
    writeText(vuePath, vueContent);
    writeJSON(dslPath, dslContent);

    // 可选：添加路由
    let routeResult = null;
    if (addRoute && routePath) {
      routeResult = toolHandlers['vtj_add_route']({
        path: routePath,
        name: pageName,
        componentPath: `$vtj/vue/${id}.vue`
      });
    }

    // 可选：添加到项目配置
    const projectFiles = readdirSync(VTJ_PROJECTS_DIR).filter(f => f.endsWith('.json'));
    const projectFile = projectFiles.length > 0 ? join(VTJ_PROJECTS_DIR, projectFiles[0]) : null;
    const updatedProject = projectFile ? readJSON(projectFile) : null;
    if (updatedProject) {
      updatedProject.pages = updatedProject.pages || [];
      if (!updatedProject.pages.find(p => p.id === id)) {
        updatedProject.pages.push({
          id,
          dir: false,
          raw: true,
          icon,
          mask: false,
          meta: '',
          name: pageName,
          page: 'page',
          pure: true,
          type: 'page',
          cache: false,
          style: null,
          title,
          hidden: false,
          layout: false,
          needLogin: false
        });
        writeJSON(join(VTJ_PROJECTS_DIR, readdirSync(VTJ_PROJECTS_DIR).find(f => f.endsWith('.json'))), updatedProject);
      }
    }

    return {
      success: true,
      id,
      name: pageName,
      title,
      files: {
        vue: `.vtj/vue/${id}.vue`,
        dsl: `.vtj/files/${id}.json`
      },
      route: routeResult,
      message: `页面"${title}" (${pageName}) 脚手架已创建。可在 VTJ 设计器中拖拽组件构建 UI，Claude Code 将负责业务逻辑。`
    };
  }
};

// ── 资源处理器 ───────────────────────────────────────────

const resourceHandlers = {
  'vtj://project/config': () => {
    const project = getProjectConfig();
    return JSON.stringify(project, null, 2);
  },
  'vtj://project/routing': () => {
    return JSON.stringify(toolHandlers['vtj_get_routing_info'](), null, 2);
  },
  'vtj://materials/catalog': () => {
    return JSON.stringify(toolHandlers['vtj_get_material_catalog']({}), null, 2);
  }
};

// ── 服务器启动 ───────────────────────────────────────────

async function main() {
  const server = new Server(
    {
      name: 'vtj-mcp-server',
      version: '1.0.0'
    },
    {
      capabilities: {
        tools: {},
        resources: {}
      }
    }
  );

  // 注册工具列表
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOLS
  }));

  // 注册工具调用处理
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const handler = toolHandlers[name];

    if (!handler) {
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: `未知工具: ${name}` }, null, 2) }]
      };
    }

    try {
      const result = handler(args || {});
      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            error: '工具执行错误',
            message: error.message,
            stack: error.stack
          }, null, 2)
        }]
      };
    }
  });

  // 注册资源列表
  server.setRequestHandler(ListResourcesRequestSchema, async () => ({
    resources: RESOURCES
  }));

  // 注册资源读取
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;
    const handler = resourceHandlers[uri];

    if (!handler) {
      throw new Error(`未知资源: ${uri}`);
    }

    return {
      contents: [{
        uri,
        mimeType: 'application/json',
        text: handler()
      }]
    };
  });

  // 启动 stdio 传输
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // 注意：stdio MCP 服务器不应向 stdout 输出日志，但可向 stderr 输出
  console.error('VTJ MCP Server 已启动');
  console.error(`项目根目录: ${PROJECT_ROOT}`);
  console.error(`VTJ 目录: ${VTJ_DIR}`);
  console.error(`可用工具: ${TOOLS.map(t => t.name).join(', ')}`);
}

main().catch(error => {
  console.error('服务器启动失败:', error);
  process.exit(1);
});

// ── 辅助函数 ─────────────────────────────────────────────

/** 根据页面配置推测路由 */
function inferRoutes(page) {
  const routes = [];

  // 自动路由
  routes.push({ type: 'auto', path: `/page/${page.id}` });

  // 已知映射
  const knownRoutes = {
    'jjvdntly': '/home',
    'mjvdqdu1': '/',
    'ujvdv5fe': '/answer',
    'login': '/login',
    'questionImport': '/question-import',
    'njvdr28b': '/page/njvdr28b',
    'ojvdrg4v': '/page/ojvdrg4v',
    'rjvduc4b': '/page/rjvduc4b',
    'sjvdul3v': '/page/sjvdul3v',
    'tjvdux1w': '/page/tjvdux1w',
    'pjvds138': '/page/pjvds138'
  };

  if (knownRoutes[page.id]) {
    routes.push({ type: 'static', path: knownRoutes[page.id] });
  }

  return routes;
}
