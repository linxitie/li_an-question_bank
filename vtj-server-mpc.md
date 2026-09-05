# VTJ MCP Server - 工具与资源记忆点

> 位置: `vtj-mcp-server/vtj-mcp-server.js`
> 配置: `.mcp.json` → `vtj` server

## MCP Server 架构

```
Claude Code ←→ VTJ MCP Server ←→ VTJ Project
  (stdio)       (Node.js)         (.vtj/ + src/)
```

## 可用工具（15个）

### 项目信息类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_get_project_info` | 获取项目完整配置 | 无 |
| `vtj_list_pages` | 列出所有页面 | `filter`: raw/generated/all |
| `vtj_list_blocks` | 列出区块组件 | `category`: 分类筛选 |
| `vtj_list_apis` | 列出 API 定义 | 无 |

### 文件读写类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_read_vue_file` | 读取 .vue 文件 | `id`, `section`: full/template/script/style |
| `vtj_write_vue_script` | 修改 script 部分 | `id`, `scriptContent`, `mode`: replace/methods/state/lifeCycles/addMethod |
| `vtj_read_dsl_file` | 读取 DSL JSON | `id`, `section`: full/nodes/state/methods/lifeCycles |
| `vtj_write_dsl_file` | 写入 DSL JSON | `id`, `section`, `content` |
| `vtj_write_vue_full` | 写入完整 .vue | `id`, `content` |
| `vtj_write_vue_template` | 写入 template 部分 | `id`, `templateContent` |
| `vtj_write_vue_style` | 写入 style 部分 | `id`, `styleContent` |

### 同步操作类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_sync_vue_to_dsl` | 同步 Vue → DSL | `id`, `dryRun` |
| `vtj_check_consistency` | 检查一致性 | `id` |

### 结构分析类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_get_page_structure` | 获取页面节点树 | `id`, `depth` |

### 路由管理类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_get_routing_info` | 获取路由配置 | 无 |
| `vtj_add_route` | 添加静态路由 | `path`, `name`, `componentPath`, `title` |

### 物料查询类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_get_material_catalog` | 获取组件目录 | `category`, `search` |
| `vtj_get_component_detail` | 获取组件详情 | `name` |

### 项目操作类
| 工具 | 用途 | 关键参数 |
|---|---|---|
| `vtj_create_page_scaffold` | 创建新页面 | `id`, `name`, `title`, `addRoute`, `routePath` |

## MCP 资源（3个）

| URI | 说明 |
|---|---|
| `vtj://project/config` | 项目完整配置 JSON |
| `vtj://project/routing` | 路由配置信息 |
| `vtj://materials/catalog` | 物料目录 |

## 典型工作流

### 修改业务逻辑
```
1. vtj_read_vue_file(id) → 了解当前代码
2. vtj_read_dsl_file(id) → 查看 DSL 状态
3. vtj_write_vue_script(id, mode, scriptContent) → 更新方法
4. vtj_sync_vue_to_dsl(id) → 同步到 JSON
5. 提醒用户清理 Vite 缓存
```

### 新增页面
```
1. vtj_create_page_scaffold(id, name, title, addRoute=true) → 创建脚手架
2. vtj_add_route(path, name, componentPath) → 添加路由
3. 用户在设计器中拖拽 UI
4. vtj_get_material_catalog() → 了解可用组件
5. 补充业务逻辑方法
```

### 了解项目
```
1. vtj_get_project_info() → 项目全貌
2. vtj_get_routing_info() → 路由结构
3. vtj_get_material_catalog() → 组件库
```

## 关键约定

1. **只修改 script** - UI 变更通过 VTJ 设计器
2. **修改后必须同步** - `.vue` → `vtj_sync_vue_to_dsl` → `.vtj/files/*.json`
3. **raw: true 受保护** - VTJ 设计器不覆盖
4. **自动备份** - 写操作创建 `.bak` 文件

## 常用页面 ID

| ID | 页面 | 说明 |
|---|---|---|
| home_page | 首页 | 首页 |
| question_bank | 题库 | 题库主页 |
| login | 登录 | 用户登录 |
| teacher_dashboard | 教师工作台 | 教师端 |
| admin_dashboard | 系统总览 | 管理员端 |
| answer_page | 答题 | 学生答题 |
| smart_exam | 智能组卷 | 智能组卷 |
| wrong_questions | 错题集 | 错题管理 |
| notes | 笔记 | 笔记管理 |
| favorites | 收藏 | 收藏管理 |

## VTJ 物料分类

- **html** - HTML 原生元素
- **element-plus** - Element Plus 组件
- **vtj-ui** - VTJ UI 组件
- **vtj-charts** - VTJ 图表组件
- **antdv** - Ant Design Vue 组件（可选）
