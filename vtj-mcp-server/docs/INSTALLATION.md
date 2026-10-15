# VTJ MCP Server 安装配置说明书

## 前置要求

在安装 VTJ MCP Server 之前，请确保您的环境满足以下条件：

| 依赖项 | 最低版本 | 说明 |
|--------|----------|------|
| **Node.js** | v18.0.0+ | 推荐 v20 LTS 或更高版本 |
| **npm** | v9.0.0+ | 随 Node.js 一起安装 |
| **Claude Code** | 最新版 | Anthropic 官方 CLI 工具 |
| **VTJ.PRO 项目** | - | 需要已初始化的 VTJ 项目目录 |

### 检查环境

```bash
# 检查 Node.js 版本
node --version    # 应输出 v18.x.x 或更高

# 检查 npm 版本
npm --version     # 应输出 9.x.x 或更高

# 检查 Claude Code 是否安装
claude --version  # 应输出版本号
```

---

## 安装步骤

### 第一步：进入项目目录

将 VTJ MCP Server 放置在 VTJ 项目的 `vtj-mcp-server` 子目录中：

```bash
# 假设您的 VTJ 项目在 /path/to/your-project
cd /path/to/your-project/vtj-mcp-server
```

### 第二步：安装依赖

```bash
npm install
```

安装完成后，`node_modules` 目录中将包含 `@modelcontextprotocol/sdk` 依赖。

### 第三步：验证安装

```bash
# 运行测试确认一切正常
npm test
```

如果所有 153 个测试通过，说明安装成功。

---

## 配置 Claude Code

### 方式一：项目级配置（推荐）

在 VTJ 项目根目录创建 `.mcp.json` 文件：

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

> **注意**：`${workspaceFolder}` 会被 Claude Code 自动替换为当前工作区路径。

### 方式二：全局配置

如果您希望在所有项目中使用 VTJ MCP Server，可以在 Claude Code 全局配置中添加：

```bash
claude config set mcpServers.vtj.command node
claude config set mcpServers.vtj.args '["vtj-mcp-server/vtj-mcp-server.js"]'
```

### 方式三：手动启动

如果不想通过 Claude Code 自动启动，可以手动运行服务器：

```bash
cd /path/to/your-vtj-project
node vtj-mcp-server/vtj-mcp-server.js
```

服务器将在 stdio 模式下运行，等待 MCP 协议消息。

---

## 验证配置

### 1. 启动 Claude Code

```bash
cd /path/to/your-vtj-project
claude
```

### 2. 测试工具是否加载

在 Claude Code 中输入以下问题：

```
请列出所有可用的 VTJ 工具
```

Claude 应该能够识别并调用 19 个 VTJ 工具。

### 3. 测试具体功能

```
帮我查看这个项目的页面列表
```

Claude 将调用 `vtj_get_project_info` 工具，返回项目配置信息。

---

## 目录结构要求

VTJ MCP Server 需要在标准的 VTJ 项目结构中运行：

```
your-vtj-project/
├── .vtj/                    # VTJ 项目数据
│   ├── projects/            # 项目配置
│   │   └── *.json
│   ├── materials/           # 物料配置
│   │   └── *.json
│   ├── files/               # DSL 定义文件
│   │   └── *.json
│   ├── vue/                 # Vue SFC 文件
│   │   └── *.vue
│   └── router/              # 路由配置
│       └── statics.js
├── src/                     # 源代码目录
│   └── router/
│       └── statics.js       # 静态路由定义
├── vtj-mcp-server/          # MCP Server 目录
│   ├── package.json
│   ├── vtj-mcp-server.js
│   ├── src/
│   ├── test/
│   └── node_modules/
├── .mcp.json                # MCP 配置文件（需要创建）
└── ...
```

> **重要**：如果 `.vtj/` 目录不存在，工具将返回 `PROJECT_NOT_FOUND` 错误。

---

## 常见问题

### Q1: 安装依赖时报错

**现象**：`npm install` 失败，提示网络或权限问题

**解决方案**：
```bash
# 使用淘宝镜像
npm install --registry=https://registry.npmmirror.com

# 或使用 yarn
yarn install
```

### Q2: 工具未被 Claude Code 识别

**现象**：Claude Code 无法调用 VTJ 工具

**检查清单**：
1. 确认 `.mcp.json` 文件位于项目根目录
2. 确认文件内容格式正确（JSON 语法）
3. 确认 `vtj-mcp-server.js` 路径正确
4. 重启 Claude Code 后重试

### Q3: 返回 "项目未找到" 错误

**现象**：调用工具时返回 `PROJECT_NOT_FOUND`

**原因**：`.vtj/projects/` 目录下没有项目配置文件

**解决方案**：确保在 VTJ 项目根目录中运行，且项目已通过 VTJ 设计器初始化。

### Q4: 如何查看服务器日志

服务器日志输出到 stderr，不会影响 MCP 协议通信：

```bash
# 将 stderr 重定向到文件
node vtj-mcp-server/vtj-mcp-server.js 2>vtj-mcp.log

# 实时查看日志
node vtj-mcp-server/vtj-mcp-server.js 2>&1 | tee vtj-mcp.log
```

### Q5: 如何更新 VTJ MCP Server

```bash
cd vtj-mcp-server
git pull
npm install    # 如果依赖有变化
npm test       # 验证更新
```

---

## 卸载

```bash
# 1. 删除 MCP Server 目录
rm -rf vtj-mcp-server/

# 2. 删除 MCP 配置文件（如果不再需要）
rm .mcp.json
```

---

## 支持的工具一览（19 个）

| 类别 | 工具名 | 功能 |
|------|--------|------|
| 项目信息 | `vtj_get_project_info` | 获取项目完整配置 |
| 项目信息 | `vtj_list_pages` | 列出所有页面 |
| 项目信息 | `vtj_list_blocks` | 列出所有区块 |
| 项目信息 | `vtj_list_apis` | 列出所有 API |
| 文件读写 | `vtj_read_vue_file` | 读取 Vue 文件 |
| 文件读写 | `vtj_write_vue_script` | 修改 Vue script |
| 文件读写 | `vtj_read_dsl_file` | 读取 DSL 文件 |
| 文件读写 | `vtj_write_vue_template` | 修改 Vue template |
| 文件读写 | `vtj_write_vue_style` | 修改 Vue style |
| 文件读写 | `vtj_write_dsl_file` | 修改 DSL 文件 |
| 文件读写 | `vtj_write_vue_full` | 完整替换 Vue 文件 |
| 同步操作 | `vtj_sync_vue_to_dsl` | Vue → DSL 同步 |
| 同步操作 | `vtj_check_consistency` | 一致性检查 |
| 结构分析 | `vtj_get_page_structure` | 页面结构概览 |
| 路由管理 | `vtj_get_routing_info` | 路由配置查询 |
| 路由管理 | `vtj_add_route` | 添加静态路由 |
| 物料查询 | `vtj_get_material_catalog` | 物料目录查询 |
| 物料查询 | `vtj_get_component_detail` | 组件详情查询 |
| 项目操作 | `vtj_create_page_scaffold` | 创建页面脚手架 |

详细参数说明请参考 `docs/TOOLS_REFERENCE.md`。
