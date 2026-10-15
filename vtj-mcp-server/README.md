# VTJ MCP Server — Claude Code ↔ VTJ.PRO 桥接服务

将 Claude Code 与 VTJ.PRO 低代码平台连接，使 Claude Code 能够直接操作 VTJ 项目。

## 架构概览

```
┌──────────────┐     MCP Protocol      ┌─────────────────┐     File I/O     ┌──────────────┐
│  Claude Code │ ◄──────────────────► │ VTJ MCP Server   │ ◄──────────────► │ VTJ Project  │
│   (终端)     │    (stdio/JSON-RPC)   │  (Node.js)       │                  │ .vtj/ + src/ │
└──────────────┘                       └─────────────────┘                  └──────────────┘
```

## 快速开始

### 1. 安装依赖
```bash
cd vtj-mcp-server && npm install
# 或从项目根目录
npm run mcp:setup
```

### 2. 配置 Claude Code
项目根目录的 `.mcp.json` 已配置好：
```json
{
  "mcpServers": {
    "vtj": {
      "command": "node",
      "args": ["vtj-mcp-server/vtj-mcp-server.js"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

### 3. 启动 Claude Code
启动 Claude Code 后，VTJ 工具将自动加载。可以通过以下方式验证：
```bash
npm run mcp:test
```

## 工具列表（19个工具 + 3个资源）

### 项目信息类（4个工具）
| 工具 | 说明 |
|------|------|
| `vtj_get_project_info` | 获取项目完整配置（页面、区块、API、依赖） |
| `vtj_list_pages` | 列出所有页面（支持 raw/generated 筛选） |
| `vtj_list_blocks` | 列出所有区块组件（支持按分类筛选） |
| `vtj_list_apis` | 列出所有 API 定义 |

### 文件读写类（7个工具）
| 工具 | 说明 |
|------|------|
| `vtj_read_vue_file` | 读取 .vue 文件（支持 section 筛选） |
| `vtj_write_vue_script` | 修改 .vue 的 `<script>` 部分（5种模式） |
| `vtj_read_dsl_file` | 读取 DSL JSON 文件（支持 section 筛选） |
| `vtj_write_vue_template` | 修改 .vue 的 `<template>` 部分 |
| `vtj_write_vue_style` | 修改 .vue 的 `<style>` 部分 |
| `vtj_write_dsl_file` | 修改 DSL JSON 文件的指定 section |
| `vtj_write_vue_full` | 完整替换 .vue 文件内容 |

### 同步操作类（2个工具）
| 工具 | 说明 |
|------|------|
| `vtj_sync_vue_to_dsl` | 同步 Vue → DSL JSON（含 dryRun 预览模式） |
| `vtj_check_consistency` | 检查 Vue ↔ DSL 一致性 |

### 结构分析类（1个工具）
| 工具 | 说明 |
|------|------|
| `vtj_get_page_structure` | 获取页面节点树结构概览 |

### 路由管理类（2个工具）
| 工具 | 说明 |
|------|------|
| `vtj_get_routing_info` | 获取完整路由配置（静态 + VTJ 自动路由） |
| `vtj_add_route` | 添加静态路由条目 |

### 物料查询类（2个工具）
| 工具 | 说明 |
|------|------|
| `vtj_get_material_catalog` | 获取全部可用组件目录 |
| `vtj_get_component_detail` | 获取单个组件详细信息 |

### 项目操作类（1个工具）
| 工具 | 说明 |
|------|------|
| `vtj_create_page_scaffold` | 创建新页面脚手架（Vue + DSL + 可选路由） |

## VTJ 资源（3个资源）

Claude Code 可以读取以下 VTJ 项目资源：
- `vtj://project/config` — 项目完整配置 JSON
- `vtj://project/routing` — 路由配置信息
- `vtj://materials/catalog` — 物料目录

## 开发工作流

### 典型工作流 1：添加业务逻辑
```
1. 用户: "给题库页的快速练习按钮加上真实数据加载"
2. Claude 调用 vtj_read_vue_file(id="mjvdqdu1") 了解当前代码
3. Claude 调用 vtj_read_dsl_file(id="mjvdqdu1") 查看 DSL 状态定义
4. Claude 调用 vtj_write_vue_script(id="mjvdqdu1", mode="methods", ...) 更新方法
5. Claude 调用 vtj_sync_vue_to_dsl(id="mjvdqdu1") 同步到 JSON
6. Claude 提醒用户清理 Vite 缓存并刷新
```

### 典型工作流 2：新增页面
```
1. 用户: "创建一个成绩排行榜页面"
2. Claude 调用 vtj_create_page_scaffold(...) 创建脚手架
3. Claude 调用 vtj_add_route(...) 添加路由
4. 用户在 VTJ 设计器中拖拽 UI
5. Claude 调用 vtj_get_material_catalog() 了解可用组件
6. Claude 补充业务逻辑方法
```

### 典型工作流 3：了解项目
```
1. 用户: "这个项目有哪些页面和组件？"
2. Claude 调用 vtj_get_project_info() 获取全貌
3. Claude 调用 vtj_get_routing_info() 了解路由
4. Claude 调用 vtj_get_material_catalog() 了解可用组件库
```

## 关键设计原则

1. **Claude Code 只修改 `<script>` 逻辑**：UI 结构变更通过 VTJ 设计器
2. **修改后必须同步**：`.vue` 修改 → `vtj_sync_vue_to_dsl` → 更新 `.vtj/files/*.json`
3. **raw: true 页面受保护**：VTJ 设计器不会覆盖这些页面的 Vue 文件
4. **自动备份**：所有写操作都会创建 `.bak` 备份文件
5. **dryRun 预览**：所有 8 个写/同步工具支持 `dryRun` 参数预览变更

## 项目结构

```
vtj-mcp-server/
├── package.json              # 项目配置
├── vtj-mcp-server.js         # MCP 服务器入口（薄包装）
├── src/
│   ├── server.js             # MCP 服务器 + 工具/资源注册
│   ├── core/
│   │   ├── file-system.js    # VTJ 文件系统抽象
│   │   ├── parser.js         # Vue SFC / DSL 解析
│   │   └── sync-engine.js    # Vue ↔ DSL 同步引擎
│   ├── tools/
│   │   ├── project-info.js   # 项目信息工具（4个）
│   │   ├── file-operations.js # 文件读写工具（7个）
│   │   ├── sync-operations.js # 同步操作工具（2个）
│   │   ├── structure-analysis.js # 结构分析工具（1个）
│   │   ├── route-management.js # 路由管理工具（2个）
│   │   ├── material-query.js # 物料查询工具（2个）
│   │   └── project-actions.js # 项目操作工具（1个）
│   └── utils/
│       ├── error-codes.js    # 错误码定义
│       ├── helpers.js        # 辅助函数
│       └── logger.js         # 日志 + 响应格式化
├── test/                     # 123 个测试用例
│   ├── server.test.js
│   ├── utils/
│   ├── core/
│   └── tools/
├── docs/
│   ├── TOOLS_REFERENCE.md    # 工具详细参考
│   └── WORKFLOWS.md          # 开发工作流指南
└── node_modules/
```

## 测试

```bash
# 运行所有测试
npm test

# 运行特定模块测试
node --test "test/server.test.js"
node --test "test/tools/*.test.js"
```

## 文档

- [工具参考](docs/TOOLS_REFERENCE.md) — 19 个工具的完整参数和返回值说明
- [开发工作流](docs/WORKFLOWS.md) — 7 个典型工作流示例
