#!/usr/bin/env node

/**
 * VTJ MCP Server — 桥接 Claude Code 与 VTJ.PRO 低代码平台
 *
 * 重构后的薄包装：所有逻辑已拆分至模块化结构
 *   src/server.js       — MCP 服务器 + 工具/资源注册
 *   src/tools/*         — 7 个工具模块（19 个工具）
 *   src/core/*          — 解析器、文件系统、同步引擎
 *   src/utils/*         — 错误码、日志、辅助函数
 */

import { start } from './src/server.js';

start().catch((err) => {
  console.error('VTJ MCP Server 启动失败:', err);
  process.exit(1);
});
