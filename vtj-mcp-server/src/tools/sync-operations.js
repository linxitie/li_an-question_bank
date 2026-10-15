/**
 * 同步操作工具模块 — 包装 sync-engine 的工具接口
 */

import { syncVueToDSL, checkConsistency } from '../core/sync-engine.js';

// ── 工具定义 ──────────────────────────────────────────────

export const TOOLS = [
  {
    name: 'vtj_sync_vue_to_dsl',
    description: `将 .vue 文件中修改的业务逻辑同步回 .vtj/files/*.json DSL 文件。
同步内容：methods 方法签名、state 字段、lifeCycles 生命周期声明、__VERSION__ 版本号。

⚠️ raw 手写页面（项目配置中 "raw": true）禁止同步，调用返回 RAW_PAGE_PROTECTED。
原因：同步提取器读不到全部手写方法，同步会丢失它们，且设计器回存会把丢失部分覆盖到手写代码上。
这类页面的 <template> 调整请让用户在 VTJ 设计器中拖拽完成。
建议先加 dryRun: true 预览再实际写入。`,
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
    description: '检查 .vue 文件和 .vtj/files/*.json DSL 之间的一致性，包括版本号、方法签名、状态字段等。',
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
  }
];

// ── 处理器 ──────────────────────────────────────────────

export const handlers = {
  async vtj_sync_vue_to_dsl({ id, dryRun = false }) {
    return syncVueToDSL(id, { dryRun });
  },

  async vtj_check_consistency({ id } = {}) {
    return checkConsistency(id);
  }
};
