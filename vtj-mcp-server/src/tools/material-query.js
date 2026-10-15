/**
 * 物料查询工具模块 — 获取组件目录和组件详情
 */

import { getMaterialConfig } from '../core/file-system.js';
import { createSuccessResponse, createErrorResponse } from '../utils/logger.js';

// ── 工具定义 ──────────────────────────────────────────────

export const TOOLS = [
  {
    name: 'vtj_get_material_catalog',
    description: '获取 VTJ 可用的全部组件物料目录，支持分类筛选和搜索。',
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
    description: '获取特定组件的完整信息，包括所有属性配置（props）、设置器类型、子组件规则、代码片段等。',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: '组件名称，如 "el-button"、"el-input"'
        }
      },
      required: ['name']
    }
  }
];

// ── 处理器 ──────────────────────────────────────────────

export const handlers = {
  async vtj_get_material_catalog({ category, search } = {}) {
    const material = getMaterialConfig();
    if (!material) {
      return createErrorResponse('MATERIAL_NOT_FOUND', '无法读取物料配置');
    }

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

      if (!catalog[cat]) {
        catalog[cat] = { name: categoryNames[cat] || cat, components: [] };
      }

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

    return createSuccessResponse({
      totalComponents: totalCount,
      categories: catalog,
      categoryFilter: category || 'all',
      searchFilter: search || null
    });
  },

  async vtj_get_component_detail({ name }) {
    const material = getMaterialConfig();
    if (!material) {
      return createErrorResponse('MATERIAL_NOT_FOUND', '无法读取物料配置');
    }

    const comp = material[name];
    if (!comp) {
      // 尝试模糊搜索
      const suggestions = Object.keys(material).filter(k =>
        k.toLowerCase().includes(name.toLowerCase()) ||
        material[k].label?.toLowerCase().includes(name.toLowerCase())
      );
      return createErrorResponse('MATERIAL_NOT_FOUND', `未找到组件 "${name}"`, {
        suggestion: `未找到组件 "${name}"`,
        suggestions: suggestions.slice(0, 10)
      });
    }

    return createSuccessResponse({
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
    });
  }
};
