/**
 * 项目信息工具模块 — 获取项目配置、页面、区块、API 列表
 */

import {
  getProjectConfig, getDslFileMap, existsFile, getVuePath
} from '../core/file-system.js';
import { inferRoutes } from '../utils/helpers.js';
import { createSuccessResponse, createErrorResponse } from '../utils/logger.js';

// ── 工具定义 ──────────────────────────────────────────────

export const TOOLS = [
  {
    name: 'vtj_get_project_info',
    description: '获取 VTJ 项目完整配置信息，包括所有页面、区块、API 定义、依赖项、项目配置。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: []
    }
  },
  {
    name: 'vtj_list_pages',
    description: '列出项目中所有页面，包含页面 ID、名称、标题、路由路径、raw 标记状态。',
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
          description: '按分类筛选'
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
  }
];

// ── 处理器 ──────────────────────────────────────────────

export const handlers = {
  async vtj_get_project_info() {
    const project = getProjectConfig();
    if (!project) {
      return createErrorResponse('PROJECT_NOT_FOUND', '无法读取项目配置');
    }

    return createSuccessResponse({
      name: project.name,
      description: project.description,
      platform: project.platform,
      homepage: project.homepage,
      pages: project.pages?.map(p => ({
        id: p.id,
        name: p.name,
        title: p.title,
        raw: p.raw,
        icon: p.icon,
        hidden: p.hidden,
        needLogin: p.needLogin
      })) || [],
      blocks: project.blocks?.map(b => ({
        id: b.id,
        name: b.name,
        title: b.title,
        category: b.category,
        fromType: b.fromType
      })) || [],
      apis: project.apis || [],
      pagesCount: project.pages?.length || 0,
      blocksCount: project.blocks?.length || 0,
      apisCount: project.apis?.length || 0,
      dependenciesCount: project.dependencies?.length || 0
    });
  },

  async vtj_list_pages({ filter = 'all' } = {}) {
    const project = getProjectConfig();
    if (!project?.pages) {
      return createErrorResponse('PROJECT_NOT_FOUND', '无法读取项目页面配置');
    }

    let pages = project.pages;
    if (filter === 'raw') pages = pages.filter(p => p.raw === true);
    if (filter === 'generated') pages = pages.filter(p => p.raw !== true);

    const dslMap = getDslFileMap();

    return createSuccessResponse(pages.map(p => ({
      id: p.id,
      name: p.name,
      title: p.title,
      icon: p.icon,
      raw: !!p.raw,
      hidden: !!p.hidden,
      needLogin: !!p.needLogin,
      hasDsl: !!dslMap[p.id],
      hasVue: existsFile(getVuePath(p.id)),
      routes: inferRoutes(p)
    })));
  },

  async vtj_list_blocks({ category } = {}) {
    const project = getProjectConfig();
    if (!project?.blocks) {
      return createErrorResponse('PROJECT_NOT_FOUND', '无法读取项目区块配置');
    }

    let blocks = project.blocks;
    if (category) {
      blocks = blocks.filter(b => b.category === category);
    }

    return createSuccessResponse(blocks.map(b => ({
      id: b.id,
      name: b.name,
      title: b.title,
      category: b.category,
      fromType: b.fromType || 'Schema'
    })));
  },

  async vtj_list_apis() {
    const project = getProjectConfig();
    if (!project?.apis) {
      return createErrorResponse('PROJECT_NOT_FOUND', '无法读取 API 配置');
    }

    return createSuccessResponse(project.apis.map(a => ({
      id: a.id,
      name: a.name,
      label: a.label,
      method: a.method?.toUpperCase(),
      url: a.url
    })));
  }
};
