# VTJ MCP Server — 工具参考

所有 19 个工具按类别分组。每个工具通过 MCP 协议提供，支持 Claude Code 直接调用。

---

## 项目信息类（4 个工具）

### `vtj_get_project_info`
获取项目完整配置：页面列表、区块列表、API 列表及数量统计。

**参数**：无
**返回**：`{ name, pages: [...], blocks: [...], apis: [...], counts: { pages, blocks, apis } }`

### `vtj_list_pages`
列出项目中所有页面。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `filter` | string | 否 | `"raw"` 仅设计师页面 / `"generated"` 仅代码生成页面 |

**返回**：`{ pages: [{ id, name, title, type, raw, ... }] }`

### `vtj_list_blocks`
列出所有区块组件。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `category` | string | 否 | 按分类筛选，如 `"layout"` / `"form"` / `"data"` |

**返回**：`{ blocks: [...] }`

### `vtj_list_apis`
列出所有 API 定义。

**参数**：无
**返回**：`{ apis: [...] }`

---

## 文件读写类（7 个工具）

### `vtj_read_vue_file`
读取 `.vtj/vue/*.vue` 文件内容。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `section` | string | 否 | `"template"` / `"script"` / `"style"`，不填返回完整文件 |

**返回**：`{ id, content, section? }`

### `vtj_write_vue_script`
修改 `.vue` 文件的 `<script>` 部分。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `content` | string | 是 | 新的 script 内容 |
| `mode` | string | 否 | `"replace"` / `"append"` / `"prepend"` / `"merge"` / `"patch"`（默认 `"replace"`） |
| `dryRun` | boolean | 否 | 预览不写入 |

**返回**：`{ success, path, backupPath? }`

### `vtj_read_dsl_file`
读取 `.vtj/files/*.json` DSL 定义文件。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `section` | string | 否 | `"state"` / `"methods"` / `"nodes"` / `"lifeCycles"`，不填返回完整 JSON |

**返回**：`{ id, content, section? }`

### `vtj_write_vue_template`
修改 `.vue` 文件的 `<template>` 部分。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `content` | string | 是 | 新的 template 内容 |
| `dryRun` | boolean | 否 | 预览不写入 |

### `vtj_write_vue_style`
修改 `.vue` 文件的 `<style>` 部分。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `content` | string | 是 | 新的 style 内容 |
| `dryRun` | boolean | 否 | 预览不写入 |

### `vtj_write_dsl_file`
修改 DSL JSON 文件的指定 section。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `section` | string | 是 | `"state"` / `"methods"` / `"nodes"` / `"lifeCycles"` |
| `content` | any | 是 | 新的 section 内容 |
| `dryRun` | boolean | 否 | 预览不写入 |

### `vtj_write_vue_full`
完整替换 `.vue` 文件内容。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `content` | string | 是 | 完整的 Vue SFC 内容 |
| `dryRun` | boolean | 否 | 预览不写入 |

---

## 同步操作类（2 个工具）

### `vtj_sync_vue_to_dsl`
将 `.vue` 文件中的业务逻辑同步回 `.vtj/files/*.json` DSL。同步内容包括：methods 方法签名、state 字段、lifeCycles 声明、`__VERSION__` 版本号。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `dryRun` | boolean | 否 | 预览不写入 |

**返回**：`{ success, methods?, state?, version?, dryRun? }`

> ⚠️ `raw: true` 的页面受保护，不允许同步。

### `vtj_check_consistency`
检查 `.vue` 文件和 DSL 之间的一致性（版本号、方法签名、状态字段）。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 否 | 指定页面 ID，不填检查所有文件 |

**返回**：`{ checked, inconsistent?, issues? }`

---

## 结构分析类（1 个工具）

### `vtj_get_page_structure`
获取页面的节点树结构概览。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 页面/区块 ID |
| `depth` | number | 否 | 展开深度（默认 2） |

**返回**：`{ id, name, children: [...] }`

---

## 路由管理类（2 个工具）

### `vtj_get_routing_info`
获取完整路由配置（静态路由 + VTJ 自动路由）。

**参数**：无
**返回**：`{ staticRoutes, autoRoutes, total }`

### `vtj_add_route`
在 `src/router/statics.js` 中添加静态路由条目。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 路由路径，如 `"/my-page"` |
| `name` | string | 是 | 组件名称（PascalCase） |
| `componentPath` | string | 否 | 组件文件路径 |
| `dryRun` | boolean | 否 | 预览不写入 |

**返回**：`{ success, path, content? }`

---

## 物料查询类（2 个工具）

### `vtj_get_material_catalog`
获取全部可用组件目录。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `category` | string | 否 | 按分类筛选 |
| `search` | string | 否 | 按名称搜索 |

**返回**：`{ components: [...], total }`

### `vtj_get_component_detail`
获取单个组件的详细信息。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 组件名称 |

**返回**：`{ name, description, props?, events?, slots? }`

---

## 项目操作类（1 个工具）

### `vtj_create_page_scaffold`
为新页面创建基础脚手架文件：`.vtj/files/<id>.json` DSL 定义 + `.vtj/vue/<id>.vue` Vue SFC + 可选静态路由。

**参数**：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 新页面唯一 ID |
| `name` | string | 是 | 组件名称（PascalCase） |
| `title` | string | 是 | 页面标题（中文） |
| `icon` | string | 否 | Element Plus 图标名（默认 `"Collection"`） |
| `addRoute` | boolean | 否 | 是否同时添加静态路由（默认 false） |
| `routePath` | string | 否 | 当 `addRoute=true` 时的路由路径 |
| `dryRun` | boolean | 否 | 预览不创建 |

**返回**：`{ id, name, title, files: { vue, dsl }, route? }`

---

## 通用说明

- 所有写操作均创建 `.bak` 备份文件
- 所有 8 个写/同步工具支持 `dryRun` 预览模式
- `raw: true` 页面受 VTJ 设计器保护，部分操作受限
- 错误响应格式：`{ success: false, error: { code, message, suggestion } }`
