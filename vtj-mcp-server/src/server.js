/**
 * MCP 服务器入口模块
 * 注册所有工具、资源处理器，提供 createServer / handleToolCall / readResource / start
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ListResourceTemplatesRequestSchema
} from '@modelcontextprotocol/sdk/types.js';

// ── 工具模块导入 ──────────────────────────────────────────────

import * as projectInfo from './tools/project-info.js';
import * as fileOperations from './tools/file-operations.js';
import * as syncOperations from './tools/sync-operations.js';
import * as structureAnalysis from './tools/structure-analysis.js';
import * as routeManagement from './tools/route-management.js';
import * as materialQuery from './tools/material-query.js';
import * as projectActions from './tools/project-actions.js';

import { configure } from './core/file-system.js';
import { existsSync } from 'node:fs';
import { dirname, join, parse, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * 从 startDir 向上查找包含 .vtj 目录的项目根。
 * @param {string} startDir 起始目录
 * @returns {string|null} 找到返回绝对路径，否则 null
 */
function findProjectRoot(startDir) {
  let current = resolve(startDir);
  const { root } = parse(current);
  while (true) {
    if (existsSync(join(current, '.vtj'))) return current;
    if (current === root) return null;
    current = dirname(current);
  }
}

/**
 * 解析 VTJ 项目根目录。
 *
 * 优先级：VTJ_PROJECT_ROOT 环境变量 → 从 cwd 向上找 .vtj → 从本文件位置向上找 .vtj，
 * 都失败时回退到 cwd。缺了这一步，configure() 不会被调用，所有路径常量都是空串，
 * 工具将找不到任何 .vtj 文件。
 *
 * @returns {string} 绝对路径
 */
export function resolveProjectRoot() {
  const fromEnv = process.env.VTJ_PROJECT_ROOT;
  if (fromEnv) return resolve(fromEnv);

  const fromCwd = findProjectRoot(process.cwd());
  if (fromCwd) return fromCwd;

  const fromModule = findProjectRoot(dirname(fileURLToPath(import.meta.url)));
  if (fromModule) return fromModule;

  return resolve(process.cwd());
}

// ── 聚合所有工具 ──────────────────────────────────────────────

const TOOL_MODULES = [
  projectInfo,
  fileOperations,
  syncOperations,
  structureAnalysis,
  routeManagement,
  materialQuery,
  projectActions
];

export const ALL_TOOLS = TOOL_MODULES.flatMap(m => m.TOOLS);

const ALL_HANDLERS = Object.assign({}, ...TOOL_MODULES.map(m => m.handlers));

// ── 资源定义 ──────────────────────────────────────────────────

export const RESOURCES = [
  {
    uri: 'vtj://project/config',
    name: 'VTJ 项目配置',
    description: '项目完整配置 JSON',
    mimeType: 'application/json'
  },
  {
    uri: 'vtj://project/routing',
    name: '路由配置',
    description: '当前路由配置信息',
    mimeType: 'application/json'
  },
  {
    uri: 'vtj://materials/catalog',
    name: '物料目录',
    description: '所有可用组件的目录',
    mimeType: 'application/json'
  }
];

const RESOURCE_HANDLERS = {
  'vtj://project/config': async () => {
    const { getProjectConfig } = await import('./core/file-system.js');
    const config = getProjectConfig();
    return JSON.stringify(config, null, 2);
  },
  'vtj://project/routing': async () => {
    const result = await ALL_HANDLERS.vtj_get_routing_info({});
    return JSON.stringify(result, null, 2);
  },
  'vtj://materials/catalog': async () => {
    const result = await ALL_HANDLERS.vtj_get_material_catalog({});
    return JSON.stringify(result, null, 2);
  }
};

// ── 工具调用分发 ──────────────────────────────────────────────

export async function handleToolCall(name, args = {}) {
  const handler = ALL_HANDLERS[name];
  if (!handler) {
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({ error: `未知工具: ${name}` }, null, 2)
      }]
    };
  }

  try {
    const result = await handler(args);
    return {
      content: [{
        type: 'text',
        text: JSON.stringify(result, null, 2)
      }]
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
}

// ── 资源读取 ──────────────────────────────────────────────────

export async function readResource(uri) {
  const handler = RESOURCE_HANDLERS[uri];
  if (!handler) {
    throw new Error(`未知资源: ${uri}`);
  }

  const text = await handler();
  return {
    contents: [{
      uri,
      mimeType: 'application/json',
      text
    }]
  };
}

// ── 创建服务器实例 ────────────────────────────────────────────

export function createServer({ projectRoot } = {}) {
  if (projectRoot) {
    configure(projectRoot);
  }

  const server = new Server(
    { name: 'vtj-mcp-server', version: '1.0.0' },
    { capabilities: { tools: {}, resources: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: ALL_TOOLS
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    return handleToolCall(name, args || {});
  });

  server.setRequestHandler(ListResourcesRequestSchema, async () => ({
    resources: RESOURCES
  }));

  // 本服务不提供参数化资源模板；显式声明空列表，避免宿主反复记录
  // "Method not found" 警告。
  server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({
    resourceTemplates: []
  }));

  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;
    return readResource(uri);
  });

  return server;
}

// ── 启动服务器 ────────────────────────────────────────────────

export async function start() {
  const projectRoot = resolveProjectRoot();
  const server = createServer({ projectRoot });
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('VTJ MCP Server 已启动');
  console.error(`项目根目录: ${projectRoot}`);
  console.error(`可用工具: ${ALL_TOOLS.map(t => t.name).join(', ')}`);
}
