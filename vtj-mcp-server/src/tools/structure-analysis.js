/**
 * 页面结构分析工具模块 — 获取页面节点树结构概览
 */

import { readJSON, existsFile, getDslPath } from '../core/file-system.js';
import { parseNodes } from '../core/parser.js';
import { createSuccessResponse, createErrorResponse } from '../utils/logger.js';

// ── 工具定义 ──────────────────────────────────────────────

export const TOOLS = [
  {
    name: 'vtj_get_page_structure',
    description: '获取页面的节点树结构概览。解析 DSL JSON 的 nodes[] 数组，展示模板中的元素层次结构、组件引用、指令和事件绑定。',
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
  }
];

// ── 处理器 ──────────────────────────────────────────────

export const handlers = {
  async vtj_get_page_structure({ id, depth = 3 }) {
    const dslPath = getDslPath(id);
    if (!existsFile(dslPath)) {
      return createErrorResponse('FILE_NOT_FOUND', `DSL 文件不存在: .vtj/files/${id}.json`);
    }

    const dsl = readJSON(dslPath);
    if (!dsl?.nodes) {
      return createErrorResponse('NODES_NOT_FOUND', 'DSL 中无 nodes 定义');
    }

    const structure = parseNodes(dsl.nodes, depth);

    return createSuccessResponse({
      id,
      name: dsl.name,
      rootNodesCount: dsl.nodes.length,
      maxDepth: depth,
      structure
    });
  }
};
